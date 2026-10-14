
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class UploadedFile(BaseModel):
    __tablename__ = "uploaded_files"

    consultation_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    size_kb: Mapped[int] = mapped_column(Integer, nullable=False)
