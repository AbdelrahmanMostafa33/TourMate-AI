import asyncio
from fastapi import WebSocket
from typing import Dict


class ConnectionManager:

    def __init__(self):
        self.active: Dict[str, WebSocket] = {}
        self.locks:  Dict[str, asyncio.Lock] = {}

    async def connect(self, key: str, websocket: WebSocket):
        """Connect new websocket (calls accept)"""
        await websocket.accept()
        self.active[key] = websocket
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

    async def connect_existing(self, key: str, websocket: WebSocket):  # ← add async
        """Re-key an already-accepted websocket to a new key.
           Used when /ws/chat/new transitions to a real trip_id."""
        self.active[key] = websocket
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

    def disconnect(self, key: str):
        """Disconnect and clean up"""
        self.active.pop(key, None)
        self.locks.pop(key, None)

    def get_lock(self, key: str) -> asyncio.Lock:
        """Get or create a lock for the given key"""
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()
        return self.locks[key]

    async def send(self, key: str, data: dict):
        """Send a JSON message to the client"""
        ws = self.active.get(key)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(key)


manager = ConnectionManager()