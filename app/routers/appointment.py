from datetime import datetime
import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentResponse
from app.websockets.manager import manager
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"],
)

VALID_STATUSES = {
    "BOOKED",
    "CHECKED_IN",
    "IN CONSULTATION",
    "COMPLETED",
    "CANCELLED",
    "NO_SHOW",
}


# --------------------------------------------------
# WebSocket queue updates
# --------------------------------------------------
async def broadcast_doctor_queue(db: Session, doctor_id: int):
    from app.websockets.routes import queue_payload, get_today_queue

    payload = queue_payload(db, doctor_id)
    await manager.broadcast_queue(doctor_id, payload)

    waiting = [
        appointment
        for appointment in get_today_queue(db, doctor_id)
        if appointment.status in ("BOOKED", "CHECKED_IN")
    ]

    if waiting:
        next_appointment = waiting[0]
        patient = (
            db.query(Patient)
            .filter(Patient.id == next_appointment.patient_id)
            .first()
        )

        if patient:
            await manager.notify_user(
                patient.user_id,
                {
                    "type": "your_turn_next",
                    "message": "You are next, please be ready",
                    "appointment_id": next_appointment.id,
                    "doctor_id": doctor_id,
                },
            )


# --------------------------------------------------
# Create appointment
# --------------------------------------------------
@router.post(
    "/",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment(
    appointment_data: AppointmentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    patient = (
        db.query(Patient)
        .filter(Patient.id == appointment_data.patient_id)
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    doctor = (
        db.query(Doctor)
        .filter(Doctor.id == appointment_data.doctor_id)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    if hasattr(doctor, "is_active") and not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor is inactive",
        )

    if appointment_data.appointment_time <= datetime.now():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Appointment time must be in the future",
        )

    existing_appointment = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == appointment_data.doctor_id,
            Appointment.appointment_time == appointment_data.appointment_time,
            Appointment.status.in_(["BOOKED", "CHECKED_IN", "IN CONSULTATION"]),
        )
        .first()
    )

    if existing_appointment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor is already booked for this time slot",
        )

    appointment = Appointment(**appointment_data.model_dump())

    try:
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
    except Exception:
        db.rollback()
        logger.exception("Failed to create appointment")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create appointment",
        )

    try:
        patient_user = (
            db.query(User)
            .filter(User.id == patient.user_id)
            .first()
        )

        if patient_user and patient_user.email:
            background_tasks.add_task(
                send_email,
                patient_user.email,
                "Appointment Booked Successfully",
                (
                    "Your appointment has been booked successfully.\n\n"
                    f"Appointment Number: {appointment.id}\n"
                    f"Doctor: {doctor.name}\n"
                    f"Date and Time: {appointment.appointment_time}\n"
                    f"Token Number: {appointment.id}\n"
                ),
            )

        await broadcast_doctor_queue(db, appointment.doctor_id)

        await manager.notify_user(
            patient.user_id,
            {
                "type": "appointment_booked",
                "message": "Your appointment has been booked successfully",
                "appointment_id": appointment.id,
                "doctor_id": appointment.doctor_id,
                "appointment_time": appointment.appointment_time.isoformat(),
            },
        )
    except Exception:
        # The appointment is already committed.
        # A notification failure must not undo a successful booking.
        logger.exception(
            "Appointment %s saved, but notification failed",
            appointment.id,
        )

    return appointment


# --------------------------------------------------
# List, paginate, and search appointments
# --------------------------------------------------
@router.get("/", response_model=list[AppointmentResponse])
def list_appointments(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status_filter: str | None = Query(None),
    doctor_id: int | None = Query(None, gt=0),
    patient_id: int | None = Query(None, gt=0),
    appointment_id: int | None = Query(None, gt=0),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Appointment)

    if status_filter:
        normalized_status = status_filter.strip().upper()

        if normalized_status not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status. Allowed values: {sorted(VALID_STATUSES)}",
            )

        query = query.filter(Appointment.status == normalized_status)

    if doctor_id is not None:
        query = query.filter(Appointment.doctor_id == doctor_id)

    if patient_id is not None:
        query = query.filter(Appointment.patient_id == patient_id)

    if appointment_id is not None:
        query = query.filter(Appointment.id == appointment_id)

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be earlier than or equal to date_to",
        )

    if date_from:
        query = query.filter(Appointment.appointment_time >= date_from)

    if date_to:
        query = query.filter(Appointment.appointment_time <= date_to)

    return (
        query.order_by(Appointment.appointment_time.desc(), Appointment.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# --------------------------------------------------
# Get appointment by ID
# --------------------------------------------------
@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    return appointment


# --------------------------------------------------
# Cancel appointment
# --------------------------------------------------
@router.patch(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
)
async def cancel_appointment(
    appointment_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if appointment.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Appointment is already cancelled",
        )

    if appointment.status in ("COMPLETED", "NO_SHOW"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel an appointment with status {appointment.status}",
        )

    appointment.status = "CANCELLED"

    try:
        db.commit()
        db.refresh(appointment)
    except Exception:
        db.rollback()
        logger.exception("Failed to cancel appointment %s", appointment_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel appointment",
        )

    patient = (
        db.query(Patient)
        .filter(Patient.id == appointment.patient_id)
        .first()
    )

    patient_user = (
        db.query(User)
        .filter(User.id == patient.user_id)
        .first()
        if patient
        else None
    )

    if patient_user and patient_user.email:
        background_tasks.add_task(
            send_email,
            patient_user.email,
            "Appointment Cancelled",
            (
                f"Your appointment {appointment.id} with doctor "
                f"{appointment.doctor_id} at "
                f"{appointment.appointment_time} has been cancelled."
            ),
        )

    try:
        await broadcast_doctor_queue(db, appointment.doctor_id)

        if patient:
            await manager.notify_user(
                patient.user_id,
                {
                    "type": "appointment_cancelled",
                    "message": "Your appointment has been cancelled",
                    "appointment_id": appointment.id,
                    "doctor_id": appointment.doctor_id,
                },
            )
    except Exception:
        logger.exception(
            "Appointment %s cancelled, but notification failed",
            appointment_id,
        )

    return appointment


# --------------------------------------------------
# Reschedule appointment
# --------------------------------------------------
@router.patch(
    "/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
)
async def reschedule_appointment(
    appointment_id: int,
    new_appointment_time: datetime,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if appointment.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reschedule a cancelled appointment",
        )

    if appointment.status in ("COMPLETED", "NO_SHOW"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reschedule an appointment with status {appointment.status}",
        )

    if new_appointment_time <= datetime.now():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New appointment time must be in the future",
        )

    existing_appointment = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == appointment.doctor_id,
            Appointment.appointment_time == new_appointment_time,
            Appointment.status.in_(["BOOKED", "CHECKED_IN", "IN CONSULTATION"]),
            Appointment.id != appointment_id,
        )
        .first()
    )

    if existing_appointment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor is already booked for this time slot",
        )

    appointment.appointment_time = new_appointment_time

    try:
        db.commit()
        db.refresh(appointment)
    except Exception:
        db.rollback()
        logger.exception("Failed to reschedule appointment %s", appointment_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reschedule appointment",
        )

    patient = (
        db.query(Patient)
        .filter(Patient.id == appointment.patient_id)
        .first()
    )

    patient_user = (
        db.query(User)
        .filter(User.id == patient.user_id)
        .first()
        if patient
        else None
    )

    if patient_user and patient_user.email:
        background_tasks.add_task(
            send_email,
            patient_user.email,
            "Appointment Rescheduled",
            (
                f"Your appointment {appointment.id} has been rescheduled to "
                f"{appointment.appointment_time}. "
                f"Doctor ID: {appointment.doctor_id}."
            ),
        )

    try:
        await broadcast_doctor_queue(db, appointment.doctor_id)

        if patient:
            await manager.notify_user(
                patient.user_id,
                {
                    "type": "appointment_rescheduled",
                    "message": "Your appointment has been rescheduled",
                    "appointment_id": appointment.id,
                    "doctor_id": appointment.doctor_id,
                    "appointment_time": appointment.appointment_time.isoformat(),
                },
            )
    except Exception:
        logger.exception(
            "Appointment %s rescheduled, but notification failed",
            appointment_id,
        )

    return appointment


# --------------------------------------------------
# Start consultation
# --------------------------------------------------
@router.patch(
    "/{appointment_id}/start-consultation",
    response_model=AppointmentResponse,
)
def start_consultation(
    appointment_id: int,
    db: Session = Depends(get_db),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if appointment.status != "BOOKED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only BOOKED appointments can start consultation",
        )

    appointment.status = "IN CONSULTATION"

    try:
        db.commit()
        db.refresh(appointment)
    except Exception:
        db.rollback()
        logger.exception("Failed to start consultation %s", appointment_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start consultation",
        )

    return appointment


# --------------------------------------------------
# Patient check-in
# --------------------------------------------------
@router.patch("/{appointment_id}/check-in")
async def check_in_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if appointment.status != "BOOKED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only BOOKED appointments can check in",
        )

    appointment.status = "CHECKED_IN"

    try:
        db.commit()
        db.refresh(appointment)
    except Exception:
        db.rollback()
        logger.exception("Failed to check in appointment %s", appointment_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check in appointment",
        )

    try:
        await broadcast_doctor_queue(db, appointment.doctor_id)
    except Exception:
        logger.exception(
            "Appointment %s checked in, but queue notification failed",
            appointment_id,
        )

    return {
        "message": "Patient checked in successfully",
        "appointment_id": appointment.id,
        "status": appointment.status,
    }