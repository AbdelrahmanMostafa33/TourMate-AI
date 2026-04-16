import asyncio
from fastapi import WebSocket
from typing import Dict


class ConnectionManager:
    """
    بيدير كل الـ WebSocket connections في الـ memory.
    مفيش locking هنا لأنه في نفس الـ event loop.
    """

    def __init__(self):
        # trip_id → WebSocket
        self.active: Dict[str, WebSocket] = {}
        # conversation_id → asyncio.Lock  (منع race condition)
        self.locks: Dict[str, asyncio.Lock] = {}

    async def connect(self, trip_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active[trip_id] = websocket
        if trip_id not in self.locks:
            self.locks[trip_id] = asyncio.Lock()

    def disconnect(self, trip_id: str):
        self.active.pop(trip_id, None)
        # Lock بيتحذف لو مفيش connection تاني

    async def send(self, trip_id: str, data: dict):
        ws = self.active.get(trip_id)
        if ws:
            await ws.send_json(data)

    def get_lock(self, trip_id: str) -> asyncio.Lock:
        if trip_id not in self.locks:
            self.locks[trip_id] = asyncio.Lock()
        return self.locks[trip_id]


# Singleton — instance واحد لكل الـ app
manager = ConnectionManager()