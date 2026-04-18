import asyncio
from fastapi import WebSocket
from typing import Dict


class ConnectionManager:

    def __init__(self):
        # key → WebSocket  (key = trip_id أو "new_" + user_id)
        self.active: Dict[str, WebSocket] = {}
        # key → Lock
        self.locks:  Dict[str, asyncio.Lock] = {}

    async def connect(self, key: str, websocket: WebSocket):
        """وصّل websocket جديد (بيعمل accept)"""
        await websocket.accept()
        self.active[key] = websocket
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

    def connect_existing(self, key: str, websocket: WebSocket):
        """ربط websocket موجود بـ key جديد (من غير accept)
           بيتستخدم لما الـ chat/new يتحول لـ trip_id"""
        self.active[key] = websocket
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

    def disconnect(self, key: str):
        """فصل الاتصال"""
        self.active.pop(key, None)
        self.locks.pop(key, None)

    def get_lock(self, key: str) -> asyncio.Lock:
        """جيب الـ lock (أو أنشئ واحد جديد)"""
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()
        return self.locks[key]

    async def send(self, key: str, data: dict):
        """بعت رسالة JSON للـ client"""
        ws = self.active.get(key)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(key)


manager = ConnectionManager()