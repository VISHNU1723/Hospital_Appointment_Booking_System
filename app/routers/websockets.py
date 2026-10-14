
from datetime import date, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.auth.security import SECRET_KEY, ALGORITHM
from app.database import SessionLocal
from app.models.user import User
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.websockets.manager import manager

router = APIRouter()


def get_user_from_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        return db.query(User).filter(User.id == user_id).first()
    except (JWTError, ValueError, TypeError):
        return None


@router.websocket("/ws/queue/{doctor_id}")
async def doctor_queue(websocket: WebSocket, doctor_id: int, token: str):
    db: Session = SessionLocal()
    user = get_user_from_token(token, db)

    if not user:
        print("WebSocket authentication failed: token did not resolve to a user")
        db.close()
        await websocket.close(code=1008)
        return

    try:
        await manager.connect_queue(doctor_id, websocket)

        doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_time >= datetime.combine(date.today(), datetime.min.time()),
                Appointment.appointment_time < datetime.combine(date.today(), datetime.max.time()),
                Appointment.status.in_(["CHECKED_IN", "IN_CONSULTATION"]),
            )
            .order_by(Appointment.appointment_time, Appointment.id)
            .all()
        )

        current = next(
            (a for a in appointments if a.status == "IN_CONSULTATION"), None
        )
        waiting = [a for a in appointments if a.status == "CHECKED_IN"]

        own_appointment = None
        if user.role == "PATIENT":
            patient = next(
                (p for p in user.__dict__.get("patient", []) if p), None
            )
            if patient:
                own_appointment = next(
                    (a for a in waiting if a.patient_id == patient.id), None
                )

        position = None
        wait_minutes = None
        if own_appointment:
            position = waiting.index(own_appointment) + 1
            wait_minutes = (position - 1) * (
                doctor.slot_duration_minutes if doctor else 15
            )

        await websocket.send_json({
            "type": "queue_update",
            "doctor_id": doctor_id,
            "current_token": current.id if current else None,
            "waiting_count": len(waiting),
            "waiting": [
                {"appointment_id": a.id, "appointment_time": a.appointment_time.isoformat()}
                for a in waiting
            ],
            "your_appointment_id": own_appointment.id if own_appointment else None,
            "position": position,
            "estimated_wait_minutes": wait_minutes,
        })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect_queue(doctor_id, websocket)
    finally:
        db.close()


@router.websocket("/ws/notifications")
async def personal_notifications(websocket: WebSocket, token: str):
    db = SessionLocal()
    user = get_user_from_token(token, db)

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
