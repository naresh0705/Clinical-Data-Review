import time
from models import Flag, SubjectProfile
from llm_client import LLMClient, parse_llm_json

CLINICAL_REVIEWER_SYSTEM = """You are a senior clinical data reviewer. You ONLY flag issues that would result in a clinical data query being sent to a site.

CRITICAL RULES:
- Do NOT flag missing medications for conditions that can be managed without drugs (back pain, seasonal allergies, obesity, resolved conditions)
- Do NOT flag conditions marked as Ongoing_YN="No" for missing medications
- Do NOT flag medications that are still ongoing when the corresponding condition is marked Ongoing_YN="No" — maintenance therapy after condition resolution is normal clinical practice
- Do NOT flag common supplements (Calcium, Vitamin D3, Folic Acid, Omega-3, Vitamin B12, Iron) for missing conditions
- Do NOT speculate about causality unless temporal relationship is within 14 days
- Do NOT flag normal clinical variations
- ONLY flag issues where data is MISSING, CONTRADICTORY, or ILLOGICAL
- Maximum 5 flags per subject. If you find more, keep only the top 5 by clinical significance.

A flag must meet ONE of these criteria:
1. A required field is missing or blank
2. Two data points directly contradict each other
3. A safety signal exists without corresponding documentation
4. A regulatory requirement (ICH-GCP) is violated
5. Dates are logically impossible

If a subject's profile looks clinically consistent, respond with:
{"subject_id": "...", "issues_found": [], "status": "No significant issues"}

Do NOT force-find issues where none exist."""
PHARMACOLOGIST_SYSTEM = "You are a clinical pharmacologist reviewing medication-condition alignment."
CAUSALITY_SYSTEM = "You are reviewing adverse event causality assessments."
QUERY_WRITER_SYSTEM = "You are a clinical data query writer. Generate professional, audit-ready clinical data queries."


def _format_lab_summary(lab_data: list[dict]) -> str:
    if not lab_data:
        return "No lab data available."
    tests = {}
    for row in lab_data:
        test = row.get("Lab_Test", "")
        if test not in tests:
            tests[test] = []
        tests[test].append(row)
    lines = []
    for test, rows in tests.items():
        values = []
        for r in rows:
            result = r.get("Result", "")
            visit = r.get("Visit_Name", "")
            high = r.get("Normal_Range_High")
            low = r.get("Normal_Range_Low")
            flag = ""
            try:
                rv = float(result)
                if high and rv > float(high):
                    flag = " [HIGH]"
                elif low and rv < float(low):
                    flag = " [LOW]"
            except (ValueError, TypeError):
                pass
            values.append(f"{visit}: {result}{flag}")
        lines.append(f"  {test}: {', '.join(values)}")
    return "\n".join(lines)


def _format_vitals_summary(vital_signs: list[dict]) -> str:
    if not vital_signs:
        return "No vital signs data."
    lines = []
    for v in vital_signs:
        lines.append(
            f"  {v.get('Visit_Name', '')}: BP {v.get('BP_Systolic', '')}/{v.get('BP_Diastolic', '')}, "
            f"Weight {v.get('Weight_kg', '')}kg, HR {v.get('Heart_Rate', '')} bpm"
        )
    return "\n".join(lines)


def _build_profile_review_prompt(profile: SubjectProfile) -> str:
    dem = profile.demographics
    disp = profile.disposition

    mh_lines = "\n".join(
        f"  - {m.get('MH_Term', '')}: Started {m.get('MH_Start_Date', 'N/A')}, "
        f"Ongoing: {m.get('Ongoing_YN', 'N/A')}"
        for m in profile.medical_history
    ) or "  None"

    med_lines = "\n".join(
        f"  - {m.get('Med_Name', '')}: Indication={m.get('Indication', '')}, "
        f"Started {m.get('Start_Date', 'N/A')}, Ongoing: {m.get('Ongoing_YN', 'N/A')}"
        for m in profile.concomitant_meds
    ) or "  None"

    ae_lines = "\n".join(
        f"  - {a.get('AE_Term', '')} ({a.get('AE_Verbatim', '')}): "
        f"Severity={a.get('Severity', '')}, Seriousness={a.get('Seriousness', '')}, "
        f"Causality={a.get('Causality', '')}, Start={a.get('Start_Date', 'N/A')}, "
        f"Outcome={a.get('Outcome', '')}, Action={a.get('Action_Taken', '')}"
        for a in profile.adverse_events
    ) or "  None"

    return f"""Review the following subject profile. ONLY flag issues that would result in a clinical data query being sent to a site.

SUBJECT: {profile.subject_id}

DEMOGRAPHICS:
- DOB: {dem.get('DOB', 'N/A')}, Sex: {dem.get('Sex', 'N/A')}
- Screening Date: {dem.get('Screening_Date', 'N/A')}
- Informed Consent Date: {dem.get('Informed_Consent_Date', 'N/A')}

MEDICAL HISTORY:
{mh_lines}

CONCOMITANT MEDICATIONS:
{med_lines}

ADVERSE EVENTS:
{ae_lines}

LAB DATA (summary):
{_format_lab_summary(profile.lab_data)}

VITAL SIGNS:
{_format_vitals_summary(profile.vital_signs)}

DISPOSITION:
- Status: {disp.get('Status', 'N/A')}
- Last Visit: {disp.get('Last_Visit_Date', 'N/A')}
- Reason: {disp.get('Reason_Discontinuation', 'N/A')}

ONLY flag issues where:
1. A medication exists with NO matching condition in Medical History or Adverse Events
2. Two data points directly CONTRADICT each other
3. A safety signal (abnormal labs, vital signs) exists WITHOUT corresponding AE documentation
4. A regulatory requirement (ICH-GCP) is clearly violated
5. Dates are logically impossible

Do NOT flag:
- Missing medications for conditions manageable without drugs (back pain, seasonal allergies, obesity, resolved conditions)
- Conditions marked Ongoing_YN="No" for missing medications
- Normal clinical variations
- Speculative causality unless temporal relationship is within 14 days

For each issue, rate confidence:
- CRITICAL: Data directly contradicts (dates impossible, fatal but completed)
- HIGH: Strong clinical evidence of missing data (lab 3x ULN with no AE)
- MEDIUM: Possible issue but could have clinical explanation
- LOW: Minor observation, likely normal variation

Only return CRITICAL and HIGH confidence issues.

Respond ONLY in JSON format:
{{
  "subject_id": "{profile.subject_id}",
  "issues_found": [
    {{
      "issue_id": "LLM-XXX",
      "forms_involved": ["Form1", "Form2"],
      "description": "...",
      "severity": "Critical|Major|Minor",
      "confidence": "Critical|High",
      "suggested_query": "..."
    }}
  ],
  "status": "Issues found|No significant issues"
}}"""


def _build_med_condition_prompt(profile: SubjectProfile) -> str:
    mh_terms = "\n".join(f"  - {m.get('MH_Term', '')} (Ongoing: {m.get('Ongoing_YN', '')})"
                          for m in profile.medical_history) or "  None"
    med_lines = "\n".join(f"  - {m.get('Med_Name', '')} (Indication: {m.get('Indication', '')})"
                           for m in profile.concomitant_meds) or "  None"
    ae_terms = "\n".join(f"  - {a.get('AE_Term', '')}" for a in profile.adverse_events) or "  None"

    return f"""For each medication below, verify it has a clinically appropriate indication in either the Medical History or Adverse Events.

SUBJECT: {profile.subject_id}

MEDICAL HISTORY:
{mh_terms}

MEDICATIONS:
{med_lines}

ADVERSE EVENTS:
{ae_terms}

For each medication, respond:
- MATCH: medication has clear clinical justification
- MISMATCH: medication has NO corresponding condition AND is NOT a common supplement — specify what condition should exist

IMPORTANT — these are always MATCH, do NOT flag them:
- Common supplements: Calcium, Vitamin D3, Calcium + Vitamin D3, Folic Acid, Omega-3, Vitamin B12, Iron, Multivitamins
- Medications for conditions marked Ongoing="No" — the condition may be resolved but medication continued for maintenance
- OTC medications (antacids, mild analgesics) taken without a formal diagnosis
- Medications where the indication field already explains the reason (e.g., "Supplement", "Bone Health", "Pain Relief")

Only flag a medication as MISMATCH if it is a prescription drug with a specific clinical indication that has NO plausible match anywhere in the subject's Medical History or Adverse Events.

Respond ONLY in JSON format:
{{
  "subject_id": "{profile.subject_id}",
  "medications": [
    {{
      "med_name": "...",
      "status": "MATCH|MISMATCH",
      "explanation": "...",
      "suggested_query": "..."
    }}
  ]
}}"""


def _build_causality_prompt(subject_id: str, med: dict, ae: dict, days_diff: int,
                             mh_terms: list[str]) -> str:
    return f"""SUBJECT: {subject_id}

TEMPORAL RELATIONSHIP:
- Medication: {med.get('Med_Name', '')} started on {med.get('Start_Date', 'N/A')}
- Adverse Event: {ae.get('AE_Term', '')} ({ae.get('AE_Verbatim', '')}) started on {ae.get('Start_Date', 'N/A')}
- Days between medication start and AE onset: {days_diff}
- Current Causality Assessment: {ae.get('Causality', '')}

QUESTION:
Given the temporal relationship, is the current causality assessment of "{ae.get('Causality', '')}" appropriate?

Consider:
1. Is {med.get('Med_Name', '')} known to cause {ae.get('AE_Term', '')}?
2. Is the temporal relationship consistent with a drug-related event?
3. Are there other explanations in the subject's medical history?

Subject Medical History: {', '.join(mh_terms) if mh_terms else 'None documented'}

Respond ONLY in JSON format:
{{
  "assessment": "APPROPRIATE|QUESTIONABLE|INCORRECT",
  "explanation": "...",
  "suggested_query": "..."
}}"""


def _build_query_prompt(flag: Flag, profile: SubjectProfile | None) -> str:
    site_id = "N/A"
    if profile and profile.demographics:
        site_id = profile.demographics.get("Site_ID", "N/A")
    return f"""Generate a professional, audit-ready clinical data query for the following issue.

STUDY: OBERON-301 (Phase III)
SUBJECT: {flag.subject_id}
SITE: {site_id}

ISSUE DETECTED:
{flag.description}

Write a clinical data query in standard format:
1. State the observation clearly
2. Reference specific data values and dates
3. Ask the site to verify/clarify
4. Request specific corrective information if needed

Keep the tone professional and factual. Do not use accusatory language. Maximum 150 words.
Respond with the query text only, no JSON wrapping."""


def _find_temporal_med_ae_pairs(profiles: dict[str, SubjectProfile], window_days: int = 7) -> list[dict]:
    from datetime import datetime
    pairs = []
    for sid, profile in profiles.items():
        for ae in profile.adverse_events:
            ae_start = ae.get("Start_Date")
            if not ae_start:
                continue
            try:
                ae_date = datetime.strptime(ae_start, "%m/%d/%Y")
            except (ValueError, TypeError):
                continue
            for med in profile.concomitant_meds:
                med_start = med.get("Start_Date")
                if not med_start:
                    continue
                try:
                    med_date = datetime.strptime(med_start, "%m/%d/%Y")
                except (ValueError, TypeError):
                    continue
                diff = (ae_date - med_date).days
                if 0 <= diff <= window_days:
                    mh_terms = [m.get("MH_Term", "") for m in profile.medical_history]
                    pairs.append({
                        "subject_id": sid,
                        "med": med,
                        "ae": ae,
                        "days_diff": diff,
                        "mh_terms": mh_terms,
                    })
    return pairs


def _is_duplicate(new_flag: Flag, existing_flags: list[Flag]) -> bool:
    for ef in existing_flags:
        if ef.subject_id != new_flag.subject_id:
            continue
        forms_overlap = set(ef.forms_involved) & set(new_flag.forms_involved)
        if not forms_overlap:
            continue
        desc_new = new_flag.description.lower()
        desc_existing = ef.description.lower()
        desc_words_new = set(desc_new.split())
        desc_words_existing = set(desc_existing.split())
        word_overlap = len(desc_words_new & desc_words_existing)
        if word_overlap > len(desc_words_new) * 0.4:
            return True
        key_terms_new = {w for w in desc_words_new if len(w) > 4 and not w.isdigit()}
        key_terms_existing = {w for w in desc_words_existing if len(w) > 4 and not w.isdigit()}
        key_overlap = len(key_terms_new & key_terms_existing)
        if key_terms_new and key_overlap > len(key_terms_new) * 0.5:
            return True
    return False


def run_llm_analysis(
    profiles: dict[str, SubjectProfile],
    rule_flags: list[Flag],
    llm_client: LLMClient,
    progress_callback=None,
) -> list[Flag]:
    all_llm_flags = []

    # Prompt 1: Subject Profile Review
    for i, (sid, profile) in enumerate(profiles.items()):
        if progress_callback:
            progress_callback(f"LLM reviewing subject {i+1}/{len(profiles)}: {sid}")
        try:
            prompt = _build_profile_review_prompt(profile)
            response = llm_client.chat(prompt, system_prompt=CLINICAL_REVIEWER_SYSTEM)
            data = parse_llm_json(response)
            issues = data.get("issues_found", []) if isinstance(data, dict) else []
            for issue in issues:
                confidence = issue.get("confidence", "Medium")
                if confidence not in ("Critical", "High"):
                    continue
                flag = Flag(
                    flag_id=f"LLM-PROFILE-{sid}-{issue.get('issue_id', 'X')}",
                    subject_id=sid,
                    rule_id=issue.get("issue_id", "LLM-PROFILE"),
                    forms_involved=issue.get("forms_involved", []),
                    description=issue.get("description", ""),
                    severity=issue.get("severity", "Major"),
                    source="AI",
                    confidence=confidence,
                    suggested_query=issue.get("suggested_query"),
                )
                if not _is_duplicate(flag, rule_flags + all_llm_flags):
                    all_llm_flags.append(flag)
        except Exception:
            continue
        time.sleep(0.1)

    # Prompt 2: Medication-Condition Matching
    flagged_cm = {f.subject_id for f in rule_flags if f.rule_id == "RULE-CM-001"}
    subjects_for_med_check = [
        (sid, p) for sid, p in profiles.items()
        if sid not in flagged_cm and p.concomitant_meds
    ]
    for i, (sid, profile) in enumerate(subjects_for_med_check):
        if progress_callback:
            progress_callback(f"LLM medication check {i+1}/{len(subjects_for_med_check)}: {sid}")
        try:
            prompt = _build_med_condition_prompt(profile)
            response = llm_client.chat(prompt, system_prompt=PHARMACOLOGIST_SYSTEM)
            data = parse_llm_json(response)
            meds = data.get("medications", []) if isinstance(data, dict) else []
            for med in meds:
                if med.get("status") == "MISMATCH":
                    flag = Flag(
                        flag_id=f"LLM-MED-{sid}-{med.get('med_name', 'X')}",
                        subject_id=sid,
                        rule_id="LLM-MED-MATCH",
                        forms_involved=["Concomitant_Meds", "Medical_History"],
                        description=f"{med.get('med_name', '')}: {med.get('explanation', '')}",
                        severity="Major",
                        source="AI",
                        confidence="High",
                        suggested_query=med.get("suggested_query"),
                    )
                    if not _is_duplicate(flag, rule_flags + all_llm_flags):
                        all_llm_flags.append(flag)
        except Exception:
            continue
        time.sleep(0.1)

    # Prompt 3: AE Causality Review
    pairs = _find_temporal_med_ae_pairs(profiles)
    for i, pair in enumerate(pairs):
        if progress_callback:
            progress_callback(f"LLM causality review {i+1}/{len(pairs)}: {pair['subject_id']}")
        try:
            prompt = _build_causality_prompt(
                pair["subject_id"], pair["med"], pair["ae"],
                pair["days_diff"], pair["mh_terms"],
            )
            response = llm_client.chat(prompt, system_prompt=CAUSALITY_SYSTEM)
            data = parse_llm_json(response)
            if isinstance(data, dict) and data.get("assessment") in ("QUESTIONABLE", "INCORRECT"):
                flag = Flag(
                    flag_id=f"LLM-CAUSAL-{pair['subject_id']}-{pair['ae'].get('AE_Term', '')}",
                    subject_id=pair["subject_id"],
                    rule_id="LLM-CAUSALITY",
                    forms_involved=["Adverse_Events", "Concomitant_Meds"],
                    description=(
                        f"Causality of '{pair['ae'].get('AE_Term', '')}' assessed as "
                        f"'{pair['ae'].get('Causality', '')}' but {pair['med'].get('Med_Name', '')} was "
                        f"started {pair['days_diff']} days before AE onset. "
                        f"Assessment: {data.get('explanation', '')}"
                    ),
                    severity="Major" if data["assessment"] == "QUESTIONABLE" else "Critical",
                    source="AI",
                    confidence="High",
                    suggested_query=data.get("suggested_query"),
                )
                if not _is_duplicate(flag, rule_flags + all_llm_flags):
                    all_llm_flags.append(flag)
        except Exception:
            continue
        time.sleep(0.1)

    # Prompt 4: Generate query text for flags without one
    combined = rule_flags + all_llm_flags
    flags_needing_query = [f for f in combined if not f.suggested_query]
    for i, flag in enumerate(flags_needing_query):
        if progress_callback:
            progress_callback(f"Generating query {i+1}/{len(flags_needing_query)}")
        try:
            profile = profiles.get(flag.subject_id)
            prompt = _build_query_prompt(flag, profile)
            flag.suggested_query = llm_client.chat(prompt, system_prompt=QUERY_WRITER_SYSTEM, max_tokens=500)
        except Exception:
            continue
        time.sleep(0.1)

    return all_llm_flags
