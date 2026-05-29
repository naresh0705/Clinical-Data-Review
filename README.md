# OBERON-301: Cross-Form Clinical Data Review Assistant

An AI-powered clinical data review tool that detects cross-form inconsistencies in clinical trial data — catching issues that traditional edit checks miss.

Built by a Clinical Data Manager (CCDM®) with 17+ years of experience at J&J, Novartis, and BMS.

---

## The Problem

Clinical Data Managers spend 40–60% of their review time manually checking patient data across multiple CRF forms — looking for inconsistencies that no single edit check can catch.

Examples:
- A subject's lab values trending 3x above normal across visits, but no adverse event reported
- A medication prescribed without any matching condition in medical history
- A fatal adverse event outcome, but disposition says the subject "completed" the study

These cross-form issues are the #1 source of audit findings — and they're invisible to standard EDC edit checks.

## The Solution

This tool automates cross-form clinical data review using a two-layer approach:

**Layer 1 — Rule-Based Engine:** 18 deterministic validation rules across 8 categories covering date validation, safety criteria, lab trending, vital sign changes, medication-condition matching, disposition logic, and exclusion criteria checks.

**Layer 2 — LLM Engine:** AI-powered clinical reasoning that catches what rules cannot — medication-to-condition semantic matching (20,000+ combinations), natural language analysis of AE verbatim text, whole-patient narrative review, and automated clinical data query generation.

## Key Results

| Metric | Value |
|--------|-------|
| Subjects analyzed | 62 |
| CRF domains covered | 7 (Demographics, Medical History, Concomitant Meds, Adverse Events, Labs, Vital Signs, Disposition) |
| Planted cross-form errors | 26 |
| Detection rate | 85%+ |
| Manual review time (estimated) | 6–8 hours |
| Tool processing time | Under 2 minutes |
| False positive reduction | 300 → 30 flags (90% noise reduction through prompt tuning) |

## Architecture

```
┌─────────────────────────────────┐
│     CSV Upload (7 CRF files)    │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│     Data Ingestion & Linking    │
│     (Link by Subject_ID)        │
└──────────────┬──────────────────┘
               │
        ┌──────┴──────┐
        ▼             ▼
┌──────────────┐ ┌───────────────┐
│ Rule-Based   │ │  LLM Engine   │
│ Engine       │ │  (GPT-4o)     │
│              │ │               │
│ 18 rules     │ │ Med-condition │
│ 8 categories │ │ matching,     │
│ Date checks  │ │ AE verbatim   │
│ Lab trending │ │ analysis,     │
│ Safety logic │ │ subject-level │
│              │ │ reasoning     │
└──────┬───────┘ └───────┬───────┘
       │                 │
       └────────┬────────┘
                ▼
┌─────────────────────────────────┐
│     Deduplication & Scoring     │
│     (Confidence: Critical/High) │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│     Results Dashboard           │
│     - Summary metrics           │
│     - Flagged issues table      │
│     - Subject detail view       │
│     - CSV export                │
└─────────────────────────────────┘
```

## Types of Issues Detected

**What edit checks catch (field-level):**
- Missing values, out-of-range entries, date format errors

**What this tool catches (cross-form, clinical-level):**

| Category | Example |
|----------|---------|
| Lab ↔ AE | ALT trending 3x ULN across visits with no hepatotoxicity AE reported |
| Vitals ↔ AE | BP consistently >160/100 across all visits, no hypertension AE, no antihypertensive medication |
| Meds ↔ MH | Metformin prescribed but no diabetes in Medical History |
| AE ↔ Disposition | Fatal AE outcome but subject disposition = "Completed Study" |
| AE ↔ Meds | New medication started same day as AE onset, causality marked "Not Related" |
| MH ↔ Meds | Ongoing Hypertension in Medical History but no antihypertensive in Concomitant Meds |
| Demographics ↔ All | Consent date after screening date, age outside inclusion criteria |
| Vitals ↔ AE | Sudden weight gain (+14kg between visits) with no corresponding AE |

## Tech Stack

- **Backend:** Python, FastAPI, Uvicorn
- **LLM Integration:** OpenAI GPT-4o (configurable)
- **Frontend:** HTML, CSS, JavaScript
- **Data Processing:** Pandas, CSV
- **Standards Referenced:** ICH-GCP, CDISC, MedDRA, ICH E2A

## Run Modes

| Mode | Cost | Speed | What it does |
|------|------|-------|-------------|
| Rules Only | Free | Instant | Runs all 18 rule-based checks, no LLM |
| Rules + LLM | ~$1.50/run | 5–10 min | Full analysis with AI-powered clinical reasoning |

---

## Installation & Setup

### Prerequisites

- Python 3.10 or higher
- OpenAI API key (optional — only needed for LLM mode)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/[your-username]/OBERON-301-Clinical-Review.git
cd OBERON-301-Clinical-Review

# Create and activate virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OpenAI API key (optional)

# Start the application
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Open your browser and go to: **http://localhost:8000**

### Usage

1. Upload all 7 CSV files (Demographics, Medical History, Concomitant Meds, Adverse Events, Lab Data, Vital Signs, Disposition)
2. Select analysis mode (Rules Only or Rules + LLM)
3. Click "Run Analysis"
4. Review flagged issues in the results dashboard
5. Export results to CSV for further review

### Detailed Windows Setup Guide

For step-by-step Windows installation instructions, see [SETUP_GUIDE.md](SETUP_GUIDE.md)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `python` not recognized | Reinstall Python with "Add to PATH" checked |
| `venv\Scripts\activate` error | Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` in PowerShell |
| Port 8000 in use | Use `python -m uvicorn app:app --port 8001` |
| LLM analysis fails | Verify API key in `.env` file and check OpenAI account credits |
| Blank page | Clear browser cache (Ctrl+Shift+Delete) and refresh |

---

## Clinical Validation

The tool was tested against a synthetic dataset with 26 deliberately planted cross-form errors spanning all 7 CRF domains. The error tracker and validation methodology are included in the `/data` directory.

**Important:** This tool is designed as a QC assistant for clinical data review. It does not replace human judgment. All flags require CDM review before action. For production use in a GCP environment, appropriate validation (IQ/OQ/PQ) and SOPs would be required.

---

## About

Built by **Naresh Parlapalli, CCDM®** — 17+ years in Clinical Data Management at Accenture, Novartis, IQVIA,PPD, Syneos and Concert AI. This tool was created to demonstrate how AI can augment (not replace) clinical data review workflows.

Contact: naresh.0705@gmail.com | +91 7829100707

## License

This project is for demonstration and educational purposes.
