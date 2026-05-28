# OBERON-301: Cross-Form Clinical Data Review Assistant

**Documentation Date:** May 25, 2026  
**Version:** 1.0 (POC)

---

## Overview

A tool that ingests 7 CSV files from a Phase III clinical trial (OBERON-301), links records by Subject_ID, runs rule-based checks + LLM analysis across forms, and outputs flagged issues with suggested query text via a web dashboard.

---

## Architecture

```
INPUT (7 CSVs uploaded via browser)
    |
DATA INGESTION (Parse + link by Subject_ID)
    |
LAYER 1: RULE-BASED ENGINE (18 deterministic IF/THEN checks)
    |
LAYER 2: LLM ENGINE (4 prompt templates via GPT-4o or Claude)
    |
OUTPUT DASHBOARD (flagged issues + suggested queries + metrics)
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.14 + FastAPI |
| LLM | Model-agnostic (OpenAI GPT-4o / Claude Sonnet) |
| Frontend | Vanilla HTML + CSS + JavaScript (SPA) |
| Database | None — CSV in, results out |
| Deployment | Local (uvicorn on port 8000) |

---

## Project Structure

```
Data1/
├── app.py                  # FastAPI entry point + all API routes
├── config.py               # Environment vars, constants, clinical thresholds
├── models.py               # Pydantic models (Flag, SubjectProfile, AnalysisResult)
├── data_loader.py          # CSV ingestion, date parsing, subject profile building
├── rule_engine.py          # 8 rule sets, 18 deterministic rules
├── llm_client.py           # Model-agnostic LLM adapter (ABC + OpenAI + Claude)
├── llm_engine.py           # 4 LLM prompt templates + orchestration
├── requirements.txt        # Python dependencies
├── .env                    # API keys (not committed)
├── .env.example            # Template for API keys
├── static/
│   ├── index.html          # SPA with 4 views
│   ├── styles.css          # UI styling
│   └── app.js              # Frontend logic
├── data/
│   ├── Demographics.csv    # 58 subjects
│   ├── Medical_History.csv # 217 rows
│   ├── Concomitant_Meds.csv# 191 rows
│   ├── Adverse_Events.csv  # 129 rows
│   ├── Lab_Data.csv        # 1,984 rows
│   ├── Vital_Signs.csv     # 258 rows
│   └── Disposition.csv     # 62 rows
└── POC_Technical_Handover.md
```

---

## Input Data

| File | Key Fields | Records |
|------|-----------|---------|
| Demographics.csv | Subject_ID, Site_ID, DOB, Sex, Race, Screening_Date, Informed_Consent_Date | 58 subjects |
| Medical_History.csv | Subject_ID, MH_Term, MH_Start_Date, MH_End_Date, Ongoing_YN | 217 rows |
| Concomitant_Meds.csv | Subject_ID, Med_Name, Indication, Start_Date, End_Date, Ongoing_YN | 191 rows |
| Adverse_Events.csv | Subject_ID, AE_Term, AE_Verbatim, Severity, Seriousness, Causality, Start_Date, End_Date, Action_Taken, Outcome | 129 rows |
| Lab_Data.csv | Subject_ID, Visit_Name, Visit_Date, Lab_Test, Result, Unit, Normal_Range_Low, Normal_Range_High | 1,984 rows |
| Vital_Signs.csv | Subject_ID, Visit_Name, Visit_Date, BP_Systolic, BP_Diastolic, Weight_kg, Heart_Rate | 258 rows |
| Disposition.csv | Subject_ID, Status, Last_Visit_Date, Reason_Discontinuation, Study_Completion_Date | 62 rows |

---

## Layer 1: Rule-Based Engine

18 deterministic rules across 8 rule sets. All coded as explicit IF/THEN logic in `rule_engine.py`.

### Rule Sets

| Rule Set | Rules | Description |
|----------|-------|-------------|
| 1. Date Validation | DT-001 to DT-004 | Consent before screening, AE/Med/MH date checks |
| 2. Demographics | DM-001 | Age inclusion criteria (18-75 years) |
| 3. Adverse Events | AE-001 to AE-003 | Hospitalization seriousness, fatal outcome, severe action |
| 4. Disposition | DS-001 to DS-003 | Fatal AE vs disposition, discontinued reason, study duration |
| 5. Lab Data | LAB-001 to LAB-003 | Impossible values, ALT/AST trending, hemoglobin drop |
| 6. Vital Signs | VS-001, VS-002 | Weight change >7kg, consistently elevated BP |
| 7. Cross-Form Meds | CM-001 | Ongoing condition without corresponding medication |
| 8. Exclusion Criteria | EX-001 | Exclusion term violations in medical history |

### Rule Detection Results (May 25, 2026)

- **Total rule-based flags:** 104
- **Critical:** 27
- **Major:** 77
- **Processing time:** 0.15 seconds
- **Planted errors detected by rules:** 20/20 (100%)

---

## Layer 2: LLM Engine

4 prompt templates in `llm_engine.py`, powered by a model-agnostic adapter in `llm_client.py`.

### LLM Prompts

| Prompt | Purpose | Calls | Scope |
|--------|---------|-------|-------|
| 1. Subject Profile Review | Full cross-form review per subject | 62 | Every subject |
| 2. Medication-Condition Match | Verify each med has clinical justification | ~35 | Subjects not flagged by CM-001 |
| 3. AE Causality Review | Check causality for temporal med-AE pairs | ~20 | Meds started within 7 days of AE |
| 4. Query Text Generation | Write audit-ready query for each flag | ~104 | Every flag |

### Model-Agnostic Design

```
┌─────────────────────────────┐
│      LLMClient (ABC)        │
│      .chat(prompt) -> str   │
├──────────┬──────────────────┤
│ Claude   │ OpenAI           │
│ Client   │ Client           │
└──────────┴──────────────────┘
         |
  create_llm_client(provider)  <- factory function
```

- Provider selected via `LLM_PROVIDER` env var (default) or UI dropdown (runtime override)
- Adding a new provider = one new class + one branch in factory function
- JSON response parsing handles markdown fences and malformed output

### Estimated LLM Cost Per Run

| Model | Input Cost | Output Cost | Total |
|-------|-----------|-------------|-------|
| GPT-4o ($2.50/$10 per 1M) | ~$0.59 | ~$0.97 | **~$1.56** |
| Claude Sonnet ($3/$15 per 1M) | ~$0.63 | ~$1.24 | **~$1.90** |
| Claude Haiku ($0.25/$1.25 per 1M) | ~$0.05 | ~$0.10 | **~$0.15** |

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Redirect to dashboard |
| POST | `/api/upload` | Upload 7 CSV files (multipart form) |
| POST | `/api/analyze` | Run analysis (`llm_provider`, `skip_llm` options) |
| GET | `/api/status` | Poll analysis progress |
| GET | `/api/results` | Full analysis results JSON |
| GET | `/api/results/subject/{id}` | Subject profile + flags |
| GET | `/api/results/export` | Download flags as CSV |
| GET | `/api/config` | LLM provider configuration |

---

## Frontend (Dashboard)

Single-page application with 4 views:

1. **Upload Screen** — File dropzone, LLM provider dropdown, Run Analysis button, progress indicator
2. **Summary Dashboard** — Stat cards (subjects, flags, severity breakdown), detection method split, estimated time saved
3. **Detailed Flags Table** — Sortable, filterable, expandable rows with suggested queries, CSV export
4. **Subject Detail View** — Full profile across all forms, highlighted flags, all clinical data tables

---

## Validation Checklist

26 planted errors in the dataset. Rule engine detection:

| # | Subject | Error | Expected Rule | Detected |
|---|---------|-------|---------------|----------|
| 1 | OB1136 | Age 16 — outside inclusion | DM-001 | Yes |
| 2 | OB1170 | Consent after Screening | DT-001 | Yes |
| 3 | OB1125 | T2DM in MH, no diabetes med | CM-001 | Yes |
| 4 | OB1148 | HTN in MH, no antihypertensive | CM-001 | Yes |
| 5 | OB1162 | Hepatic Impairment — exclusion | EX-001 | Yes |
| 6 | OB1186 | MH Start after Screening | DT-004 | Yes |
| 7 | OB1129 | Metformin without diabetes in MH | LLM | LLM Layer |
| 8 | OB1157 | Sumatriptan + Headache same day, "Not Related" | LLM | LLM Layer |
| 9 | OB1172 | Amoxicillin Start before Consent | DT-003 | Yes |
| 10 | OB1140 | Hospitalization but Seriousness=No | AE-001 | Yes |
| 11 | OB1176 | Fatal MI but Disposition=Completed | DS-001 | Yes |
| 12 | OB1166 | AE Start before Consent | DT-002 | Yes |
| 13 | OB1153 | Severe AE, Action=None | AE-003 | Yes |
| 14 | OB1193 | Fatal Outcome, Seriousness=No | AE-002 | Yes |
| 15 | OB1193 | Disposition Reason=AE not Death | DS-001 | Yes |
| 16 | OB1132 | ALT/AST trending 3x ULN, no AE | LAB-002 | Yes |
| 17 | OB1160 | Hemoglobin dropping, no AE | LAB-003 | Yes |
| 18 | OB1149 | Hemoglobin=45.2 impossible | LAB-001 | Yes |
| 19 | OB1134 | +14kg weight gain, no AE | VS-001 | Yes |
| 20 | OB1122 | BP >160/100 all visits, no AE/med | VS-002 | Yes |
| 21 | OB1155 | Completed but only 18 days in study | DS-003 | Yes |
| 22 | OB1169 | Discontinued, Reason blank | DS-002 | Yes |
| 23-26 | Various | Cross-form duplicates | LLM | LLM Layer |

**Rule Engine: 20/20 targeted errors detected (100%)**  
**LLM Layer: Catches #7, #8, #23-26 (cross-form reasoning beyond hard-coded rules)**  
**Target: 85%+ (22+ out of 26)**

---

## How to Run

### Prerequisites
- Python 3.12+
- OpenAI API key or Claude API key

### Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env and add your API key
```

### Start the Server

```bash
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

### Usage

1. Upload all 7 CSV files from the `data/` folder
2. Select LLM provider: "Rules Only", "OpenAI", or "Claude"
3. Click "Run Analysis"
4. View results on the Summary and Flags pages
5. Click any Subject ID for the full detail view
6. Export flags to CSV via the Export button

---

## Performance

| Metric | Rules Only | Rules + GPT-4o |
|--------|-----------|----------------|
| Processing Time | ~0.15 seconds | ~3-6 minutes |
| API Calls | 0 | ~221 |
| API Cost | $0 | ~$1.56 |
| Flags Detected | 104 | 104 + AI flags |
| Planted Errors | 20/26 (77%) | 22-26/26 (85-100%) |
| Est. Manual Hours Saved | 31 hours | 31 hours |

---

## Dependencies

```
fastapi==0.115.0
uvicorn==0.30.6
pandas==2.2.3
python-dotenv==1.0.1
python-multipart==0.0.12
anthropic==0.40.0
openai>=2.0.0
```

---

## Security Notes

- API keys are stored in `.env` (never commit this file)
- No data leaves the local machine except LLM API calls
- LLM prompts contain clinical data — ensure compliance with data handling policies
- No authentication on the web dashboard (local use only)

---

## Future Enhancements

- Add more LLM providers (Gemini, Llama via Ollama)
- Batch API calls for cost reduction
- Add authentication for multi-user deployment
- Database backend for persistent results
- Timeline visualization for subject events
- Automated re-analysis on data updates
