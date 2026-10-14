
import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.doctor import Doctor
from app.models.doctor_leave import DoctorLeave
from app.models.user import User
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/doctor-leaves",
    tags=["Doctor Leaves"],
)


@router.post("/", status_code=201)
def create_doctor_leave(
    background_tasks: BackgroundTasks,
    doctor_id: int,
    leave_date: str,
    reason: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        parsed_leave_date = date.fromisoformat(leave_date)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="leave_date must use YYYY-MM-DD format",
        )

    doctor = (
        db.query(Doctor)
        .filter(Doctor.id == doctor_id)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found",
        )

    leave = DoctorLeave(
        doctor_id=doctor_id,
        leave_date=parsed_leave_date,
        reason=reason,
    )

    db.add(leave)
    db.commit()
    db.refresh(leave)

    # Get the doctor's email from the linked user account.
    doctor_user = (
        db.query(User)
        .filter(User.id == doctor.user_id)
        .first()
    )

    if doctor_user and doctor_user.email:
        background_tasks.add_task(
            send_email,
            doctor_user.email,
            "Doctor Leave Recorded",
            (
                f"Your leave has been recorded for "
                f"{parsed_leave_date}.\n"
                f"Reason: {reason or 'Not specified'}"
            ),
        )
        logger.info(
            "Leave notification queued for doctor %s",
            doctor_id,
        )
    else:
        logger.warning(
            "Leave %s created, but no linked user email was found "
            "for doctor %s",
            leave.id,
            doctor_id,
        )

    return leave


@router.get("/")
def list_doctor_leaves(
    db: Session = Depends(get_db),
):
    return db.query(DoctorLeave).all()
