"""Redis session cache management for the interview module.

Provides context caching, distributed locking, and async task status
tracking for active interview sessions.
"""

from __future__ import annotations

import json
from typing import Any, Optional

# Default TTLs
CONTEXT_TTL = 7200  # 2 hours
LOCK_TTL = 30  # 30 seconds


class SessionCache:
    """Redis-backed session cache with distributed locking.

    Accepts a Redis client (or compatible async interface). When no client
    is provided, falls back to an in-memory dict for testing.
    """

    def __init__(self, redis_client: Any = None) -> None:
        self._redis = redis_client
        # In-memory fallback for testing
        self._mem: dict[str, Any] = {}
        self._locks: set[str] = set()

    # ------------------------------------------------------------------
    # Context management
    # ------------------------------------------------------------------

    def _ctx_key(self, session_id: str) -> str:
        return f"interview:session:{session_id}:context"

    async def load_context(self, session_id: str) -> Optional[dict[str, Any]]:
        """Load session context from cache."""
        key = self._ctx_key(session_id)
        if self._redis:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        return self._mem.get(key)

    async def save_context(self, session_id: str, context: dict[str, Any]) -> None:
        """Save session context with TTL refresh."""
        key = self._ctx_key(session_id)
        if self._redis:
            await self._redis.setex(key, CONTEXT_TTL, json.dumps(context))
        else:
            self._mem[key] = context

    async def delete_context(self, session_id: str) -> None:
        """Remove session context from cache."""
        key = self._ctx_key(session_id)
        if self._redis:
            await self._redis.delete(key)
        else:
            self._mem.pop(key, None)

    # ------------------------------------------------------------------
    # Distributed lock
    # ------------------------------------------------------------------

    def _lock_key(self, session_id: str) -> str:
        return f"interview:session:{session_id}:lock"

    async def acquire_lock(self, session_id: str) -> bool:
        """Try to acquire a session lock (NX mode, TTL 30s)."""
        key = self._lock_key(session_id)
        if self._redis:
            return bool(await self._redis.set(key, 1, nx=True, ex=LOCK_TTL))
        if key in self._locks:
            return False
        self._locks.add(key)
        return True

    async def release_lock(self, session_id: str) -> None:
        """Release a session lock."""
        key = self._lock_key(session_id)
        if self._redis:
            await self._redis.delete(key)
        else:
            self._locks.discard(key)

    # ------------------------------------------------------------------
    # Task status
    # ------------------------------------------------------------------

    def _task_key(self, task_id: str) -> str:
        return f"interview:task:{task_id}:status"

    async def update_task_status(
        self, task_id: str, status: str, result: dict | None = None
    ) -> None:
        """Update async task status in cache."""
        key = self._task_key(task_id)
        payload = {"status": status, "result": result or {}}
        if self._redis:
            await self._redis.setex(key, CONTEXT_TTL, json.dumps(payload))
        else:
            self._mem[key] = payload

    async def get_task_status(self, task_id: str) -> Optional[dict[str, Any]]:
        """Get async task status from cache."""
        key = self._task_key(task_id)
        if self._redis:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        return self._mem.get(key)
