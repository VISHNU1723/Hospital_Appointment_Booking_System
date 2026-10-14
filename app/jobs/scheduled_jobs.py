import logging
from datetime import datetime, timedelta, date

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.user import User
from app.services.email_service import send_email

logger = logging.getLogger(__name__)


def get_patient_email(db: Session, patient_id: int):
    """Get the email address from the User linked to a patient."""
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id)
        .first()
    )

    if not patient:
        logger.warning("Patient %s was not found", patient_id)
        return None

    patient_user = (
        db.query(User)
        .filter(User.id == patient.user_id)
        .first()
    )

    if not patient_user or not patient_user.email:
        logger.warning(
            "No linked user email found for patient %s", patient_id
        )
        return None

    return patient_user.email


def send_appointment_reminders():
    """Email reminders for booked appointments within the next 24 hours."""
    db: Session = SessionLocal()

    try:
        now = datetime.now()

        upcoming = (
            db.query(Appointment)
            .filter(
                Appointment.appointment_time >= now,
                Appointment.appointment_time <= now + timedelta(hours=24),
                Appointment.status == "BOOKED",
                Appointment.reminder_sent.is_(False),
            )
            .all()
        )

        for appointment in upcoming:
            try:
                email = get_patient_email(db, appointment.patient_id)

                if not email:
                    continue

                success = send_email(
                    email,
                    "Appointment Reminder",
                    (
                        f"Reminder: Appointment {appointment.id} with doctor "
                        f"{appointment.doctor_id} is scheduled for "
                        f"{appointment.appointment_time}."
                    ),
                )

                if success:
                    appointment.reminder_sent = True
                    db.commit()
                else:
                    logger.warning(
                        "Reminder email was not sent for appointment %s",
                        appointment.id,
                    )

            except Exception:
                db.rollback()
                logger.exception(
                    "Reminder failed for appointment %s",
                    appointment.id,
                )

    except Exception:
        logger.exception("Appointment reminder job failed")

    finally:
        db.close()


def mark_no_shows():
    """Mark booked appointments as no-shows 30 minutes after their time."""
    db: Session = SessionLocal()

    try:
        cutoff = datetime.now() - timedelta(minutes=30)

        overdue = (
            db.query(Appointment)
            .filter(
                Appointment.appointment_time < cutoff,
                Appointment.status == "BOOKED",
            )
            .all()
        )

        for appointment in overdue:
            appointment.status = "NO_SHOW"

        if overdue:
            db.commit()
            logger.info("Marked %s appointments as NO_SHOW", len(overdue))

    except Exception:
        logger.exception("No-show job failed")
        db.rollback()

    finally:
        db.close()


def send_follow_up_reminders():
    """Email reminders one day before a completed appointment's follow-up."""
    db: Session = SessionLocal()

    try:
        tomorrow = date.today() + timedelta(days=1)

        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.follow_up_date == tomorrow,
                Appointment.status == "COMPLETED",
                Appointment.follow_up_reminder_sent.is_(False),
            )
            .all()
        )

        for appointment in appointments:
            try:
                email = get_patient_email(db, appointment.patient_id)

                if not email:
                    continue

                success = send_email(
                    email,
                    "Follow-up Reminder",
                    f"Your follow-up date is tomorrow ({tomorrow}).",
                )

                if success:
                    appointment.follow_up_reminder_sent = True
                    db.commit()
                else:
                    logger.warning(
                        "Follow-up email was not sent for appointment %s",
                        appointment.id,
                    )

            except Exception:
                db.rollback()
                logger.exception(
                    "Follow-up reminder failed for appointment %s",
                    appointment.id,
                )

    except Exception:
        logger.exception("Follow-up reminder job failed")

    finally:
        db.close()


scheduler = BackgroundScheduler()


def start_scheduler():
    """Register and start scheduled jobs once."""
    if scheduler.running:
        logger.info("Scheduler is already running")
        return

    scheduler.add_job(
        send_appointment_reminders,
        "interval",
        hours=1,
        id="appointment_reminders",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    scheduler.add_job(
        mark_no_shows,
        "interval",
        minutes=15,
        id="mark_no_shows",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    scheduler.add_job(
        send_follow_up_reminders,
        "interval",
        hours=24,
        id="follow_up_reminders",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    scheduler.start()

    logger.info(
        "Appointment scheduler started. Registered jobs: %s",
        [job.id for job in scheduler.get_jobs()],
    )