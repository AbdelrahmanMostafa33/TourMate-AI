import asyncio
import logging
from fastapi import WebSocket
from typing import Dict


logger = logging.getLogger(__name__)


class ConnectionManager:

    def __init__(self):
        self.active: Dict[str, WebSocket] = {}
        self.locks:  Dict[str, asyncio.Lock] = {}
        # Monotonically increasing generation per key so stale tasks can
        # detect that the client has moved on (reconnected).
        self._generations: Dict[str, int] = {}

    async def connect(self, key: str, websocket: WebSocket):
        """Connect new websocket (calls accept)"""
        await websocket.accept()
        self.active[key] = websocket
        self._bump_generation(key)
        logger.info("[WSSend] Connected key=%s (active=%d)", key, len(self.active))
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

    async def connect_existing(self, key: str, websocket: WebSocket):
        """Re-key an already-accepted websocket to a new key.
           Used when /ws/chat/new transitions to a real trip_id."""
        self.active[key] = websocket
        self._bump_generation(key)
        logger.info("[WSSend] Re-keyed key=%s (active=%d)", key, len(self.active))
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

    def _bump_generation(self, key: str) -> None:
        """Increment the generation counter for the given key."""
        self._generations[key] = self._generations.get(key, 0) + 1

    def get_generation(self, key: str) -> int:
        """Return the current generation for a key (0 if never connected)."""
        return self._generations.get(key, 0)

    def is_stale(self, key: str, generation: int) -> bool:
        """Return True if the caller's generation is not the latest.

        This means the client disconnected and reconnected while a
        background task was still running for this key.
        """
        return generation != self._generations.get(key, 0)

    def disconnect(self, key: str):
        """Disconnect and clean up"""
        self.active.pop(key, None)
        self.locks.pop(key, None)
        self._generations.pop(key, None)
        logger.info("[WSSend] Disconnected key=%s (active=%d)", key, len(self.active))

    def get_lock(self, key: str) -> asyncio.Lock:
        """Get or create a lock for the given key"""
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()
        return self.locks[key]

    async def send(self, key: str, data: dict) -> bool:
        """Send a JSON message to the client.

        Returns True on success, False if the WebSocket was missing or the
        send failed (e.g. connection closed by client). On failure, the
        key is disconnected and cleaned up automatically.
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
            return False

        try:
            await ws.send_json(data)
            logger.debug(
                "[WSSend] Sent to key=%s event_type=%s",
                key,
                data.get("type") or data.get("event_type", "unknown"),
            )
            return True
        except Exception as e:
            logger.error(
                "[WSSend] FAILED to send to key=%s event_type=%s: %s",
                key,
                data.get("type") or data.get("event_type", "unknown"),
                e,
            )
            self.disconnect(key)
            return False


manager = ConnectionManager()