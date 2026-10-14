
from datetime import date, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Boolean, Date

from app.models.base import BaseModel


class Appointment(BaseModel):
    __tablename__ = "appointments"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"),
        nullable=False,
        index=True,
    )

    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id"),
        nullable=False,
        index=True,
    )

    appointment_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="BOOKED",
        nullable=False,
    )

    reminder_sent: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    follow_up_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    follow_up_reminder_sent: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )