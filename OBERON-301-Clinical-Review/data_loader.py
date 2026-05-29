import io
import pandas as pd
import numpy as np
from models import SubjectProfile

DATE_COLUMNS = {
    "demographics": ["DOB", "Screening_Date", "Informed_Consent_Date"],
    "medical_history": ["MH_Start_Date", "MH_End_Date"],
    "concomitant_meds": ["Start_Date", "End_Date"],
    "adverse_events": ["Start_Date", "End_Date"],
    "lab_data": ["Visit_Date"],
    "vital_signs": ["Visit_Date"],
    "disposition": ["Last_Visit_Date", "Study_Completion_Date"],
}

FILE_MAP = {
    "demographics": "Demographics.csv",
    "medical_history": "Medical_History.csv",
    "concomitant_meds": "Concomitant_Meds.csv",
    "adverse_events": "Adverse_Events.csv",
    "lab_data": "Lab_Data.csv",
    "vital_signs": "Vital_Signs.csv",
    "disposition": "Disposition.csv",
}


def parse_dates(df: pd.DataFrame, date_columns: list[str]) -> pd.DataFrame:
    for col in date_columns:
        if col in df.columns:
            parsed = pd.to_datetime(df[col], format="mixed", errors="coerce")
            df.loc[:, col] = parsed.dt.strftime("%m/%d/%Y").where(parsed.notna(), None)
    return df


def load_all_csvs(data_dir: str) -> dict[str, pd.DataFrame]:
    import os
    dataframes = {}
    for key, filename in FILE_MAP.items():
        path = os.path.join(data_dir, filename)
        df = pd.read_csv(path)
        df = parse_dates(df, DATE_COLUMNS.get(key, []))
        dataframes[key] = df
    return dataframes


def load_csvs_from_uploads(files: dict[str, bytes]) -> dict[str, pd.DataFrame]:
    filename_to_key = {v: k for k, v in FILE_MAP.items()}
    dataframes = {}
    for filename, content in files.items():
        key = filename_to_key.get(filename)
        if key is None:
            for fk, fv in FILE_MAP.items():
                if fv.lower() == filename.lower():
                    key = fk
                    break
        if key is None:
            continue
        df = pd.read_csv(io.BytesIO(content))
        df = parse_dates(df, DATE_COLUMNS.get(key, []))
        dataframes[key] = df
    return dataframes


def _row_to_dict(row) -> dict:
    d = {}
    for k, v in row.items():
        if v is pd.NaT or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            d[k] = None
        elif isinstance(v, pd.Timestamp):
            d[k] = v.strftime("%m/%d/%Y")
        elif isinstance(v, (np.integer,)):
            d[k] = int(v)
        elif isinstance(v, (np.floating,)):
            d[k] = float(v)
        else:
            d[k] = v
    return d


def build_subject_profiles(dataframes: dict[str, pd.DataFrame]) -> dict[str, SubjectProfile]:
    all_subject_ids = set()
    for df in dataframes.values():
        if "Subject_ID" in df.columns:
            all_subject_ids.update(df["Subject_ID"].dropna().unique())

    profiles = {}
    for sid in sorted(all_subject_ids):
        dem_df = dataframes.get("demographics")
        dem_rows = dem_df[dem_df["Subject_ID"] == sid] if dem_df is not None else pd.DataFrame()
        demographics = _row_to_dict(dem_rows.iloc[0]) if len(dem_rows) > 0 else {}

        disp_df = dataframes.get("disposition")
        disp_rows = disp_df[disp_df["Subject_ID"] == sid] if disp_df is not None else pd.DataFrame()
        disposition = _row_to_dict(disp_rows.iloc[0]) if len(disp_rows) > 0 else {}

        def get_rows(table_key):
            df = dataframes.get(table_key)
            if df is None:
                return []
            rows = df[df["Subject_ID"] == sid]
            return [_row_to_dict(r) for _, r in rows.iterrows()]

        profiles[sid] = SubjectProfile(
            subject_id=sid,
            demographics=demographics,
            medical_history=get_rows("medical_history"),
            concomitant_meds=get_rows("concomitant_meds"),
            adverse_events=get_rows("adverse_events"),
            lab_data=get_rows("lab_data"),
            vital_signs=get_rows("vital_signs"),
            disposition=disposition,
        )

    return profiles
