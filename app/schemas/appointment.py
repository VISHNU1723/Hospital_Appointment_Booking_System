from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    appointment_time: datetime


class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    appointment_time: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)