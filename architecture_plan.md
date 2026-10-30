# AyuSynk WhatsApp Sales Pipeline — Architecture Plan

## Directory Structure

```
AyuDevices/
├── app/
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── database.py        # DB engine/session
│   │   └── migrations/        # Alembic or manual migrations
│   ├── core/
│   │   ├── __init__.py
│   │   ├── pipeline_engine.py # Pipeline execution logic
│   │   ├── scheduler.py       # APScheduler setup
│   │   ├── whatsapp.py        # WhatsApp integration layer
│   │   └── template_engine.py # Placeholder rendering
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routers/
│   │   │   ├── doctors.py
│   │   │   ├── pipelines.py
│   │   │   ├── templates.py
│   │   │   ├── media.py
│   │   │   └── dashboard.py
│   │   └── main.py            # FastAPI app
│   └── streamlit/
│       ├── main.py            # Entry point
│       ├── pages/
│       │   ├── 1_Dashboard.py
│       │   ├── 2_Doctors.py
│       │   ├── 3_Pipelines.py
│       │   ├── 4_Templates.py
│       │   ├── 5_Media.py
│       │   └── 6_Send_Messages.py
│       └── utils/
│           ├── api_client.py
│           └── helpers.py
├── media/                     # Local media storage
│   ├── videos/
│   ├── images/
│   ├── pdfs/
│   └── brochures/
├── data/
│   └── ayusynk.db            # SQLite database
├── config/
│   └── settings.py
├── requirements.txt
├── run.py                     # Launcher script
└── README.md
```

## Database Schema (Key Tables)

- `doctors` — contacts with specialty, status
- `specialties` — lookup table
- `pipelines` — one per specialty, named, versioned
- `pipeline_steps` — ordered steps within a pipeline (template_id, media_id, delay_hours, conditions)
- `message_templates` — text templates with placeholders
- `media_files` — uploaded files with metadata
- `doctor_pipeline_enrollments` — which pipeline a doctor is on, current step
- `pipeline_executions` — individual step execution records (status, timestamps)
- `message_log` — complete history of every send attempt

## Build Order

1. DB models + seed data
2. FastAPI backend (CRUD routes)
3. Pipeline engine + scheduler
4. Streamlit UI — Dashboard, Doctors, Admin panels
5. WhatsApp integration (manual-send bridge)
6. Tests + README
