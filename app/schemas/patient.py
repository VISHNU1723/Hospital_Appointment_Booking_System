
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PatientCreate(BaseModel):
    user_id: int = Field(gt=0)
    full_name: str = Field(min_length=2, max_length=150)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(
        default=None,
        pattern=r"^[0-9]{10}$",
    )
    address: str | None = Field(default=None, max_length=300)
    blood_group: str | None = Field(default=None, max_length=5)


class PatientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(
        default=None,
        pattern=r"^[0-9]{10}$",
    )
    address: str | None = Field(default=None, max_length=300)
    blood_group: str | None = Field(default=None, max_length=5)
    is_active: bool | None = None


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    full_name: str
    date_of_birth: date | None
    gender: str | None
    phone: str | None
    address: str | None
    blood_group: str | None
    is_active: bool
