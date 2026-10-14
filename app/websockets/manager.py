
from collections import defaultdict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.doctor_queues = defaultdict(list)
        self.user_notifications = defaultdict(list)

    async def connect_queue(self, doctor_id: int, websocket: WebSocket):
        await websocket.accept()
        self.doctor_queues[doctor_id].append(websocket)

    def disconnect_queue(self, doctor_id: int, websocket: WebSocket):
        connections = self.doctor_queues.get(doctor_id, [])
        if websocket in connections:
            connections.remove(websocket)

    async def broadcast_queue(self, doctor_id: int, message: dict):
        for websocket in list(self.doctor_queues.get(doctor_id, [])):
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect_queue(doctor_id, websocket)

    async def connect_notifications(
        self, user_id: int, websocket: WebSocket
    ):
        await websocket.accept()
        self.user_notifications[user_id].append(websocket)

    def disconnect_notifications(self, user_id: int, websocket: WebSocket):
        connections = self.user_notifications.get(user_id, [])
        if websocket in connections:
            connections.remove(websocket)

    async def notify_user(self, user_id: int, message: dict):
        for websocket in list(self.user_notifications.get(user_id, [])):
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect_notifications(user_id, websocket)


manager = ConnectionManager()
