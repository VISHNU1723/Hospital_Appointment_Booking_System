
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.auth.security import SECRET_KEY, ALGORITHM
from app.database import SessionLocal
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.user import User
from app.websockets.manager import manager
from app.models.patient import Patient


router = APIRouter(tags=["Live Queue"])


def get_websocket_user(token: str, db: Session):
    try:
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM]
        )
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        return None

    return db.query(User).filter(User.id == user_id).first()


def get_today_queue(db: Session, doctor_id: int):
    start = datetime.combine(date.today(), time.min)
    end = start + timedelta(days=1)

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_time >= start,
            Appointment.appointment_time < end,
            Appointment.status.in_(
                ["BOOKED", "CHECKED_IN", "IN_CONSULTATION", "IN CONSULTATION"]
            ),
        )
        .order_by(Appointment.appointment_time.asc(), Appointment.id.asc())
        .all()
    )

    return appointments


def queue_payload(db: Session, doctor_id: int, user_id: int | None = None):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    appointments = get_today_queue(db, doctor_id)

    current = next(
        (a for a in appointments if a.status == "IN CONSULTATION"),
        None,
    )
    waiting = [
        a for a in appointments
        if a.status in ("BOOKED", "CHECKED_IN")
    ]

    payload = {
        "type": "queue_update",
        "doctor_id": doctor_id,
        "current_token": current.id if current else None,
        "waiting_count": len(waiting),
        "waiting": [
            {"appointment_id": a.id, "appointment_time": a.appointment_time.isoformat()}
            for a in waiting
        ],
    }

    if user_id is not None:
        patient = (
            db.query(Patient)
            .filter(Patient.user_id == user_id)
            .first()
        )

        own = None
        if patient:
            own = next(
                (
                    a for a in appointments
                    if a.patient_id == patient.id
                    and a.status in ("BOOKED", "CHECKED_IN")
                ),
                None,
            )
        if own:
            ahead = sum(
                1 for a in waiting
                if (a.appointment_time, a.id)
                < (own.appointment_time, own.id)
            )

            payload["your_appointment_id"] = own.id
            payload["position"] = ahead + 1
            payload["estimated_wait_minutes"] = (
                ahead * (doctor.slot_duration_minutes if doctor else 15)
            )

            if ahead == 0:
                payload["your_turn_next"] = True
            else:
                payload["your_turn_next"] = False

    return payload


@router.websocket("/ws/queue/{doctor_id}")
async def doctor_queue(websocket: WebSocket, doctor_id: int, token: str):
    db = SessionLocal()
    user = get_websocket_user(token, db)

    if not user:
        db.close()
        await websocket.close(code=1008)
        return

    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        db.close()
        await websocket.close(code=1008)
        return

    await manager.connect_queue(doctor_id, websocket)

    try:
        await websocket.send_json(queue_payload(db, doctor_id, user.id))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_queue(doctor_id, websocket)
        db.close()


@router.websocket("/ws/notifications")
async def personal_notifications(websocket: WebSocket, token: str):
    db = SessionLocal()
    user = get_websocket_user(token, db)

    if not user:
        db.close()
        await websocket.close(code=1008)
        return

    await manager.connect_notifications(user.id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_notifications(user.id, websocket)
        db.close()
