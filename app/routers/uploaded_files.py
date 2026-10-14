
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.uploaded_file import UploadedFile
from app.schemas.uploaded_file import UploadedFileResponse

router = APIRouter(tags=["Appointment Files"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
MAX_FILE_SIZE = 5 * 1024 * 1024


@router.post(
    "/appointments/{appointment_id}/files",
    response_model=UploadedFileResponse,
    status_code=201,
)
async def upload_appointment_file(
    appointment_id: int,
    uploaded_by: int = Form(...),
    file_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if file_type not in {"Lab Report", "Prescription", "Scan"}:
        raise HTTPException(400, "Invalid file_type")

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id
    ).first()
    if not appointment:
        raise HTTPException(404, "Appointment not found")

    consultation = db.query(Consultation).filter(
        Consultation.appointment_id == appointment_id
    ).first()
    if not consultation:
        raise HTTPException(400, "Create the consultation before uploading files")

    extension = ALLOWED_TYPES.get(file.content_type)
    if not extension:
        raise HTTPException(415, "Only PDF, JPG, and PNG files are allowed")

    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "File must not exceed 5 MB")

    unique_name = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOAD_DIR / unique_name

    try:
        destination.write_bytes(content)
        record = UploadedFile(
            consultation_id=consultation.id,
            uploaded_by=uploaded_by,
            file_type=file_type,
            original_name=file.filename or "upload",
            stored_name=unique_name,
            size_kb=(len(content) + 1023) // 1024,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.get(
    "/appointments/{appointment_id}/files",
    response_model=list[UploadedFileResponse],
)
def list_appointment_files(
    appointment_id: int,
    db: Session = Depends(get_db),
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id
    ).first()
    if not appointment:
        raise HTTPException(404, "Appointment not found")

    consultation = db.query(Consultation).filter(
        Consultation.appointment_id == appointment_id
    ).first()
    if not consultation:
        return []

    return db.query(UploadedFile).filter(
        UploadedFile.consultation_id == consultation.id
    ).all()


@router.get("/files/{file_id}/download")
def download_file(
    file_id: int,
    db: Session = Depends(get_db),
):
    from fastapi.responses import FileResponse

    record = db.query(UploadedFile).filter(
        UploadedFile.id == file_id
    ).first()
    if not record:
        raise HTTPException(404, "File not found")

    path = UPLOAD_DIR / record.stored_name
    if not path.is_file():
        raise HTTPException(404, "Stored file not found")

    return FileResponse(
        path=str(path),
        filename=record.original_name,
    )
