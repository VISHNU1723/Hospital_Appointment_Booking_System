
from datetime import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.doctor import Doctor
from app.models.doctor_schedule import DoctorSchedule
from app.schemas.doctor_schedule import (
    DoctorScheduleCreate,
    DoctorScheduleUpdate,
    DoctorScheduleResponse,
)

router = APIRouter(
    prefix="/doctor-schedules",
    tags=["Doctor Schedules"],
)


@router.post(
    "/",
    response_model=DoctorScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(
    schedule_data: DoctorScheduleCreate,
    db: Session = Depends(get_db),
):
    doctor = db.get(Doctor, schedule_data.doctor_id)

    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if schedule_data.start_time >= schedule_data.end_time:
        raise HTTPException(
            status_code=400,
            detail="Start time must be before end time",
        )

    schedule = DoctorSchedule(**schedule_data.model_dump())
    db.add(schedule)

    try:
        db.commit()
        db.refresh(schedule)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Schedule conflicts with an existing record",
        )

    return schedule


@router.get("/", response_model=list[DoctorScheduleResponse])
def list_schedules(
    doctor_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(DoctorSchedule)

    if doctor_id is not None:
        query = query.filter(DoctorSchedule.doctor_id == doctor_id)

    return query.all()


@router.get("/{schedule_id}", response_model=DoctorScheduleResponse)
def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
):
    schedule = db.get(DoctorSchedule, schedule_id)

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return schedule


@router.put("/{schedule_id}", response_model=DoctorScheduleResponse)
def update_schedule(
    schedule_id: int,
    schedule_data: DoctorScheduleUpdate,
    db: Session = Depends(get_db),
):
    schedule = db.get(DoctorSchedule, schedule_id)

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    updates = schedule_data.model_dump(exclude_unset=True)
    start_time = updates.get("start_time", schedule.start_time)
    end_time = updates.get("end_time", schedule.end_time)

    if start_time >= end_time:
        raise HTTPException(
            status_code=400,
            detail="Start time must be before end time",
        )

    for field, value in updates.items():
        setattr(schedule, field, value)

    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
):
    schedule = db.get(DoctorSchedule, schedule_id)

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    db.delete(schedule)
    db.commit()
