import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "claude")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
LLM_MAX_TOKENS = 2000
LLM_TEMPERATURE = 0.1

STUDY_DURATION_WEEKS = 16
AGE_MIN = 18
AGE_MAX = 75

VISIT_ORDER = [
    "Screening",
    "Visit 1 (Week 4)",
    "Visit 2 (Week 8)",
    "Visit 3 (Week 12)",
    "Visit 4 (Week 16)",
]

IMPOSSIBLE_LAB_RANGES = {
    "Hemoglobin": (2.0, 25.0),
    "ALT": (0, 10000),
    "AST": (0, 10000),
    "Creatinine": (0, 30),
    "WBC": (0, 100),
    "Platelets": (0, 2000),
    "Total Bilirubin": (0, 50),
    "Albumin": (0, 10),
}

CONDITION_MED_KEYWORDS = {
    "Type 2 Diabetes Mellitus": [
        "metformin", "glimepiride", "sitagliptin", "insulin",
        "gliclazide", "pioglitazone", "empagliflozin", "dapagliflozin",
    ],
    "Hypertension": [
        "amlodipine", "losartan", "lisinopril", "telmisartan", "enalapril",
        "valsartan", "ramipril", "metoprolol", "atenolol", "nifedipine",
    ],
    "Hypothyroidism": ["levothyroxine", "thyronorm", "eltroxin"],
    "Asthma": ["salbutamol", "montelukast", "budesonide", "fluticasone", "formoterol"],
    "Atrial Fibrillation": ["warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban"],
}

EXCLUSION_TERMS = [
    "hepatic impairment", "liver failure", "cirrhosis",
    "hepatic encephalopathy", "severe renal impairment",
    "dialysis", "active malignancy", "hiv positive",
]

HOSPITALIZATION_KEYWORDS = [
    "hospitalization", "hospitalisation", "hospital admission",
    "admitted to hospital", "inpatient", "emergency room", "er visit",
]

ANTIHYPERTENSIVE_MEDS = [
    "amlodipine", "losartan", "lisinopril", "telmisartan",
    "enalapril", "valsartan", "metoprolol", "atenolol",
]

AVG_MANUAL_REVIEW_MINUTES = 30
