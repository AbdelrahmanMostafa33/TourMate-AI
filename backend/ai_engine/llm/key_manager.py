"""
Key Manager — multi-key rotation with rate-limit awareness.

Set comma-separated API keys in your .env to enable automatic fallback::

    GOOGLE_API_KEY=key1,key2,key3
    GROQ_API_KEY=key1,key2,key3

When a key hits a 429 rate limit, ``invoke_with_fallback`` tries the next key.
Keys are never marked globally exhausted — callers track failed keys locally.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ai_engine.llm.config import Provider

logger = logging.getLogger(__name__)


class KeyManager:
    """
    Manages multiple API keys per provider with round-robin rotation.

    Keys are never marked globally exhausted — callers track failed keys
    locally per retry sequence. ``get_key()`` returns the next available
    key via round-robin, providing ``None`` only when no keys are
    registered for the provider.
    """

    def __init__(self) -> None:
        self._keys: Dict[Provider, List[str]] = {}
        self._rr_index: Dict[Provider, int] = {}

    def register_keys(self, provider: Provider, raw: str) -> None:
        """Parse a comma-separated key string and register the keys."""
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        self._keys[provider] = keys
        self._rr_index[provider] = 0
        if keys:
            logger.info(
                "[KeyManager] Registered %d key(s) for %s",
                len(keys), provider.value,
            )

    def get_key(self, provider: Provider) -> Optional[str]:
        """Return the next available key for *provider* via round-robin."""
        keys = self._keys.get(provider, [])
        if not keys:
            return None

        idx = self._rr_index.get(provider, 0)
        key = keys[idx]
        self._rr_index[provider] = (idx + 1) % len(keys)
        return key

    def get_available_count(self, provider: Provider) -> int:
        """Number of registered keys for *provider*."""
        return len(self._keys.get(provider, []))

    def get_total_count(self, provider: Provider) -> int:
        """Total registered keys for *provider*."""
        return len(self._keys.get(provider, []))


# ── Singleton key manager ────────────────────────────────────────────────────

key_manager = KeyManager()


def _init_key_manager() -> None:
    """Parse env vars and register keys for all providers."""
    from app.core.config import settings

    key_manager.register_keys(Provider.GEMINI, settings.google_api_key)
    key_manager.register_keys(Provider.GROQ, settings.groq_api_key)


# Run once on import
_init_key_manager()
