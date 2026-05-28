import io
import csv
import time
import threading
import traceback
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse

from data_loader import load_all_csvs, load_csvs_from_uploads, build_subject_profiles
from rule_engine import run_all_rules
from models import AnalysisResult, Flag
import config

app = FastAPI(title="OBERON-301 Cross-Form Clinical Data Review")

app_state = {
    "dataframes": None,
    "profiles": None,
    "results": None,
    "status": "idle",
    "progress": "",
    "error": None,
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.post("/api/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    file_dict = {}
    for f in files:
        content = await f.read()
        file_dict[f.filename] = content

    try:
        dataframes = load_csvs_from_uploads(file_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing CSV files: {e}")

    expected = {"demographics", "medical_history", "concomitant_meds", "adverse_events",
                "lab_data", "vital_signs", "disposition"}
    missing = expected - set(dataframes.keys())
    if missing:
        from data_loader import FILE_MAP
        missing_files = [FILE_MAP[k] for k in missing]
        raise HTTPException(status_code=400, detail=f"Missing files: {', '.join(missing_files)}")

    profiles = build_subject_profiles(dataframes)
    app_state["dataframes"] = dataframes
    app_state["profiles"] = profiles
    app_state["results"] = None
    app_state["status"] = "uploaded"
    app_state["error"] = None

    summary = {k: len(df) for k, df in dataframes.items()}
    return {"status": "ok", "subjects": len(profiles), "file_summary": summary}


@app.post("/api/analyze")
async def analyze(body: dict | None = None):
    if app_state["dataframes"] is None:
        raise HTTPException(status_code=400, detail="No data uploaded. Upload CSV files first.")

    if app_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Analysis already running.")

    body = body or {}
    llm_provider = body.get("llm_provider")
    skip_llm = body.get("skip_llm", True)

    app_state["status"] = "running"
    app_state["progress"] = "Running rule-based checks..."
    app_state["error"] = None

    def run_analysis():
        start_time = time.time()
        try:
            flags = run_all_rules(app_state["dataframes"], app_state["profiles"])
            rule_count = len(flags)
            app_state["progress"] = f"Rule engine complete. {rule_count} flags found."

            ai_flags = []
            llm_provider_name = None
            llm_model_name = None

            if not skip_llm:
                try:
                    from llm_client import create_llm_client
                    from llm_engine import run_llm_analysis

                    client = create_llm_client(llm_provider)
                    llm_provider_name = client.provider_name
                    llm_model_name = client.model_name

                    def progress_cb(msg):
                        app_state["progress"] = msg

                    ai_flags = run_llm_analysis(
                        app_state["profiles"], flags, client, progress_callback=progress_cb
                    )
                    flags.extend(ai_flags)
                except Exception as e:
                    print(f"LLM analysis error: {e}")
                    traceback.print_exc()
                    app_state["progress"] = f"LLM failed: {e}. Showing rule-based results only."

            elapsed = time.time() - start_time
            manual_hours = len(app_state["profiles"]) * config.AVG_MANUAL_REVIEW_MINUTES / 60
            estimated_saved = max(0, manual_hours - (elapsed / 3600))

            app_state["results"] = AnalysisResult(
                total_subjects=len(app_state["profiles"]),
                total_flags=len(flags),
                critical_count=sum(1 for f in flags if f.severity == "Critical"),
                major_count=sum(1 for f in flags if f.severity == "Major"),
                minor_count=sum(1 for f in flags if f.severity == "Minor"),
                rule_flags=rule_count,
                ai_flags=len(ai_flags),
                flags=flags,
                processing_time_seconds=round(elapsed, 2),
                estimated_hours_saved=round(estimated_saved, 1),
                llm_provider=llm_provider_name,
                llm_model=llm_model_name,
            )
            app_state["status"] = "complete"
            app_state["progress"] = "Analysis complete."
            print(f"Analysis complete: {len(flags)} flags in {elapsed:.2f}s")

        except Exception as e:
            print(f"Analysis error: {e}")
            traceback.print_exc()
            app_state["status"] = "error"
            app_state["progress"] = f"Error: {e}"
            app_state["error"] = str(e)

    thread = threading.Thread(target=run_analysis, daemon=True)
    thread.start()

    # For fast rule-only analysis, wait up to 5 seconds for it to finish
    # so we can return results directly
    if skip_llm:
        thread.join(timeout=5.0)
        if app_state["status"] == "complete" and app_state["results"]:
            return {"status": "complete", "results": app_state["results"].model_dump()}
        elif app_state["status"] == "error":
            return {"status": "error", "error": app_state["error"]}

    return {"status": "started"}


@app.get("/api/status")
def get_status():
    return {
        "status": app_state["status"],
        "progress": app_state["progress"],
    }


@app.get("/api/results")
def get_results():
    if app_state["results"] is None:
        raise HTTPException(status_code=404, detail="No results available. Run analysis first.")
    return app_state["results"].model_dump()


@app.get("/api/results/subject/{subject_id}")
def get_subject(subject_id: str):
    if app_state["profiles"] is None:
        raise HTTPException(status_code=404, detail="No data loaded.")
    profile = app_state["profiles"].get(subject_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Subject {subject_id} not found.")

    subject_flags = []
    if app_state["results"]:
        subject_flags = [f.model_dump() for f in app_state["results"].flags if f.subject_id == subject_id]

    return {"profile": profile.model_dump(), "flags": subject_flags}


@app.get("/api/results/export")
def export_csv():
    if app_state["results"] is None:
        raise HTTPException(status_code=404, detail="No results available.")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Subject_ID", "Rule_ID", "Forms_Involved", "Description",
        "Severity", "Source", "Confidence", "Suggested_Query",
    ])
    for f in app_state["results"].flags:
        writer.writerow([
            f.subject_id, f.rule_id, " + ".join(f.forms_involved),
            f.description, f.severity, f.source, f.confidence,
            f.suggested_query or "",
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=OBERON301_flags.csv"},
    )


@app.get("/api/config")
def get_config():
    available = []
    if config.CLAUDE_API_KEY:
        available.append("claude")
    if config.OPENAI_API_KEY:
        available.append("openai")
    return {
        "default_provider": config.LLM_PROVIDER,
        "available_providers": available,
        "claude_model": config.CLAUDE_MODEL,
        "openai_model": config.OPENAI_MODEL,
    }


static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
