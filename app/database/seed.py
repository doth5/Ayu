"""
Seed data – creates default pipelines, placeholder templates, and pipeline steps
for every specialty. All content is marked as PLACEHOLDER so the admin can
replace it through the admin panel without touching code.
"""
from sqlalchemy.orm import Session

from app.database.models import (
    Pipeline, MessageTemplate, PipelineStep, SpecialtyEnum,
    StepType,
)

SPECIALTIES = [e.value for e in SpecialtyEnum]


# ── Default placeholder templates (one greeting + one intro per specialty) ───

def _tmpl(name: str, content: str, specialty: str | None = None) -> dict:
    return {"name": name, "content": content, "specialty": specialty}


TEMPLATES: list[dict] = [
    # ── Universal ─────────────────────────────────────────────────────────────
    _tmpl(
        "Universal Greeting",
        "Hello Dr. {doctor_name} 👋\n\nI'm reaching out from AyuSynk. May I have a moment of your time?",
    ),
    _tmpl(
        "Universal Introduction",
        "We'd like to introduce you to the *AyuSynk 2+* — a cutting-edge digital stethoscope designed for modern clinical practice.\n\nI'll share more details shortly.",
    ),
    _tmpl(
        "Follow-up Check-in",
        "Hello Dr. {doctor_name},\n\nJust following up on our earlier message about AyuSynk 2+. Do you have any questions or would you like to schedule a quick demo?",
    ),
    _tmpl(
        "Stop / Opt-out Acknowledgement",
        "Dr. {doctor_name}, we have noted your request and will not send further messages. Thank you for your time.",
    ),

    # ── Cardiologist ──────────────────────────────────────────────────────────
    _tmpl(
        "Cardiology – Specialty Pitch",
        "Dr. {doctor_name}, as a Cardiologist you'll appreciate the AyuSynk 2+'s *high-fidelity cardiac auscultation* and real-time heart sound visualisation. It pairs with our companion app for remote patient monitoring.",
        "Cardiologist",
    ),

    # ── Pediatrician ─────────────────────────────────────────────────────────
    _tmpl(
        "Pediatrics – Specialty Pitch",
        "Dr. {doctor_name}, the AyuSynk 2+ is ideal for paediatric care — its sensitive diaphragm captures subtle breath and heart sounds even in infants, while the digital recording lets you review and share findings instantly.",
        "Pediatrician",
    ),

    # ── Pulmonologist ─────────────────────────────────────────────────────────
    _tmpl(
        "Pulmonology – Specialty Pitch",
        "Dr. {doctor_name}, the AyuSynk 2+ provides *crystal-clear lung sound auscultation* with noise cancellation — perfect for your pulmonology practice. Recorded sounds can be exported and shared for teleconsultations.",
        "Pulmonologist",
    ),

    # ── General Physician ─────────────────────────────────────────────────────
    _tmpl(
        "General Physician – Specialty Pitch",
        "Dr. {doctor_name}, the AyuSynk 2+ is a versatile digital stethoscope that enhances your everyday clinical assessments — from cardiac to respiratory auscultation — with AI-assisted sound analysis.",
        "General Physician",
    ),

    # ── Surgeon ───────────────────────────────────────────────────────────────
    _tmpl(
        "Surgeon – Specialty Pitch",
        "Dr. {doctor_name}, the AyuSynk 2+ assists surgical teams with pre- and post-operative auscultation, ensuring accurate baseline recordings that can be stored and accessed digitally.",
        "Surgeon",
    ),

    # ── Anesthesiologist ─────────────────────────────────────────────────────
    _tmpl(
        "Anesthesiology – Specialty Pitch",
        "Dr. {doctor_name}, the AyuSynk 2+ supports anaesthesiology workflows with precise auscultation and digital recording for airway management and patient monitoring during procedures.",
        "Anesthesiologist",
    ),

    # ── Orthopedic ────────────────────────────────────────────────────────────
    _tmpl(
        "Orthopedic – Specialty Pitch",
        "Dr. {doctor_name}, while orthopaedics focuses on musculoskeletal care, accurate cardiac and respiratory baselines are critical. The AyuSynk 2+ makes pre-operative assessments faster and more reliable.",
        "Orthopedic",
    ),

    # ── Emergency Medicine ────────────────────────────────────────────────────
    _tmpl(
        "Emergency Medicine – Specialty Pitch",
        "Dr. {doctor_name}, in emergency settings every second counts. The AyuSynk 2+'s instant digital auscultation and noise-cancelling technology help you make rapid assessments even in noisy environments.",
        "Emergency Medicine",
    ),

    # ── Gynecologist ─────────────────────────────────────────────────────────
    _tmpl(
        "Gynecology – Specialty Pitch",
        "Dr. {doctor_name}, the AyuSynk 2+ supports maternal care with clear cardiac and fetal heart sound capture, helping you monitor both mother and baby with greater confidence.",
        "Gynecologist",
    ),

    # ── Medical Student ───────────────────────────────────────────────────────
    _tmpl(
        "Medical Student – Specialty Pitch",
        "Dear Dr. {doctor_name} (future specialist! 🎓), the AyuSynk 2+ is the perfect learning companion — built-in sound libraries, recordings, and AI-guided analysis accelerate clinical skill development.",
        "Medical Student",
    ),

    # ── Professor ─────────────────────────────────────────────────────────────
    _tmpl(
        "Professor – Specialty Pitch",
        "Dear Prof. {doctor_name}, the AyuSynk 2+ brings *digital auscultation into the classroom* — record, annotate, and share heart and lung sounds with students in real time or asynchronously.",
        "Professor",
    ),
]


def _get_or_create_template(db: Session, tmpl: dict) -> MessageTemplate:
    obj = db.query(MessageTemplate).filter_by(name=tmpl["name"]).first()
    if not obj:
        obj = MessageTemplate(**tmpl)
        db.add(obj)
        db.flush()
    return obj


def seed_all(db: Session):
    """Idempotent seed – won't duplicate records on restart."""
    # 1. Create templates
    template_map: dict[str, MessageTemplate] = {}
    for t in TEMPLATES:
        tmpl = _get_or_create_template(db, t)
        template_map[t["name"]] = tmpl

    # 2. Create one pipeline per specialty with 3 default steps
    for specialty in SPECIALTIES:
        existing = db.query(Pipeline).filter_by(specialty=specialty).first()
        if existing:
            continue

        pipeline = Pipeline(
            name=f"{specialty} Sales Pipeline",
            specialty=specialty,
            description=f"Default outreach pipeline for {specialty} doctors. Edit steps in the Admin panel.",
        )
        db.add(pipeline)
        db.flush()

        # Step 1 – Universal Greeting
        greeting_tmpl = template_map["Universal Greeting"]
        step1 = PipelineStep(
            pipeline_id=pipeline.id,
            step_order=1,
            name="Initial Greeting",
            step_type=StepType.text,
            template_id=greeting_tmpl.id,
            delay_hours=0,
        )
        db.add(step1)

        # Step 2 – Specialty pitch (24 h later)
        pitch_key = f"{specialty} – Specialty Pitch"
        pitch_tmpl = template_map.get(pitch_key, template_map["Universal Introduction"])
        step2 = PipelineStep(
            pipeline_id=pipeline.id,
            step_order=2,
            name="Specialty Introduction",
            step_type=StepType.text,
            template_id=pitch_tmpl.id,
            delay_hours=24,
        )
        db.add(step2)

        # Step 3 – Follow-up (48 h after step 2)
        followup_tmpl = template_map["Follow-up Check-in"]
        step3 = PipelineStep(
            pipeline_id=pipeline.id,
            step_order=3,
            name="Follow-up Check-in",
            step_type=StepType.text,
            template_id=followup_tmpl.id,
            delay_hours=48,
        )
        db.add(step3)

        db.flush()
