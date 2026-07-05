import asyncio
import logging
from fastapi import WebSocket
from typing import Dict


logger = logging.getLogger(__name__)


class ConnectionManager:

    def __init__(self):
        self.active: Dict[str, WebSocket] = {}
        self.locks:  Dict[str, asyncio.Lock] = {}

    async def connect(self, key: str, websocket: WebSocket):
        """Connect new websocket (calls accept)"""
        await websocket.accept()
        self.active[key] = websocket
        logger.info("[WSSend] Connected key=%s (active=%d)", key, len(self.active))
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

    async def connect_existing(self, key: str, websocket: WebSocket):
        """Re-key an already-accepted websocket to a new key.
           Used when /ws/chat/new transitions to a real trip_id."""
        self.active[key] = websocket
        logger.info("[WSSend] Re-keyed key=%s (active=%d)", key, len(self.active))
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

    def disconnect(self, key: str):
        """Disconnect and clean up"""
        self.active.pop(key, None)
        self.locks.pop(key, None)
        logger.info("[WSSend] Disconnected key=%s (active=%d)", key, len(self.active))

    def get_lock(self, key: str) -> asyncio.Lock:
        """Get or create a lock for the given key"""
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()
        return self.locks[key]

    async def send(self, key: str, data: dict):
        """Send a JSON message to the client.

        If the WebSocket is not found for the given key, logs a warning.
        If sending fails (e.g. connection closed), disconnects the key
        and logs the error with full context.
        """
        ws = self.active.get(key)
        if not ws:
            logger.warning(
                "[WSSend] No active WebSocket for key=%s — dropping event type=%s "
                "(active keys: %s)",
                key,
                data.get("type") or data.get("event_type", "unknown"),
                list(self.active.keys()),
            )
            return

        try:
            await ws.send_json(data)
            logger.debug(
                "[WSSend] Sent to key=%s event_type=%s",
                key,
                data.get("type") or data.get("event_type", "unknown"),
            )
        except Exception as e:
            logger.error(
                "[WSSend] FAILED to send to key=%s event_type=%s: %s",
                key,
                data.get("type") or data.get("event_type", "unknown"),
                e,
            )
            self.disconnect(key)


manager = ConnectionManager()