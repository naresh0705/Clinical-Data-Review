from pydantic import BaseModel


class Flag(BaseModel):
    flag_id: str
    subject_id: str
    rule_id: str
    forms_involved: list[str]
    description: str
    severity: str
    source: str
    confidence: str = "High"
    suggested_query: str | None = None
    details: dict | None = None


class SubjectProfile(BaseModel):
    subject_id: str
    demographics: dict
    medical_history: list[dict]
    concomitant_meds: list[dict]
    adverse_events: list[dict]
    lab_data: list[dict]
    vital_signs: list[dict]
    disposition: dict


class AnalysisResult(BaseModel):
    total_subjects: int
    total_flags: int
    critical_count: int
    major_count: int
    minor_count: int
    rule_flags: int
    ai_flags: int
    flags: list[Flag]
    processing_time_seconds: float
    estimated_hours_saved: float
    llm_provider: str | None = None
    llm_model: str | None = None
