
from datetime import date

from sqlalchemy import Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Consultation(BaseModel):
    __tablename__ = "consultations"

    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    symptoms: Mapped[str] = mapped_column(Text, nullable=False)
    diagnosis: Mapped[str] = mapped_column(Text, nullable=False)
    prescription: Mapped[str | None] = mapped_column(Text, nullable=True)
    advice: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
