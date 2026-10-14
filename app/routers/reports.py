
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, extract, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import require_role
from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.department import Department
from app.models.patient import Patient

router = APIRouter(
    prefix="/reports",
    tags=["Reports & Dashboard"],
    dependencies=[Depends(require_role("ADMIN"))],
)


def validate_date_range(date_from: date, date_to: date):
    if date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="date_from must be on or before date_to",
        )


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    today = date.today()
    start = datetime.combine(today, time.min)
    end = start + timedelta(days=1)

    appointments = db.query(Appointment).filter(
        Appointment.appointment_time >= start,
        Appointment.appointment_time < end,
    )

    total = appointments.count()

    status_counts = dict(
        db.query(
            Appointment.status,
            func.count(Appointment.id),
        )
        .filter(
            Appointment.appointment_time >= start,
            Appointment.appointment_time < end,
        )
        .group_by(Appointment.status)
        .all()
    )

    revenue = (
        db.query(func.coalesce(func.sum(Doctor.consultation_fee), 0))
        .join(Appointment, Appointment.doctor_id == Doctor.id)
        .filter(
            Appointment.appointment_time >= start,
            Appointment.appointment_time < end,
            Appointment.status == "COMPLETED",
        )
        .scalar()
    )

    return {
        "date": today,
        "total_appointments": total,
        "checked_in": status_counts.get("CHECKED_IN", 0),
        "completed": status_counts.get("COMPLETED", 0),
        "cancelled": status_counts.get("CANCELLED", 0),
        "no_shows": status_counts.get("NO_SHOW", 0),
        "consultation_revenue": float(revenue or 0),
    }


@router.get("/doctor-performance")
def doctor_performance(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
):
    validate_date_range(date_from, date_to)

    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to + timedelta(days=1), time.min)

    rows = (
        db.query(
            Doctor.id.label("doctor_id"),
            Doctor.name.label("doctor_name"),
            func.count(Appointment.id).label("appointments"),
            func.sum(
                case(
                    (Appointment.status == "COMPLETED", 1),
                    else_=0,
                )
            ).label("completed_consultations"),
            func.sum(
                case(
                    (Appointment.status == "NO_SHOW", 1),
                    else_=0,
                )
            ).label("no_shows"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            Appointment.status == "COMPLETED",
                            Doctor.consultation_fee,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("revenue"),
        )
        .outerjoin(
            Appointment,
            (Appointment.doctor_id == Doctor.id)
            & (Appointment.appointment_time >= start)
            & (Appointment.appointment_time < end),
        )
        .group_by(Doctor.id, Doctor.name)
        .all()
    )

    results = []
    for row in rows:
        count = row.appointments or 0
        no_shows = row.no_shows or 0

        results.append({
            "doctor_id": row.doctor_id,
            "doctor_name": row.doctor_name,
            "appointments": count,
            "completed_consultations": row.completed_consultations or 0,
            "no_shows": no_shows,
            "no_show_percentage": round(
                no_shows / count * 100, 2
            ) if count else 0,
            "revenue": float(row.revenue or 0),
        })

    return {
        "date_from": date_from,
        "date_to": date_to,
        "doctors": results,
    }


@router.get("/department-summary")
def department_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
):
    validate_date_range(date_from, date_to)

    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to + timedelta(days=1), time.min)

    rows = (
        db.query(
            Department.id.label("department_id"),
            Department.name.label("department_name"),
            func.count(Appointment.id).label("appointment_count"),
        )
        .outerjoin(Doctor, Doctor.department_id == Department.id)
        .outerjoin(
            Appointment,
            (Appointment.doctor_id == Doctor.id)
            & (Appointment.appointment_time >= start)
            & (Appointment.appointment_time < end),
        )
        .group_by(Department.id, Department.name)
        .all()
    )

    return [
        {
            "department_id": row.department_id,
            "department_name": row.department_name,
            "appointment_count": row.appointment_count,
        }
        for row in rows
    ]


@router.get("/peak-hours")
def peak_hours(
    report_date: date = Query(default=None),
    db: Session = Depends(get_db),
):
    selected_date = report_date or date.today()
    start = datetime.combine(selected_date, time.min)
    end = start + timedelta(days=1)

    rows = (
        db.query(
            extract("hour", Appointment.appointment_time).label("hour"),
            func.count(Appointment.id).label("appointment_count"),
        )
        .filter(
            Appointment.appointment_time >= start,
            Appointment.appointment_time < end,
        )
        .group_by(extract("hour", Appointment.appointment_time))
        .order_by(extract("hour", Appointment.appointment_time))
        .all()
    )

    return {
        "date": selected_date,
        "hours": [
            {
                "hour": int(row.hour),
                "appointment_count": row.appointment_count,
            }
            for row in rows
        ],
    }


@router.get("/frequent-no-shows")
def frequent_no_shows(db: Session = Depends(get_db)):
    end = datetime.now()
    start = end - timedelta(days=90)

    rows = (
        db.query(
            Patient.id.label("patient_id"),
            Patient.full_name.label("patient_name"),
            func.count(Appointment.id).label("no_show_count"),
        )
        .join(Appointment, Appointment.patient_id == Patient.id)
        .filter(
            Appointment.status == "NO_SHOW",
            Appointment.appointment_time >= start,
            Appointment.appointment_time <= end,
        )
        .group_by(Patient.id, Patient.full_name)
        .having(func.count(Appointment.id) >= 3)
        .order_by(func.count(Appointment.id).desc())
        .all()
    )

    return [
        {
            "patient_id": row.patient_id,
            "patient_name": row.patient_name,
            "no_show_count": row.no_show_count,
        }
        for row in rows
    ]
