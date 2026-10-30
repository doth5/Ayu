# AyuSynk 2+ WhatsApp Sales Pipeline

Automated WhatsApp outreach management system for the AyuSynk 2+ digital stethoscope.

---

## Features

- **11 specialty-specific pipelines** (Cardiologist, Pediatrician, Pulmonologist, etc.)
- **Auto-enrolment** – add a doctor once and the system assigns the right pipeline automatically
- **Template library** – message templates with `{doctor_name}`, `{specialty}` placeholders
- **Media library** – upload and attach videos, images, PDFs, brochures per pipeline step
- **Daily send queue** – prepared messages with one-click WhatsApp deep links
- **Scheduler** – APScheduler runs every 15 minutes with persistent SQLite job store
- **Admin panel** – full CRUD for pipelines, steps, templates, and media via Streamlit UI
- **Pipeline controls** – pause, resume, stop (opt-out) per doctor
- **Dashboard** – live stats, specialty breakdown, recent activity, CSV export

---

## Quick Start (Windows)

### 1. Install Python 3.11+

Download from https://www.python.org/downloads/ and check *"Add Python to PATH"* during install.

### 2. Create and activate a virtual environment

```powershell
cd b:\Project\AyuDevices
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> If you get an execution policy error, run:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Start the application

```powershell
python run.py
```

This starts:
- **FastAPI backend** at http://127.0.0.1:8000  
- **Streamlit UI** at http://127.0.0.1:8501  
- **API docs** at http://127.0.0.1:8000/docs

Open your browser to **http://127.0.0.1:8501** to use the app.

---

## Environment Configuration (Optional)

Create a `.env` file in the project root to override defaults:

```env
# WhatsApp Business Cloud API (leave blank to use manual-send mode)
WHATSAPP_API_URL=https://graph.facebook.com/v19.0
WHATSAPP_TOKEN=your_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id

# Database (default: SQLite in ./data/ayusynk.db)
DATABASE_URL=sqlite:///./data/ayusynk.db

# Timezone for scheduler
SCHEDULER_TIMEZONE=Asia/Kolkata

# Max upload size in MB
MAX_UPLOAD_MB=50
```

---

## Daily Workflow

1. Open the **Streamlit UI** at http://127.0.0.1:8501
2. Go to **👨‍⚕️ Doctors** → add a new doctor with name, mobile, and specialty
3. The system immediately enrolls them in the correct pipeline
4. Go to **📤 Send Messages** → click **Prepare Due Messages**
5. A list of ready messages appears with **📲 Open WhatsApp** buttons
6. Click the button → WhatsApp opens with the message pre-filled
7. Send it manually → come back and click **✅ Mark as Sent**
8. The pipeline advances to the next step automatically

---

## Project Structure

```
AyuDevices/
├── app/
│   ├── api/            FastAPI backend + routers
│   ├── core/           Pipeline engine, scheduler, WhatsApp, template renderer
│   ├── database/       SQLAlchemy models, DB setup, seed data
│   └── streamlit/      Streamlit UI pages
├── config/             Settings (pydantic-settings)
├── data/               SQLite database (auto-created)
├── media/              Uploaded files (images, videos, PDFs, audio)
├── requirements.txt
├── run.py              One-command launcher
└── README.md
```

---

## WhatsApp Integration Modes

### Manual-Send Mode (Default)
The app generates a `wa.me` deep-link with the message pre-filled.  
You click the link → WhatsApp opens → you press Send.  
This keeps messages feeling personal and human.

### API Mode (Optional)
Set `WHATSAPP_API_URL`, `WHATSAPP_TOKEN`, and `WHATSAPP_PHONE_NUMBER_ID` in `.env`.  
Messages will be sent automatically via the official WhatsApp Business Cloud API.

---

## Admin Panel Usage

| Page | What you can do |
|------|----------------|
| 📊 Dashboard | View KPIs, specialty breakdown, recent activity, export CSV |
| 👨‍⚕️ Doctors | Add/search/filter doctors, pause/resume/stop pipelines |
| 📤 Send Messages | Daily queue – prepare, preview, send, mark done |
| 🔧 Pipelines | Edit steps, delays, template/media associations per specialty |
| 📝 Templates | Create/edit message templates with live preview |
| 📁 Media | Upload and manage videos, images, PDFs, documents |

---

## Database Migration to PostgreSQL

Change `DATABASE_URL` in `.env`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/ayusynk
```

All models are PostgreSQL-compatible (SQLAlchemy ORM).

---

## Support

For issues or feature requests, check the pipeline logs in the terminal or open the FastAPI docs at http://127.0.0.1:8000/docs.
