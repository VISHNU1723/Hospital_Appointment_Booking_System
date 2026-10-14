from io import BytesIO
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from app.database import get_db
from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationResponse,
)

router = APIRouter(prefix="/appointments", tags=["Consultations"])


@router.post(
    "/{appointment_id}/consultation",
    response_model=ConsultationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_consultation(
    appointment_id: int,
    data: ConsultationCreate,
    db: Session = Depends(get_db),
):
    appointment = db.get(Appointment, appointment_id)

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.status != "IN CONSULTATION":
        raise HTTPException(
            status_code=400,
            detail="Consultation can only be saved when appointment is IN CONSULTATION",
        )

    existing = db.query(Consultation).filter(
        Consultation.appointment_id == appointment_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Consultation already exists for this appointment",
        )

    consultation = Consultation(
        appointment_id=appointment_id,
        **data.model_dump(),
    )

    appointment.status = "COMPLETED"
    db.add(consultation)
    db.commit()
    db.refresh(consultation)

    return consultation


@router.get(
    "/{appointment_id}/consultation",
    response_model=ConsultationResponse,
)
def get_consultation(
    appointment_id: int,
    db: Session = Depends(get_db),
):
    consultation = db.query(Consultation).filter(
        Consultation.appointment_id == appointment_id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    return consultation


@router.get("/{appointment_id}/consultation/pdf")
def download_prescription_pdf(
    appointment_id: int,
    db: Session = Depends(get_db),
):
    appointment = db.get(Appointment, appointment_id)

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.status != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="Prescription PDF is available only for completed appointments",
        )

    consultation = db.query(Consultation).filter(
        Consultation.appointment_id == appointment_id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"Prescription Appointment {appointment_id}",
    )

    styles = getSampleStyleSheet()
    story = [
        Paragraph("Hospital Prescription", styles["Title"]),
        Spacer(1, 16),
        Paragraph(f"Appointment ID: {appointment_id}", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("Symptoms", styles["Heading2"]),
        Paragraph(escape(consultation.symptoms or "Not provided"), styles["BodyText"]),
        Spacer(1, 10),
        Paragraph("Diagnosis", styles["Heading2"]),
        Paragraph(escape(consultation.diagnosis or "Not provided"), styles["BodyText"]),
        Spacer(1, 10),
        Paragraph("Prescription / Medication", styles["Heading2"]),
        Paragraph(
            escape(consultation.prescription or "No prescription provided"),
            styles["BodyText"],
        ),
        Spacer(1, 10),
        Paragraph("Advice", styles["Heading2"]),
        Paragraph(
            escape(consultation.advice or "No additional advice"),
            styles["BodyText"],
        ),
        Spacer(1, 10),
        Paragraph(
            f"Follow-up date: {consultation.follow_up_date or 'Not scheduled'}",
            styles["Normal"],
        ),
    ]

    document.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="prescription_appointment_{appointment_id}.pdf"'
            )
        },
    )
