
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class DoctorCreate(BaseModel):
    user_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=150)
    department_id: int = Field(gt=0)
    specialization: str = Field(min_length=2, max_length=150)
    qualification: str = Field(min_length=2, max_length=150)
    experience_years: int = Field(default=0, ge=0)
    consultation_fee: float = Field(gt=0)
    slot_duration_minutes: Literal[10, 15, 20, 30] = 15


class DoctorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    department_id: int | None = Field(default=None, gt=0)
    specialization: str | None = Field(
        default=None, min_length=2, max_length=150
    )
    qualification: str | None = Field(
        default=None, min_length=2, max_length=150
    )
    experience_years: int | None = Field(default=None, ge=0)
    consultation_fee: float | None = Field(default=None, gt=0)
    slot_duration_minutes: Literal[10, 15, 20, 30] | None = None
    is_active: bool | None = None


class DoctorResponse(BaseModel):
    id: int
    user_id: int
    name: str
    department_id: int
    specialization: str
    qualification: str
    experience_years: int
    consultation_fee: float
    slot_duration_minutes: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
