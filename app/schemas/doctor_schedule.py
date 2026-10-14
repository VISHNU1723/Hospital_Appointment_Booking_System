
from datetime import time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DoctorScheduleBase(BaseModel):
    doctor_id: int = Field(gt=0)
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    break_start: time | None = None
    break_end: time | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.start_time >= self.end_time:
            raise ValueError("Start time must be before end time")

        if (self.break_start is None) != (self.break_end is None):
            raise ValueError("Provide both break_start and break_end")

        if self.break_start is not None and self.break_end is not None:
            if not (
                self.start_time <= self.break_start
                < self.break_end <= self.end_time
            ):
                raise ValueError(
                    "Break must be within working hours and start before it ends"
                )

        return self


class DoctorScheduleCreate(DoctorScheduleBase):
    pass


class DoctorScheduleUpdate(BaseModel):
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    break_start: time | None = None
    break_end: time | None = None
    is_active: bool | None = None


class DoctorScheduleResponse(DoctorScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
