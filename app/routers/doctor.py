
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.doctor import Doctor
from app.models.department import Department
from app.models.appointment import Appointment
from app.schemas.doctor import (
    DoctorCreate,
    DoctorUpdate,
    DoctorResponse,
)
from app.auth.dependencies import require_role
from app.websockets.manager import manager
from app.websockets.routes import queue_payload

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.post(
    "/",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_doctor(
    doctor_data: DoctorCreate,
    db: Session = Depends(get_db),
):
    user = db.get(User, doctor_data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    department = db.get(Department, doctor_data.department_id)

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    existing = (
        db.query(Doctor)
        .filter(Doctor.user_id == doctor_data.user_id)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user already has a doctor profile",
        )

    doctor = Doctor(**doctor_data.model_dump())

    try:
        db.add(doctor)
        db.commit()
        db.refresh(doctor)
        return doctor
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create doctor",
        )


@router.get("/", response_model=list[DoctorResponse])
def list_doctors(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return (
        db.query(Doctor)
        .order_by(Doctor.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
):
    doctor = db.get(Doctor, doctor_id)

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    return doctor


@router.put("/{doctor_id}", response_model=DoctorResponse)
def update_doctor(
    doctor_id: int,
    doctor_data: DoctorUpdate,
    db: Session = Depends(get_db),
):
    doctor = db.get(Doctor, doctor_id)

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    updates = doctor_data.model_dump(exclude_unset=True)

    if "department_id" in updates and updates["department_id"] is not None:
        department = db.get(Department, updates["department_id"])

        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found",
            )

    for field, value in updates.items():
        setattr(doctor, field, value)

    try:
        db.commit()
        db.refresh(doctor)
        return doctor
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update doctor",
        )


@router.delete("/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
):
    doctor = db.get(Doctor, doctor_id)

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    try:
        db.delete(doctor)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete doctor",
        )


@router.put("/me/call-next")
async def call_next_patient(
    current_user=Depends(require_role("DOCTOR")),
    db: Session = Depends(get_db),
):
    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found",
        )

    start = datetime.combine(date.today(), time.min)
    end = start + timedelta(days=7)

    current = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_time >= start,
            Appointment.appointment_time < end,
            Appointment.status == "IN CONSULTATION",
        )
        .first()
    )

    if current:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete the current consultation before calling next",
        )

    next_appointment = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_time >= start,
            Appointment.appointment_time < end,
            Appointment.status == "CHECKED_IN",
        )
        .order_by(
            Appointment.appointment_time.asc(),
            Appointment.id.asc(),
        )
        .first()
    )

    if not next_appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No checked-in patients waiting",
        )

    next_appointment.status = "IN CONSULTATION"

    try:
        db.commit()
        db.refresh(next_appointment)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to call the next patient",
        )

    await manager.broadcast_queue(
        doctor.id,
        queue_payload(db, doctor.id),
    )

    return {
        "message": "Next patient called successfully",
        "appointment_id": next_appointment.id,
        "status": next_appointment.status,
    }
