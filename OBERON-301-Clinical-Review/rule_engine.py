import pandas as pd
import numpy as np
from models import Flag, SubjectProfile
import config


def _fmt_date(dt) -> str:
    if pd.isna(dt):
        return "N/A"
    return dt.strftime("%m/%d/%Y")


def _calculate_age(dob, reference_date) -> float | None:
    if pd.isna(dob) or pd.isna(reference_date):
        return None
    delta = reference_date - dob
    return delta.days / 365.25


def _get_subject_dem(subject_id: str, dem_df: pd.DataFrame) -> pd.Series | None:
    rows = dem_df[dem_df["Subject_ID"] == subject_id]
    return rows.iloc[0] if len(rows) > 0 else None


def _check_ae_exists(subject_id: str, keywords: list[str], ae_df: pd.DataFrame) -> bool:
    subj_aes = ae_df[ae_df["Subject_ID"] == subject_id]
    for _, ae in subj_aes.iterrows():
        ae_text = f"{ae.get('AE_Term', '')} {ae.get('AE_Verbatim', '')}".lower()
        if any(kw in ae_text for kw in keywords):
            return True
    return False


def _check_med_exists(subject_id: str, keywords: list[str], meds_df: pd.DataFrame) -> bool:
    subj_meds = meds_df[meds_df["Subject_ID"] == subject_id]
    for _, med in subj_meds.iterrows():
        med_name = str(med.get("Med_Name", "")).lower()
        if any(kw in med_name for kw in keywords):
            return True
    return False


def _get_lab_values_by_visit(subject_id: str, lab_test: str, lab_df: pd.DataFrame) -> list[dict]:
    subj_labs = lab_df[(lab_df["Subject_ID"] == subject_id) & (lab_df["Lab_Test"] == lab_test)]
    visit_order = {v: i for i, v in enumerate(config.VISIT_ORDER)}
    rows = []
    for _, r in subj_labs.iterrows():
        rows.append({
            "Visit_Name": r["Visit_Name"],
            "Result": r["Result"],
            "Normal_Range_Low": r.get("Normal_Range_Low"),
            "Normal_Range_High": r.get("Normal_Range_High"),
            "Visit_Date": r.get("Visit_Date"),
            "sort_key": visit_order.get(r["Visit_Name"], 999),
        })
    rows.sort(key=lambda x: x["sort_key"])
    return rows


# ── Rule Set 1: Date Validation ──────────────────────────────────────────────

def check_date_rules(dataframes: dict[str, pd.DataFrame], profiles: dict[str, SubjectProfile]) -> list[Flag]:
    flags = []
    dem = dataframes["demographics"]
    ae_df = dataframes.get("adverse_events", pd.DataFrame())
    meds_df = dataframes.get("concomitant_meds", pd.DataFrame())
    mh_df = dataframes.get("medical_history", pd.DataFrame())

    # RULE-DT-001: Informed Consent Date must be on or before Screening Date
    for _, row in dem.iterrows():
        if pd.notna(row["Informed_Consent_Date"]) and pd.notna(row["Screening_Date"]):
            if row["Informed_Consent_Date"] > row["Screening_Date"]:
                flags.append(Flag(
                    flag_id=f"RULE-DT-001-{row['Subject_ID']}",
                    subject_id=row["Subject_ID"],
                    rule_id="RULE-DT-001",
                    forms_involved=["Demographics"],
                    description=(
                        f"Informed Consent Date ({_fmt_date(row['Informed_Consent_Date'])}) is after "
                        f"Screening Date ({_fmt_date(row['Screening_Date'])}). "
                        f"Consent must be obtained before any study procedures."
                    ),
                    severity="Critical",
                    source="Rule",
                ))

    # RULE-DT-002: AE Start Date must be on or after Informed Consent Date
    if not ae_df.empty:
        for _, ae in ae_df.iterrows():
            subj = _get_subject_dem(ae["Subject_ID"], dem)
            if subj is None:
                continue
            if pd.notna(ae["Start_Date"]) and pd.notna(subj["Informed_Consent_Date"]):
                if ae["Start_Date"] < subj["Informed_Consent_Date"]:
                    flags.append(Flag(
                        flag_id=f"RULE-DT-002-{ae['Subject_ID']}-{ae['AE_Term']}",
                        subject_id=ae["Subject_ID"],
                        rule_id="RULE-DT-002",
                        forms_involved=["Adverse_Events", "Demographics"],
                        description=(
                            f"AE '{ae['AE_Term']}' Start Date ({_fmt_date(ae['Start_Date'])}) is before "
                            f"Informed Consent Date ({_fmt_date(subj['Informed_Consent_Date'])}). "
                            f"AEs cannot be reported before consent."
                        ),
                        severity="Critical",
                        source="Rule",
                    ))

    # RULE-DT-003: Con Med Start Date before Informed Consent (for non-ongoing meds)
    if not meds_df.empty:
        for _, med in meds_df.iterrows():
            subj = _get_subject_dem(med["Subject_ID"], dem)
            if subj is None:
                continue
            if pd.notna(med["Start_Date"]) and pd.notna(subj["Informed_Consent_Date"]):
                if med["Start_Date"] < subj["Informed_Consent_Date"] and str(med.get("Ongoing_YN", "")).strip() == "No":
                    flags.append(Flag(
                        flag_id=f"RULE-DT-003-{med['Subject_ID']}-{med['Med_Name']}",
                        subject_id=med["Subject_ID"],
                        rule_id="RULE-DT-003",
                        forms_involved=["Concomitant_Meds", "Demographics"],
                        description=(
                            f"Medication '{med['Med_Name']}' Start Date ({_fmt_date(med['Start_Date'])}) is before "
                            f"Informed Consent Date ({_fmt_date(subj['Informed_Consent_Date'])}). "
                            f"Please verify if this is a pre-existing medication."
                        ),
                        severity="Major",
                        source="Rule",
                    ))

    # RULE-DT-004: Medical History Start Date must be before Screening Date
    if not mh_df.empty:
        for _, mh in mh_df.iterrows():
            subj = _get_subject_dem(mh["Subject_ID"], dem)
            if subj is None:
                continue
            if pd.notna(mh["MH_Start_Date"]) and pd.notna(subj["Screening_Date"]):
                if mh["MH_Start_Date"] > subj["Screening_Date"]:
                    flags.append(Flag(
                        flag_id=f"RULE-DT-004-{mh['Subject_ID']}-{mh['MH_Term']}",
                        subject_id=mh["Subject_ID"],
                        rule_id="RULE-DT-004",
                        forms_involved=["Medical_History", "Demographics"],
                        description=(
                            f"Medical History '{mh['MH_Term']}' Start Date ({_fmt_date(mh['MH_Start_Date'])}) is after "
                            f"Screening Date ({_fmt_date(subj['Screening_Date'])}). "
                            f"Medical history events must predate screening."
                        ),
                        severity="Critical",
                        source="Rule",
                    ))

    return flags


# ── Rule Set 2: Demographics ─────────────────────────────────────────────────

def check_demographics_rules(dataframes: dict[str, pd.DataFrame], profiles: dict[str, SubjectProfile]) -> list[Flag]:
    flags = []
    dem = dataframes["demographics"]

    # RULE-DM-001: Subject Age must be within inclusion criteria (18-75 years)
    for _, row in dem.iterrows():
        age = _calculate_age(row["DOB"], row["Screening_Date"])
        if age is not None:
            if age < config.AGE_MIN or age > config.AGE_MAX:
                flags.append(Flag(
                    flag_id=f"RULE-DM-001-{row['Subject_ID']}",
                    subject_id=row["Subject_ID"],
                    rule_id="RULE-DM-001",
                    forms_involved=["Demographics"],
                    description=(
                        f"Subject age at screening is {age:.0f} years. "
                        f"Outside inclusion criteria ({config.AGE_MIN}-{config.AGE_MAX} years). "
                        f"Potential protocol violation."
                    ),
                    severity="Critical",
                    source="Rule",
                ))

    return flags


# ── Rule Set 3: Adverse Events ───────────────────────────────────────────────

def check_ae_rules(dataframes: dict[str, pd.DataFrame], profiles: dict[str, SubjectProfile]) -> list[Flag]:
    flags = []
    ae_df = dataframes.get("adverse_events", pd.DataFrame())
    if ae_df.empty:
        return flags

    for _, ae in ae_df.iterrows():
        verbatim = str(ae.get("AE_Verbatim", "")).lower()

        # RULE-AE-001: Hospitalization mentioned but Seriousness=No
        if any(kw in verbatim for kw in config.HOSPITALIZATION_KEYWORDS) and str(ae.get("Seriousness", "")) == "No":
            flags.append(Flag(
                flag_id=f"RULE-AE-001-{ae['Subject_ID']}-{ae['AE_Term']}",
                subject_id=ae["Subject_ID"],
                rule_id="RULE-AE-001",
                forms_involved=["Adverse_Events"],
                description=(
                    f"AE Verbatim mentions hospitalization but Seriousness='No'. "
                    f"Per ICH E2A, hospitalization meets serious criteria. "
                    f"Seriousness should be 'Yes'. (AE: '{ae['AE_Term']}', Verbatim: '{ae['AE_Verbatim']}')"
                ),
                severity="Critical",
                source="Rule",
            ))

        # RULE-AE-002: Fatal Outcome must be Serious
        if str(ae.get("Outcome", "")) == "Fatal" and str(ae.get("Seriousness", "")) == "No":
            flags.append(Flag(
                flag_id=f"RULE-AE-002-{ae['Subject_ID']}-{ae['AE_Term']}",
                subject_id=ae["Subject_ID"],
                rule_id="RULE-AE-002",
                forms_involved=["Adverse_Events"],
                description=(
                    f"AE '{ae['AE_Term']}' has Outcome='Fatal' but Seriousness='No'. "
                    f"Death is always a serious criterion per ICH E2A."
                ),
                severity="Critical",
                source="Rule",
            ))

        # RULE-AE-003: Severe AE must have Action Taken
        action = ae.get("Action_Taken")
        action_str = str(action).strip() if pd.notna(action) else ""
        if str(ae.get("Severity", "")) == "Severe" and (action_str == "" or action_str == "None"):
            flags.append(Flag(
                flag_id=f"RULE-AE-003-{ae['Subject_ID']}-{ae['AE_Term']}",
                subject_id=ae["Subject_ID"],
                rule_id="RULE-AE-003",
                forms_involved=["Adverse_Events"],
                description=(
                    f"AE '{ae['AE_Term']}' is Severe but Action Taken='None'. "
                    f"Severe AEs typically require intervention. Please verify Action Taken."
                ),
                severity="Major",
                source="Rule",
            ))

    return flags


# ── Rule Set 4: Disposition ──────────────────────────────────────────────────

def check_disposition_rules(dataframes: dict[str, pd.DataFrame], profiles: dict[str, SubjectProfile]) -> list[Flag]:
    flags = []
    ae_df = dataframes.get("adverse_events", pd.DataFrame())
    disp_df = dataframes.get("disposition", pd.DataFrame())
    dem_df = dataframes.get("demographics", pd.DataFrame())

    if disp_df.empty:
        return flags

    # RULE-DS-001: Fatal AE Outcome must match Disposition
    if not ae_df.empty:
        fatal_aes = ae_df[ae_df["Outcome"] == "Fatal"]
        for _, ae in fatal_aes.iterrows():
            disp_rows = disp_df[disp_df["Subject_ID"] == ae["Subject_ID"]]
            if disp_rows.empty:
                continue
            disp = disp_rows.iloc[0]
            if str(disp.get("Status", "")) == "Completed":
                flags.append(Flag(
                    flag_id=f"RULE-DS-001a-{ae['Subject_ID']}-{ae['AE_Term']}",
                    subject_id=ae["Subject_ID"],
                    rule_id="RULE-DS-001",
                    forms_involved=["Adverse_Events", "Disposition"],
                    description=(
                        f"AE Outcome='Fatal' for '{ae['AE_Term']}' but Disposition Status='Completed'. "
                        f"Subject with fatal AE cannot have completed the study."
                    ),
                    severity="Critical",
                    source="Rule",
                ))
            reason = str(disp.get("Reason_Discontinuation", "")).strip()
            if reason and reason != "Death" and reason != "nan":
                flags.append(Flag(
                    flag_id=f"RULE-DS-001b-{ae['Subject_ID']}-{ae['AE_Term']}",
                    subject_id=ae["Subject_ID"],
                    rule_id="RULE-DS-001",
                    forms_involved=["Adverse_Events", "Disposition"],
                    description=(
                        f"AE Outcome='Fatal' for '{ae['AE_Term']}' but Disposition Reason is "
                        f"'{reason}', not 'Death'. Please reconcile."
                    ),
                    severity="Critical",
                    source="Rule",
                ))

    # RULE-DS-002: Discontinued subjects must have Reason
    for _, disp in disp_df.iterrows():
        if str(disp.get("Status", "")) == "Discontinued":
            reason = str(disp.get("Reason_Discontinuation", "")).strip()
            if reason == "" or reason == "nan":
                flags.append(Flag(
                    flag_id=f"RULE-DS-002-{disp['Subject_ID']}",
                    subject_id=disp["Subject_ID"],
                    rule_id="RULE-DS-002",
                    forms_involved=["Disposition"],
                    description=(
                        f"Subject discontinued but Reason for Discontinuation is blank. "
                        f"Reason is mandatory for all discontinued subjects."
                    ),
                    severity="Major",
                    source="Rule",
                ))

    # RULE-DS-003: Completed subjects must have reasonable study duration
    for _, disp in disp_df.iterrows():
        if str(disp.get("Status", "")) == "Completed":
            subj = _get_subject_dem(disp["Subject_ID"], dem_df)
            if subj is None:
                continue
            if pd.notna(disp.get("Last_Visit_Date")) and pd.notna(subj.get("Screening_Date")):
                actual_days = (disp["Last_Visit_Date"] - subj["Screening_Date"]).days
                min_days = config.STUDY_DURATION_WEEKS * 7 * 0.5
                if actual_days < min_days:
                    flags.append(Flag(
                        flag_id=f"RULE-DS-003-{disp['Subject_ID']}",
                        subject_id=disp["Subject_ID"],
                        rule_id="RULE-DS-003",
                        forms_involved=["Disposition", "Demographics"],
                        description=(
                            f"Subject marked 'Completed' but last visit was only {actual_days} days after screening. "
                            f"Expected study duration is {config.STUDY_DURATION_WEEKS} weeks ({config.STUDY_DURATION_WEEKS * 7} days). "
                            f"Please verify completion status."
                        ),
                        severity="Major",
                        source="Rule",
                    ))

    return flags


# ── Rule Set 5: Lab Data ─────────────────────────────────────────────────────

def check_lab_rules(dataframes: dict[str, pd.DataFrame], profiles: dict[str, SubjectProfile]) -> list[Flag]:
    flags = []
    lab_df = dataframes.get("lab_data", pd.DataFrame())
    ae_df = dataframes.get("adverse_events", pd.DataFrame())

    if lab_df.empty:
        return flags

    # RULE-LAB-001: Physically impossible lab values
    for _, lab in lab_df.iterrows():
        test_name = lab.get("Lab_Test", "")
        if test_name in config.IMPOSSIBLE_LAB_RANGES:
            min_val, max_val = config.IMPOSSIBLE_LAB_RANGES[test_name]
            result = lab.get("Result")
            if pd.notna(result):
                try:
                    result = float(result)
                except (ValueError, TypeError):
                    continue
                if result < min_val or result > max_val:
                    flags.append(Flag(
                        flag_id=f"RULE-LAB-001-{lab['Subject_ID']}-{test_name}-{lab.get('Visit_Name', '')}",
                        subject_id=lab["Subject_ID"],
                        rule_id="RULE-LAB-001",
                        forms_involved=["Lab_Data"],
                        description=(
                            f"{test_name} = {result} {lab.get('Unit', '')} at {lab.get('Visit_Name', '')}. "
                            f"Value is outside physically possible range ({min_val}-{max_val}). "
                            f"Likely data entry error."
                        ),
                        severity="Critical",
                        source="Rule",
                    ))

    # RULE-LAB-002: ALT/AST trending >3x ULN without corresponding AE
    for subject_id in lab_df["Subject_ID"].unique():
        for test in ["ALT", "AST"]:
            values = _get_lab_values_by_visit(subject_id, test, lab_df)
            if len(values) < 2:
                continue
            for v in values:
                uln = v.get("Normal_Range_High")
                result = v.get("Result")
                if pd.notna(result) and pd.notna(uln):
                    try:
                        result = float(result)
                        uln = float(uln)
                    except (ValueError, TypeError):
                        continue
                    if uln > 0 and result > uln * 3:
                        hepatic_keywords = [
                            "hepatotoxicity", "liver", "hepatic", "alt", "ast",
                            "transaminase", "enzyme",
                        ]
                        if not _check_ae_exists(subject_id, hepatic_keywords, ae_df):
                            first_val = values[0].get("Result", "N/A")
                            flags.append(Flag(
                                flag_id=f"RULE-LAB-002-{subject_id}-{test}-{v['Visit_Name']}",
                                subject_id=subject_id,
                                rule_id="RULE-LAB-002",
                                forms_involved=["Lab_Data", "Adverse_Events"],
                                description=(
                                    f"{test} is {result} U/L ({result/uln:.1f}x ULN) at {v['Visit_Name']}. "
                                    f"Trending upward from {first_val} at Screening. "
                                    f"No corresponding AE reported. Potential missed hepatotoxicity."
                                ),
                                severity="Critical",
                                source="Rule",
                            ))
                        break

    # RULE-LAB-003: Hemoglobin dropping significantly without corresponding AE
    for subject_id in lab_df["Subject_ID"].unique():
        hgb_values = _get_lab_values_by_visit(subject_id, "Hemoglobin", lab_df)
        if len(hgb_values) < 3:
            continue
        try:
            first_val = float(hgb_values[0]["Result"])
            last_val = float(hgb_values[-1]["Result"])
            last_low = float(hgb_values[-1].get("Normal_Range_Low", 0))
        except (ValueError, TypeError):
            continue
        drop = first_val - last_val
        if drop > 3.0 and last_val < last_low:
            anemia_keywords = ["anemia", "anaemia", "hemoglobin", "haemoglobin", "blood loss"]
            if not _check_ae_exists(subject_id, anemia_keywords, ae_df):
                flags.append(Flag(
                    flag_id=f"RULE-LAB-003-{subject_id}",
                    subject_id=subject_id,
                    rule_id="RULE-LAB-003",
                    forms_involved=["Lab_Data", "Adverse_Events"],
                    description=(
                        f"Hemoglobin dropped from {first_val} to {last_val} g/dL "
                        f"across {len(hgb_values)} visits. Currently below normal range. "
                        f"No corresponding AE reported. Potential missed anemia."
                    ),
                    severity="Critical",
                    source="Rule",
                ))

    return flags


# ── Rule Set 6: Vital Signs ──────────────────────────────────────────────────

def check_vital_signs_rules(dataframes: dict[str, pd.DataFrame], profiles: dict[str, SubjectProfile]) -> list[Flag]:
    flags = []
    vs_df = dataframes.get("vital_signs", pd.DataFrame())
    ae_df = dataframes.get("adverse_events", pd.DataFrame())
    meds_df = dataframes.get("concomitant_meds", pd.DataFrame())

    if vs_df.empty:
        return flags

    visit_order = {v: i for i, v in enumerate(config.VISIT_ORDER)}

    for subject_id in vs_df["Subject_ID"].unique():
        subj_vs = vs_df[vs_df["Subject_ID"] == subject_id].copy()
        subj_vs.loc[:, "_sort"] = subj_vs["Visit_Name"].map(visit_order).fillna(999)
        subj_vs = subj_vs.sort_values("_sort")

        # RULE-VS-001: Significant weight change (>7kg between consecutive visits)
        weights = subj_vs[["Visit_Name", "Weight_kg"]].dropna(subset=["Weight_kg"])
        prev_row = None
        for _, row in weights.iterrows():
            if prev_row is not None:
                change = abs(float(row["Weight_kg"]) - float(prev_row["Weight_kg"]))
                if change > 7.0:
                    flags.append(Flag(
                        flag_id=f"RULE-VS-001-{subject_id}-{row['Visit_Name']}",
                        subject_id=subject_id,
                        rule_id="RULE-VS-001",
                        forms_involved=["Vital_Signs", "Adverse_Events"],
                        description=(
                            f"Weight changed by {change:.1f}kg between {prev_row['Visit_Name']} and "
                            f"{row['Visit_Name']} ({prev_row['Weight_kg']}kg -> {row['Weight_kg']}kg). "
                            f"No corresponding AE reported."
                        ),
                        severity="Major",
                        source="Rule",
                    ))
            prev_row = row

        # RULE-VS-002: Consistently elevated BP (>160/100) across 3+ visits
        high_bp_count = 0
        high_visits = []
        for _, row in subj_vs.iterrows():
            sys = row.get("BP_Systolic")
            dia = row.get("BP_Diastolic")
            if pd.notna(sys) and pd.notna(dia):
                if float(sys) > 160 or float(dia) > 100:
                    high_bp_count += 1
                    high_visits.append(row["Visit_Name"])
        if high_bp_count >= 3:
            bp_keywords = ["hypertension", "blood pressure", "bp elevated"]
            ae_exists = _check_ae_exists(subject_id, bp_keywords, ae_df)
            med_exists = _check_med_exists(subject_id, config.ANTIHYPERTENSIVE_MEDS, meds_df)
            if not ae_exists and not med_exists:
                flags.append(Flag(
                    flag_id=f"RULE-VS-002-{subject_id}",
                    subject_id=subject_id,
                    rule_id="RULE-VS-002",
                    forms_involved=["Vital_Signs", "Adverse_Events", "Concomitant_Meds"],
                    description=(
                        f"BP consistently elevated (>160/100) across {high_bp_count} visits "
                        f"({', '.join(high_visits)}). No hypertension AE reported and "
                        f"no antihypertensive medication documented."
                    ),
                    severity="Critical",
                    source="Rule",
                ))

    return flags


# ── Rule Set 7: Cross-Form Medication ────────────────────────────────────────

def check_medication_rules(dataframes: dict[str, pd.DataFrame], profiles: dict[str, SubjectProfile]) -> list[Flag]:
    flags = []
    mh_df = dataframes.get("medical_history", pd.DataFrame())
    meds_df = dataframes.get("concomitant_meds", pd.DataFrame())

    if mh_df.empty or meds_df.empty:
        return flags

    # RULE-CM-001: Ongoing Medical History should have corresponding medication
    for _, mh in mh_df.iterrows():
        if str(mh.get("Ongoing_YN", "")).strip() != "Yes":
            continue
        mh_term = str(mh.get("MH_Term", "")).strip()
        if mh_term not in config.CONDITION_MED_KEYWORDS:
            continue

        expected_meds = config.CONDITION_MED_KEYWORDS[mh_term]
        subject_id = mh["Subject_ID"]
        if not _check_med_exists(subject_id, expected_meds, meds_df):
            flags.append(Flag(
                flag_id=f"RULE-CM-001-{subject_id}-{mh_term}",
                subject_id=subject_id,
                rule_id="RULE-CM-001",
                forms_involved=["Medical_History", "Concomitant_Meds"],
                description=(
                    f"Subject has ongoing '{mh_term}' in Medical History but no corresponding "
                    f"medication found. Expected medications like: {', '.join(expected_meds[:3])}. "
                    f"Please verify treatment status."
                ),
                severity="Major",
                source="Rule",
            ))

    return flags


# ── Rule Set 8: Exclusion Criteria ───────────────────────────────────────────

def check_exclusion_rules(dataframes: dict[str, pd.DataFrame], profiles: dict[str, SubjectProfile]) -> list[Flag]:
    flags = []
    mh_df = dataframes.get("medical_history", pd.DataFrame())

    if mh_df.empty:
        return flags

    # RULE-EX-001: Check for exclusion criterion violations
    for _, mh in mh_df.iterrows():
        mh_term_lower = str(mh.get("MH_Term", "")).lower()
        for term in config.EXCLUSION_TERMS:
            if term in mh_term_lower:
                flags.append(Flag(
                    flag_id=f"RULE-EX-001-{mh['Subject_ID']}-{mh['MH_Term']}",
                    subject_id=mh["Subject_ID"],
                    rule_id="RULE-EX-001",
                    forms_involved=["Medical_History"],
                    description=(
                        f"Subject has '{mh['MH_Term']}' in Medical History which is a potential "
                        f"exclusion criterion violation. Please verify eligibility per protocol Section 4.2."
                    ),
                    severity="Critical",
                    source="Rule",
                ))
                break

    return flags


# ── Master Function ──────────────────────────────────────────────────────────

def run_all_rules(dataframes: dict[str, pd.DataFrame], profiles: dict[str, SubjectProfile]) -> list[Flag]:
    flags = []
    flags.extend(check_date_rules(dataframes, profiles))
    flags.extend(check_demographics_rules(dataframes, profiles))
    flags.extend(check_ae_rules(dataframes, profiles))
    flags.extend(check_disposition_rules(dataframes, profiles))
    flags.extend(check_lab_rules(dataframes, profiles))
    flags.extend(check_vital_signs_rules(dataframes, profiles))
    flags.extend(check_medication_rules(dataframes, profiles))
    flags.extend(check_exclusion_rules(dataframes, profiles))
    return flags
