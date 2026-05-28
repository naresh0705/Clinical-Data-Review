# OBERON-301: Cross-Form Clinical Data Review Assistant
## Technical Handover Document

---

## PROJECT OVERVIEW

**What we're building:** A tool that ingests 7 CSV files from a clinical trial, links records by Subject_ID, runs rule-based checks + LLM analysis across forms, and outputs flagged issues with suggested query text.

**Architecture:**

```
INPUT (7 CSVs uploaded)
    ↓
DATA INGESTION (Parse + link by Subject_ID)
    ↓
LAYER 1: RULE-BASED ENGINE (deterministic IF/THEN checks)
    ↓
LAYER 2: LLM ENGINE (clinical reasoning + query generation)
    ↓
OUTPUT DASHBOARD (flagged issues + suggested queries + metrics)
```

**Tech Stack:**
- Backend: Python + FastAPI
- LLM: Claude API (claude-sonnet-4-20250514) or GPT-4
- Frontend: Simple HTML + CSS + JavaScript
- Database: None. CSV in, results out.
- Deployment: Local (for demo purposes)

---

## INPUT FILES

| File | Key Fields | Records |
|------|-----------|---------|
| Demographics.csv | Subject_ID, Site_ID, DOB, Sex, Race, Screening_Date, Informed_Consent_Date | 58 subjects |
| Medical_History.csv | Subject_ID, MH_Term, MH_Start_Date, MH_End_Date, Ongoing_YN | 217 rows, 62 subjects |
| Concomitant_Meds.csv | Subject_ID, Med_Name, Indication, Start_Date, End_Date, Ongoing_YN | 191 rows, 62 subjects |
| Adverse_Events.csv | Subject_ID, AE_Term, AE_Verbatim, Severity, Seriousness, Causality, Start_Date, End_Date, Action_Taken, Outcome | 129 rows, 51 subjects |
| Lab_Data.csv | Subject_ID, Visit_Name, Visit_Date, Lab_Test, Result, Unit, Normal_Range_Low, Normal_Range_High | 1984 rows, 62 subjects |
| Vital_Signs.csv | Subject_ID, Visit_Name, Visit_Date, BP_Systolic, BP_Diastolic, Weight_kg, Heart_Rate | 258 rows, 62 subjects |
| Disposition.csv | Subject_ID, Status, Last_Visit_Date, Reason_Discontinuation, Study_Completion_Date | 62 rows |

---

## LAYER 1: RULE-BASED ENGINE

These are deterministic checks. Code them as explicit IF/THEN logic. No LLM needed.

---

### RULE SET 1: DATE VALIDATION RULES

**RULE-DT-001: Informed Consent Date must be on or before Screening Date**
```
FOR EACH subject IN Demographics:
    IF Informed_Consent_Date > Screening_Date:
        FLAG: "Informed Consent Date ({consent_date}) is after Screening Date ({screening_date}). 
               Consent must be obtained before any study procedures."
        SEVERITY: Critical
        FORMS: Demographics
```

**RULE-DT-002: AE Start Date must be on or after Informed Consent Date**
```
FOR EACH ae IN Adverse_Events:
    consent_date = Demographics[ae.Subject_ID].Informed_Consent_Date
    IF ae.Start_Date < consent_date:
        FLAG: "AE '{ae.AE_Term}' Start Date ({ae.Start_Date}) is before Informed Consent Date ({consent_date}). 
               AEs cannot be reported before consent."
        SEVERITY: Critical
        FORMS: Adverse_Events + Demographics
```

**RULE-DT-003: Concomitant Medication Start Date should not be before Informed Consent Date (for new medications)**
```
FOR EACH med IN Concomitant_Meds:
    consent_date = Demographics[med.Subject_ID].Informed_Consent_Date
    screening_date = Demographics[med.Subject_ID].Screening_Date
    IF med.Start_Date < consent_date AND med.Ongoing_YN == "No":
        # New (non-chronic) medication started before consent
        FLAG: "Medication '{med.Med_Name}' Start Date ({med.Start_Date}) is before Informed Consent Date ({consent_date}). 
               Please verify if this is a pre-existing medication."
        SEVERITY: Major
        FORMS: Concomitant_Meds + Demographics
```

**RULE-DT-004: Medical History Start Date must be before Screening Date**
```
FOR EACH mh IN Medical_History:
    screening_date = Demographics[mh.Subject_ID].Screening_Date
    IF mh.MH_Start_Date > screening_date:
        FLAG: "Medical History '{mh.MH_Term}' Start Date ({mh.MH_Start_Date}) is after Screening Date ({screening_date}). 
               Medical history events must predate screening."
        SEVERITY: Critical
        FORMS: Medical_History + Demographics
```

---

### RULE SET 2: DEMOGRAPHICS RULES

**RULE-DM-001: Subject Age must be within inclusion criteria (18-75 years)**
```
FOR EACH subject IN Demographics:
    age_at_screening = (Screening_Date - DOB) in years
    IF age_at_screening < 18 OR age_at_screening > 75:
        FLAG: "Subject age at screening is {age} years. Outside inclusion criteria (18-75 years). 
               Potential protocol violation."
        SEVERITY: Critical
        FORMS: Demographics
```

---

### RULE SET 3: ADVERSE EVENT RULES

**RULE-AE-001: Seriousness Criteria - Hospitalization must be Serious**
```
FOR EACH ae IN Adverse_Events:
    hospitalization_keywords = ["hospitalization", "hospitalisation", "hospital admission", 
                                "admitted to hospital", "inpatient", "emergency room", "ER visit"]
    IF any keyword IN ae.AE_Verbatim.lower() AND ae.Seriousness == "No":
        FLAG: "AE Verbatim mentions hospitalization but Seriousness='No'. 
               Per ICH E2A, hospitalization meets serious criteria. Seriousness should be 'Yes'."
        SEVERITY: Critical
        FORMS: Adverse_Events
```

**RULE-AE-002: Fatal Outcome must be Serious**
```
FOR EACH ae IN Adverse_Events:
    IF ae.Outcome == "Fatal" AND ae.Seriousness == "No":
        FLAG: "AE '{ae.AE_Term}' has Outcome='Fatal' but Seriousness='No'. 
               Death is always a serious criterion per ICH E2A."
        SEVERITY: Critical
        FORMS: Adverse_Events
```

**RULE-AE-003: Severe AE must have Action Taken**
```
FOR EACH ae IN Adverse_Events:
    IF ae.Severity == "Severe" AND ae.Action_Taken == "None":
        FLAG: "AE '{ae.AE_Term}' is Severe but Action Taken='None'. 
               Severe AEs typically require intervention. Please verify Action Taken."
        SEVERITY: Major
        FORMS: Adverse_Events
```

---

### RULE SET 4: DISPOSITION RULES

**RULE-DS-001: Fatal AE Outcome must match Disposition**
```
FOR EACH ae IN Adverse_Events:
    IF ae.Outcome == "Fatal":
        disposition = Disposition[ae.Subject_ID]
        IF disposition.Status == "Completed":
            FLAG: "AE Outcome='Fatal' for '{ae.AE_Term}' but Disposition Status='Completed'. 
                   Subject with fatal AE cannot have completed the study."
            SEVERITY: Critical
            FORMS: Adverse_Events + Disposition
        IF disposition.Reason_Discontinuation != "Death":
            FLAG: "AE Outcome='Fatal' for '{ae.AE_Term}' but Disposition Reason is '{disposition.Reason_Discontinuation}', not 'Death'. 
                   Please reconcile."
            SEVERITY: Critical
            FORMS: Adverse_Events + Disposition
```

**RULE-DS-002: Discontinued subjects must have Reason**
```
FOR EACH subject IN Disposition:
    IF subject.Status == "Discontinued" AND subject.Reason_Discontinuation == "":
        FLAG: "Subject discontinued but Reason for Discontinuation is blank. 
               Reason is mandatory for all discontinued subjects."
        SEVERITY: Major
        FORMS: Disposition
```

**RULE-DS-003: Completed subjects must have reasonable study duration**
```
STUDY_DURATION_WEEKS = 16
FOR EACH subject IN Disposition:
    IF subject.Status == "Completed":
        screening_date = Demographics[subject.Subject_ID].Screening_Date
        expected_completion = screening_date + (STUDY_DURATION_WEEKS * 7 days)
        actual_duration = subject.Last_Visit_Date - screening_date
        IF actual_duration < (STUDY_DURATION_WEEKS * 7 * 0.5):  # Less than 50% of study duration
            FLAG: "Subject marked 'Completed' but last visit was only {actual_duration} days after screening. 
                   Expected study duration is {STUDY_DURATION_WEEKS} weeks. Please verify completion status."
            SEVERITY: Major
            FORMS: Disposition + Demographics
```

---

### RULE SET 5: LAB DATA RULES

**RULE-LAB-001: Physically impossible lab values**
```
impossible_ranges = {
    "Hemoglobin": (2.0, 25.0),      # g/dL
    "ALT": (0, 10000),               # U/L
    "AST": (0, 10000),               # U/L
    "Creatinine": (0, 30),           # mg/dL
    "WBC": (0, 100),                 # 10^3/uL
    "Platelets": (0, 2000),          # 10^3/uL
    "Total Bilirubin": (0, 50),      # mg/dL
    "Albumin": (0, 10),              # g/dL
}

FOR EACH lab IN Lab_Data:
    min_val, max_val = impossible_ranges[lab.Lab_Test]
    IF lab.Result < min_val OR lab.Result > max_val:
        FLAG: "{lab.Lab_Test} = {lab.Result} {lab.Unit} at {lab.Visit_Name}. 
               Value is outside physically possible range. Likely data entry error."
        SEVERITY: Critical
        FORMS: Lab_Data
```

**RULE-LAB-002: Lab values trending significantly (>3x ULN across consecutive visits) without corresponding AE**
```
FOR EACH subject IN unique(Lab_Data.Subject_ID):
    FOR EACH test IN ["ALT", "AST"]:
        values = get_values_by_visit_order(subject, test)
        FOR i in range(1, len(values)):
            IF values[i].Result > (values[i].Normal_Range_High * 3):
                # Check if AE exists for this subject with hepatic/liver terms
                ae_exists = check_ae_exists(subject, ["hepatotoxicity", "liver", "hepatic", 
                                                       "ALT", "AST", "transaminase", "enzyme"])
                IF NOT ae_exists:
                    FLAG: "{test} is {values[i].Result} U/L ({values[i].Result/values[i].Normal_Range_High:.1f}x ULN) 
                           at {values[i].Visit_Name}. Trending upward from {values[0].Result} at Screening. 
                           No corresponding AE reported. Potential missed hepatotoxicity."
                    SEVERITY: Critical
                    FORMS: Lab_Data + Adverse_Events
```

**RULE-LAB-003: Hemoglobin dropping significantly without corresponding AE**
```
FOR EACH subject IN unique(Lab_Data.Subject_ID):
    hgb_values = get_values_by_visit_order(subject, "Hemoglobin")
    IF len(hgb_values) >= 3:
        first_value = hgb_values[0].Result
        last_value = hgb_values[-1].Result
        drop = first_value - last_value
        IF drop > 3.0 AND last_value < hgb_values[-1].Normal_Range_Low:
            ae_exists = check_ae_exists(subject, ["anemia", "anaemia", "hemoglobin", "haemoglobin", "blood loss"])
            IF NOT ae_exists:
                FLAG: "Hemoglobin dropped from {first_value} to {last_value} g/dL across {len(hgb_values)} visits. 
                       Currently below normal range. No corresponding AE reported. Potential missed anemia."
                SEVERITY: Critical
                FORMS: Lab_Data + Adverse_Events
```

---

### RULE SET 6: VITAL SIGNS RULES

**RULE-VS-001: Significant weight change without corresponding AE**
```
FOR EACH subject IN unique(Vital_Signs.Subject_ID):
    weights = get_values_by_visit_order(subject, "Weight_kg")
    FOR i in range(1, len(weights)):
        change = abs(weights[i] - weights[i-1])
        IF change > 7.0:  # >7kg between consecutive visits
            ae_exists = check_any_ae_exists(subject)  # simplified check
            IF NOT ae_exists OR no_weight_related_ae(subject):
                FLAG: "Weight changed by {change:.1f}kg between {visits[i-1]} and {visits[i]} 
                       ({weights[i-1]}kg → {weights[i]}kg). No corresponding AE reported."
                SEVERITY: Major
                FORMS: Vital_Signs + Adverse_Events
```

**RULE-VS-002: Consistently elevated BP without AE or medication**
```
FOR EACH subject IN unique(Vital_Signs.Subject_ID):
    bp_readings = get_all_bp(subject)
    high_count = count(bp WHERE BP_Systolic > 160 OR BP_Diastolic > 100)
    IF high_count >= 3:
        ae_exists = check_ae_exists(subject, ["hypertension", "blood pressure", "BP elevated"])
        med_exists = check_med_exists(subject, ["amlodipine", "losartan", "lisinopril", 
                                                 "telmisartan", "enalapril", "valsartan", 
                                                 "metoprolol", "atenolol"])
        IF NOT ae_exists AND NOT med_exists:
            FLAG: "BP consistently elevated (>160/100) across {high_count} visits. 
                   No hypertension AE reported and no antihypertensive medication documented."
            SEVERITY: Critical
            FORMS: Vital_Signs + Adverse_Events + Concomitant_Meds
```

---

### RULE SET 7: CROSS-FORM MEDICATION RULES

**RULE-CM-001: Ongoing Medical History condition should have corresponding medication**
```
condition_med_keywords = {
    "Type 2 Diabetes Mellitus": ["metformin", "glimepiride", "sitagliptin", "insulin", 
                                  "gliclazide", "pioglitazone", "empagliflozin", "dapagliflozin"],
    "Hypertension": ["amlodipine", "losartan", "lisinopril", "telmisartan", "enalapril", 
                      "valsartan", "ramipril", "metoprolol", "atenolol", "nifedipine"],
    "Hypothyroidism": ["levothyroxine", "thyronorm", "eltroxin"],
    "Asthma": ["salbutamol", "montelukast", "budesonide", "fluticasone", "formoterol"],
    "Atrial Fibrillation": ["warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban"],
}

FOR EACH mh IN Medical_History:
    IF mh.Ongoing_YN == "Yes" AND mh.MH_Term IN condition_med_keywords:
        expected_meds = condition_med_keywords[mh.MH_Term]
        subject_meds = [m.Med_Name.lower() for m in Concomitant_Meds WHERE Subject_ID == mh.Subject_ID]
        IF NOT any(keyword IN med for keyword IN expected_meds for med IN subject_meds):
            FLAG: "Subject has ongoing '{mh.MH_Term}' in Medical History but no corresponding medication found. 
                   Expected medications like: {expected_meds[:3]}. Please verify treatment status."
            SEVERITY: Major
            FORMS: Medical_History + Concomitant_Meds
```

**NOTE:** This rule covers COMMON conditions only. The LLM Layer handles the remaining 90% of medication-condition matching that can't be hard-coded.

---

### RULE SET 8: EXCLUSION CRITERIA RULES

**RULE-EX-001: Check for exclusion criterion violations in Medical History**
```
exclusion_terms = ["hepatic impairment", "liver failure", "cirrhosis", 
                    "hepatic encephalopathy", "severe renal impairment",
                    "dialysis", "active malignancy", "HIV positive"]

FOR EACH mh IN Medical_History:
    IF any(term IN mh.MH_Term.lower() for term IN exclusion_terms):
        FLAG: "Subject has '{mh.MH_Term}' in Medical History which is a potential exclusion criterion violation. 
               Please verify eligibility per protocol Section 4.2."
        SEVERITY: Critical
        FORMS: Medical_History
```

---

## LAYER 2: LLM ENGINE

These checks require clinical knowledge, natural language understanding, or reasoning that cannot be hard-coded. Send data to the LLM API for each subject.

---

### LLM PROMPT 1: Complete Subject Profile Review

**When to call:** After Rule Engine completes. Run for EVERY subject.

**Prompt template:**
```
You are a senior clinical data reviewer performing a cross-form data review 
for a Phase III clinical trial (OBERON-301).

Review the following subject profile and identify ANY clinical inconsistencies 
across forms that a rule-based system might miss.

SUBJECT: {subject_id}

DEMOGRAPHICS:
- DOB: {dob}, Sex: {sex}, Age at Screening: {age}
- Screening Date: {screening_date}
- Informed Consent Date: {consent_date}

MEDICAL HISTORY:
{list all MH entries with term, start date, ongoing status}

CONCOMITANT MEDICATIONS:
{list all meds with name, indication, start date, ongoing status}

ADVERSE EVENTS:
{list all AEs with term, verbatim, severity, seriousness, causality, dates, outcome}

LAB DATA (summary - flag abnormals):
{for each lab test, show visit-over-visit trend, flag any out-of-range values}

VITAL SIGNS (summary):
{show visit-over-visit BP, weight, heart rate}

DISPOSITION:
- Status: {status}
- Last Visit: {last_visit_date}
- Reason: {reason}

INSTRUCTIONS:
1. Does every medication have a matching medical condition or adverse event?
2. Does every ongoing medical condition have corresponding treatment?
3. Are there lab trends that should have triggered an AE report?
4. Are there vital sign changes that need AE documentation?
5. Is the AE severity/seriousness classification clinically appropriate given the verbatim?
6. Does the disposition status align with adverse event outcomes?
7. Are there any temporal inconsistencies (dates that don't make clinical sense)?
8. Is the causality assessment appropriate given medication timing?

Respond in JSON format:
{
  "subject_id": "...",
  "issues_found": [
    {
      "issue_id": "LLM-001",
      "forms_involved": ["Medical_History", "Concomitant_Meds"],
      "description": "...",
      "severity": "Critical|Major|Minor",
      "suggested_query": "..."
    }
  ],
  "no_issues_confirmed": ["list of checks that passed"]
}
```

---

### LLM PROMPT 2: Medication-Condition Matching (Bulk)

**When to call:** For subjects where Rule CM-001 didn't flag anything but you want deeper analysis.

**Prompt template:**
```
You are a clinical pharmacologist reviewing medication-condition alignment.

For each medication below, verify it has a clinically appropriate indication 
in either the Medical History or Adverse Events.

SUBJECT: {subject_id}

MEDICAL HISTORY:
{all MH terms}

MEDICATIONS:
{all medications with indication}

ADVERSE EVENTS:
{all AE terms}

For each medication, respond:
- MATCH: medication has clear clinical justification
- MISMATCH: medication has no corresponding condition — specify what condition 
  should exist
- REVIEW: indication exists but the specific drug choice is unusual — specify concern

Respond in JSON format only.
```

---

### LLM PROMPT 3: AE Causality Review

**When to call:** For subjects where a new medication was started within 7 days of an AE.

**Prompt template:**
```
You are reviewing adverse event causality assessments.

SUBJECT: {subject_id}

TEMPORAL RELATIONSHIP:
- Medication: {med_name} started on {med_start_date}
- Adverse Event: {ae_term} ({ae_verbatim}) started on {ae_start_date}
- Days between medication start and AE onset: {days_diff}
- Current Causality Assessment: {causality}

QUESTION:
Given the temporal relationship between the medication and the adverse event, 
is the current causality assessment of "{causality}" appropriate?

Consider:
1. Is {med_name} known to cause {ae_term}?
2. Is the temporal relationship consistent with a drug-related event?
3. Are there other explanations in the subject's medical history?

Subject Medical History: {mh_terms}

Respond with:
- APPROPRIATE: causality assessment is reasonable
- QUESTIONABLE: causality should be re-evaluated (explain why)
- INCORRECT: causality is clearly wrong (explain why)

Include a suggested query if causality should be reviewed.
Respond in JSON format only.
```

---

### LLM PROMPT 4: Query Text Generation

**When to call:** For EVERY flagged issue (from both Rule Engine and LLM analysis).

**Prompt template:**
```
You are a clinical data query writer. Generate a professional, audit-ready 
clinical data query for the following issue.

STUDY: OBERON-301 (Phase III)
SUBJECT: {subject_id}
SITE: {site_id}

ISSUE DETECTED:
{issue_description}

DATA INVOLVED:
{relevant_data_points}

Write a clinical data query in standard format:
1. State the observation clearly
2. Reference specific data values and dates
3. Ask the site to verify/clarify
4. Request specific corrective information if needed

Keep the tone professional and factual. Do not use accusatory language.
Maximum 150 words.
```

---

## OUTPUT SPECIFICATION

### Results Dashboard (Frontend)

**Page 1: Upload Screen**
- Upload area for 7 CSV files
- "Run Analysis" button
- Processing indicator

**Page 2: Summary Dashboard**
```
┌─────────────────────────────────────────────┐
│  OBERON-301 Cross-Form Review Results       │
├─────────────────────────────────────────────┤
│  Total Subjects Analyzed: 62                │
│  Total Issues Found: XX                     │
│                                             │
│  🔴 Critical: XX    🟡 Major: XX    🟢 Minor: XX │
│                                             │
│  Detection Method:                          │
│    Rule-Based: XX flags                     │
│    AI-Detected: XX flags                    │
│                                             │
│  Estimated Time Saved: XX hours             │
│  (vs manual review of XX subjects)          │
└─────────────────────────────────────────────┘
```

**Page 3: Detailed Flags Table**

| Subject | Forms Involved | Issue | Severity | Source | Suggested Query | Confidence |
|---------|---------------|-------|----------|--------|----------------|------------|
| OB1132 | Lab + AE | ALT trending 3x ULN, no AE | Critical | Rule | [query text] | High |
| OB1129 | CM + MH | Metformin without diabetes | Major | AI | [query text] | High |

- Sortable by severity, subject, form
- Expandable rows showing full details
- Export to CSV button

**Page 4: Subject Detail View (click on any subject)**
- Full profile across all forms
- Highlighted flagged fields
- Timeline view of events

---

## PROCESSING FLOW (Step by Step)

```
STEP 1: Parse all 7 CSVs into data structures (dicts keyed by Subject_ID)

STEP 2: Build subject profiles
    For each Subject_ID:
        profile = {
            demographics: {...},
            medical_history: [...],
            concomitant_meds: [...],
            adverse_events: [...],
            lab_data: [...],
            vital_signs: [...],
            disposition: {...}
        }

STEP 3: Run Rule Engine (all rules in this document)
    For each rule:
        For each applicable subject:
            Check condition → if failed, add to flags[]

STEP 4: Run LLM Engine
    For each subject:
        Build prompt from profile (LLM Prompt 1)
        Call LLM API
        Parse JSON response
        Add new issues to flags[]
        
    For flagged med-condition mismatches:
        Run LLM Prompt 2 for deeper analysis
        
    For temporal med-AE relationships:
        Run LLM Prompt 3 for causality review

STEP 5: Generate Queries
    For each flag:
        Call LLM Prompt 4
        Attach generated query text to flag

STEP 6: Calculate Metrics
    Total flags by severity
    Total flags by detection method (rule vs AI)
    Estimated time saved = (subjects * avg_manual_review_minutes) - tool_processing_time

STEP 7: Render Dashboard
    Display summary + detailed table + export option
```

---

## API CONFIGURATION

```python
# Claude API
import anthropic

client = anthropic.Anthropic(api_key="YOUR_KEY")

def call_llm(prompt, system_prompt="You are a senior clinical data reviewer."):
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

---

## VALIDATION CHECKLIST

The dataset contains 26 planted errors. After running the tool, check detection rate:

| # | Subject | Error | Expected Detection |
|---|---------|-------|-------------------|
| 1 | OB1136 | Age 16 — outside inclusion | Rule DM-001 |
| 2 | OB1170 | Consent after Screening | Rule DT-001 |
| 3 | OB1125 | T2DM in MH, no diabetes med | Rule CM-001 or LLM |
| 4 | OB1148 | HTN in MH, no antihypertensive | Rule CM-001 or LLM |
| 5 | OB1162 | Hepatic Impairment — exclusion | Rule EX-001 |
| 6 | OB1186 | MH Start after Screening | Rule DT-004 |
| 7 | OB1129 | Metformin without diabetes in MH | LLM Prompt 2 |
| 8 | OB1157 | Sumatriptan + Headache same day, "Not Related" | LLM Prompt 3 |
| 9 | OB1172 | Amoxicillin Start before Consent | Rule DT-003 |
| 10 | OB1140 | Hospitalization but Seriousness=No | Rule AE-001 |
| 11 | OB1176 | Fatal MI but Disposition=Completed | Rule DS-001 |
| 12 | OB1166 | AE Start before Consent | Rule DT-002 |
| 13 | OB1153 | Severe AE, Action=None | Rule AE-003 |
| 14 | OB1193 | Fatal Outcome, Seriousness=No | Rule AE-002 |
| 15 | OB1193 | Disposition Reason=AE not Death | Rule DS-001 |
| 16 | OB1132 | ALT/AST trending 3x ULN, no AE | Rule LAB-002 |
| 17 | OB1160 | Hemoglobin dropping, no AE | Rule LAB-003 |
| 18 | OB1149 | Hemoglobin=45.2 impossible | Rule LAB-001 |
| 19 | OB1134 | +14kg weight gain, no AE | Rule VS-001 |
| 20 | OB1122 | BP >160/100 all visits, no AE, no med | Rule VS-002 |
| 21 | OB1155 | Completed but only 18 days in study | Rule DS-003 |
| 22 | OB1169 | Discontinued, Reason blank | Rule DS-002 |
| 23-26 | Various | Cross-form duplicates of above | LLM Prompt 1 |

**Target: 85%+ detection rate (22+ out of 26)**

---

## TIMELINE

- Day 1: Review this document, set up project, parse CSVs
- Day 2: Build Rule Engine (all 8 rule sets)
- Day 3: Integrate LLM Engine (4 prompts)
- Day 4: Build Frontend Dashboard
- Day 5: Testing + validation against checklist
- Day 6: Polish + demo prep
- Day 7: Buffer / final fixes

---

## NOTES FOR CO-FOUNDER

1. **Start with Rule Engine only.** Get all deterministic rules working first. LLM is Layer 2.
2. **LLM calls are expensive.** Don't call LLM for every row. Call per subject (62 calls total, not 2000+).
3. **Parse LLM JSON carefully.** LLMs sometimes return malformed JSON. Wrap in try/catch, retry if needed.
4. **The demo matters more than perfection.** If a rule is hard to implement, skip it. Focus on the most impactful flags.
5. **Frontend can be ugly.** A clean table with sorting is enough. No need for fancy charts.
6. **Export to CSV is critical.** Hiring managers want to see "I can export this to Excel and share with my team."
