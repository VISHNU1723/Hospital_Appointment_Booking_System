from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Doctor(BaseModel):
    __tablename__ = "doctors"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"),
        nullable=False,
    )

    specialization: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    qualification: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    experience_years: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    consultation_fee: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    slot_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=15,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationship to the department.
    department: Mapped["Department"] = relationship(
        "Department",
        back_populates="doctors",
    )

    # Relationship to the user account that stores the doctor's email.
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
    )