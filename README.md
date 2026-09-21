# ExamGuard

**Development of Smart Examination Monitoring platform with Integrity Analysis & Reporting System**

ExamGuard is a Flask-based examination integrity platform that combines candidate authentication, identity verification, webcam face-presence monitoring, browser event logging, integrity scoring, analytics, and report generation in a single SQLite-backed system.

## Objectives

- Detect suspicious exam behavior in real time.
- Monitor face presence and browser activity during assessments.
- Score candidate integrity consistently and transparently.
- Produce reports and exports for administrative review.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed_db.py
python app.py
```

Open `http://127.0.0.1:5000/`.

Optional invigilator dashboard:

```powershell
streamlit run streamlit_app.py
```

Optional phone detection support is represented by `models/yolo11n.pt`.
Install the package without replacing the compatible OpenCV contrib build:

```powershell
pip install --no-deps -r requirements-optional.txt
```

Optional AI report configuration uses `EXAMGUARD_LLM_API_KEY` and optionally `EXAMGUARD_LLM_MODEL`. Never commit credentials.

## Main features

- Candidate registration, authentication, exam selection, and results.
- Identity verification and OpenCV Haar-cascade face presence detection.
- Browser event logging, integrity scoring, evidence, and exports.
- Streamlit invigilator dashboard, analytics, and real K-Means clustering.
- Optional LangChain/OpenAI reporting with a factual offline fallback.

## Project structure

- `app.py` — Flask entry point
- `routes/` — application workflows and APIs
- `database/` — SQLite schema and service layer
- `services/` — monitoring, scoring, analytics, and reporting
- `templates/` and `static/` — web interface
- `models/` — ML model files
- `tests/` — regression tests
- `docs/` and `Project_Documentation.md` — documentation

## Testing summary

```powershell
python -m pytest -q
python -m unittest discover -s tests -v
python -m compileall -q .
python -m pip check
```

See [Project_Documentation.md](Project_Documentation.md) for the complete technical documentation.
