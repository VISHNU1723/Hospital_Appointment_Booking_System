
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConsultationCreate(BaseModel):
    symptoms: str = Field(min_length=1)
    diagnosis: str = Field(min_length=1)
    prescription: str | None = None
    advice: str | None = None
    follow_up_date: date | None = None

    @field_validator("symptoms", "diagnosis")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class ConsultationResponse(BaseModel):
    id: int
    appointment_id: int
    symptoms: str
    diagnosis: str
    prescription: str | None = None
    advice: str | None = None
    follow_up_date: date | None = None

    model_config = ConfigDict(from_attributes=True)
