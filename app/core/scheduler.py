"""
APScheduler setup – persistent SQLAlchemy job store so scheduled jobs
survive application restarts.
"""
import logging
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from config.settings import settings

logger = logging.getLogger(__name__)

TZ = pytz.timezone(settings.SCHEDULER_TIMEZONE)

_jobstores = {
    "default": SQLAlchemyJobStore(url=settings.DATABASE_URL),
}
_executors = {
    "default": ThreadPoolExecutor(max_workers=4),
}

scheduler = BackgroundScheduler(
    jobstores=_jobstores,
    executors=_executors,
    timezone=TZ,
    job_defaults={
        "coalesce": True,        # merge missed runs into one
        "max_instances": 1,      # never run same job twice concurrently
        "misfire_grace_time": 3600,  # 1-hour grace for missed jobs
    },
)


def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started (timezone: %s)", settings.SCHEDULER_TIMEZONE)
        _register_pipeline_poller()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)


def _register_pipeline_poller():
    """
    Register two recurring jobs:
    1. pipeline_poller  – prepares due steps every 15 min
    2. auto_sender      – sends prepared messages every 15 min (if AUTO_SEND_ENABLED)
    """
    scheduler.add_job(
        _poll_due_steps,
        trigger="interval",
        minutes=15,
        id="pipeline_poller",
        replace_existing=True,
        next_run_time=datetime.now(TZ),
    )
    scheduler.add_job(
        _run_auto_sender,
        trigger="interval",
        minutes=15,
        id="auto_sender",
        replace_existing=True,
        next_run_time=datetime.now(TZ),
    )


def _poll_due_steps():
    """Scan the DB for due enrollments and prepare their next steps."""
    from app.database.database import SessionLocal
    from app.core.pipeline_engine import (
        get_due_enrollments, get_next_pending_step,
        prepare_step, check_conditions,
    )

    db = SessionLocal()
    try:
        due = get_due_enrollments(db)
        logger.info("Scheduler poll: %d enrollment(s) due", len(due))
        for enrollment in due:
            try:
                step = get_next_pending_step(db, enrollment)
                if step and check_conditions(step, enrollment):
                    prepare_step(db, enrollment, step)
                    db.commit()
                    logger.info(
                        "Prepared step '%s' for doctor '%s'",
                        step.name,
                        enrollment.doctor.name,
                    )
            except Exception as exc:
                db.rollback()
                logger.error("Error preparing step for enrollment %d: %s", enrollment.id, exc)
    finally:
        db.close()


def _run_auto_sender():
    """Automatically send all prepared messages if AUTO_SEND_ENABLED=true."""
    from app.database.database import SessionLocal
    from app.core.auto_sender import auto_send_prepared
    from config.settings import settings

    if not settings.AUTO_SEND_ENABLED:
        return

    db = SessionLocal()
    try:
        summary = auto_send_prepared(db)
        logger.info("Auto-send complete: %s", summary)
    except Exception as exc:
        logger.error("Auto-sender error: %s", exc)
    finally:
        db.close()

