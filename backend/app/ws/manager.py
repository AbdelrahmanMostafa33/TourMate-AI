import asyncio
from fastapi import WebSocket
from typing import Dict


class ConnectionManager:

    def __init__(self):
        # trip_id → WebSocket
        self.active: Dict[str, WebSocket] = {}
        # trip_id → Lock
        self.locks:  Dict[str, asyncio.Lock] = {}

    async def connect(self, trip_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active[trip_id] = websocket
        if trip_id not in self.locks:
            self.locks[trip_id] = asyncio.Lock()

    def disconnect(self, trip_id: str):
        self.active.pop(trip_id, None)
        self.locks.pop(trip_id, None)

    def get_lock(self, trip_id: str) -> asyncio.Lock:
        if trip_id not in self.locks:
            self.locks[trip_id] = asyncio.Lock()
        return self.locks[trip_id]

    async def send(self, trip_id: str, data: dict):
        ws = self.active.get(trip_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(trip_id)


manager = ConnectionManager()