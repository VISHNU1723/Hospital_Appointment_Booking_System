from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine, Base
from app.jobs.scheduled_jobs import start_scheduler, scheduler

from app.routers.auth import router as auth_router
from app.routers.departments import router as departments_router
from app.routers.doctor import router as doctor_router

from app.routers import (
    patients,
    doctor,
    doctor_schedule,
    doctor_leaves,
    appointment,
    consultation,
    uploaded_files,
)

from app.routers.websockets import router as websocket_router

# Import models before creating tables.
from app.models import department, doctor as doctor_model
from app.models import doctor_schedule as doctor_schedule_model
from app.models import patient, user
from app.models import appointment as appointment_model
from app.models import consultation as consultation_model
from app.models import uploaded_file as uploaded_file_model
from app.middleware.file_validation import FileValidationMiddleware
from app.routers import reports
from app.routers import review

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist.
    Base.metadata.create_all(bind=engine)

    # Start scheduled background jobs.
    start_scheduler()

    # Confirm scheduler status in the server terminal.
    print("Scheduler running:", scheduler.running)
    print(
        "Registered jobs:",
        [job.id for job in scheduler.get_jobs()],
    )

    try:
        yield
    finally:
        # Stop the scheduler when the application shuts down.
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(
    title="Hospital Appointment Booking System",
    description=(
        "API for hospital departments, doctors, patients, "
        "appointments, consultations, and uploaded files."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# Register API routers.
app.include_router(auth_router)
app.include_router(departments_router)
app.include_router(doctor_router)
app.include_router(patients.router)
app.include_router(doctor.router)
app.include_router(doctor_schedule.router)
app.include_router(doctor_leaves.router)
app.include_router(appointment.router)
app.include_router(consultation.router)
app.include_router(uploaded_files.router)
app.include_router(websocket_router)
app.add_middleware(FileValidationMiddleware)
app.include_router(reports.router)
app.include_router(review.router)


@app.get("/")
def root():
    return {
        "message": "Hospital Appointment Booking System API is running"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}