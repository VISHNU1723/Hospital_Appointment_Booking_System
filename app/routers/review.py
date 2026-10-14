from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appointment import Appointment
from app.models.review import Review
from app.models.patient import Patient

router = APIRouter(prefix="/reviews", tags=["Reviews"])


class ReviewCreate(BaseModel):
    appointment_id: int = Field(gt=0)
    patient_id: int = Field(gt=0)
    rating: int = Field(ge=1, le=5)
    feedback: str | None = Field(default=None, max_length=2000)


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_id: int
    patient_id: int
    doctor_id: int
    rating: int
    feedback: str | None = None


@router.post("/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(data: ReviewCreate, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter(
        Appointment.id == data.appointment_id
    ).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.status != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="Reviews are allowed only after completed appointments",
        )

    if appointment.patient_id != data.patient_id:
        raise HTTPException(
            status_code=403,
            detail="Patient does not own this appointment",
        )

    existing = db.query(Review).filter(
        Review.appointment_id == data.appointment_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="A review already exists for this appointment",
        )

    review = Review(
        appointment_id=appointment.id,
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        rating=data.rating,
        feedback=data.feedback,
    )

    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.get("/", response_model=list[ReviewResponse])
def list_reviews(
    doctor_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Review)

    if doctor_id is not None:
        query = query.filter(Review.doctor_id == doctor_id)

    return query.order_by(Review.id.desc()).all()
