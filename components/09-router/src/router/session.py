"""
Session management and archival.

- SessionManager: per-user chat session stored as a single JSON blob in Redis.
- Archiver: background task that persists sessions to PostgreSQL.

Redis structure (one key per user):
    Key:   chat:{username}
    Value: JSON string —
        {
            "session_id": "a3f5c7d2-...",
            "user_id": "jessica.thompson@example.com",
            "username": "jessica_thompson",
            "session_history": [
                {"role": "user",      "content": "..."},
                {"role": "assistant", "content": "..."},
                ...
            ]
        }

PostgreSQL table:
    chat_sessions (username TEXT PK, history JSONB)
    — one row per user, overwritten on every turn.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg
import redis.asyncio as aioredis

logger = logging.getLogger("router")


# ── Redis Session Manager ─────────────────────────────────────────────

class SessionManager:
    """Per-user chat stored as a single JSON blob in Redis."""

    def __init__(self, redis_client: aioredis.Redis, max_turns: int = 5, ttl: int = 1800):
        self._r = redis_client
        self._max_turns = max_turns
        self._ttl = ttl

    @staticmethod
    def _key(username: str) -> str:
        return f"chat:{username}"

    async def get_session(self, username: str) -> Optional[Dict[str, Any]]:
        """Return the full session blob for a user, or None."""
        raw = await self._r.get(self._key(username))
        if raw:
            return json.loads(raw)
        return None

    async def get_history(self, username: str) -> List[Dict[str, str]]:
        """Return just the session_history list."""
        session = await self.get_session(username)
        if session:
            return session.get("session_history", [])
        return []

    async def get_window(self, username: str, n: int = 5) -> List[Dict[str, str]]:
        """Return the last *n* turns (n user + n assistant = 2n entries)."""
        history = await self.get_history(username)
        return history[-(n * 2):] if history else []

    async def append(
        self,
        username: str,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_content: str,
    ) -> int:
        """Append a turn, trim to max_turns, and save back with TTL.

        Returns the current length of session_history.
        """
        session = await self.get_session(username) or {
            "session_id": session_id,
            "user_id": user_id,
            "username": username,
            "session_history": [],
        }

        session["session_id"] = session_id
        session["user_id"] = user_id

        session["session_history"].append({"role": "user", "content": user_message})
        session["session_history"].append({"role": "assistant", "content": assistant_content})

        max_items = self._max_turns * 2
        session["session_history"] = session["session_history"][-max_items:]

        await self._r.set(self._key(username), json.dumps(session), ex=self._ttl)
        return len(session["session_history"])

    async def delete(self, username: str) -> None:
        await self._r.delete(self._key(username))

    async def get_ttl(self, username: str) -> int:
        return await self._r.ttl(self._key(username))

    async def scan_sessions(self) -> List[str]:
        """Return all chat keys (as usernames)."""
        usernames: List[str] = []
        async for key in self._r.scan_iter(match="chat:*"):
            k = key.decode() if isinstance(key, bytes) else key
            usernames.append(k.replace("chat:", "", 1))
        return usernames


# ── Postgres Archiver ─────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    username  TEXT PRIMARY KEY,
    history   JSONB NOT NULL
);
"""

UPSERT_SQL = """
INSERT INTO chat_sessions (username, history)
VALUES ($1, $2::jsonb)
ON CONFLICT (username) DO UPDATE SET
    history = EXCLUDED.history;
"""


class Archiver:
    """Persist chat sessions from Redis to PostgreSQL.

    One row per user — each archival overwrites the previous row.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        session_mgr: SessionManager,
        interval: int = 120,
        ttl_threshold: int = 300,
    ):
        self._pool = pool
        self._sm = session_mgr
        self._interval = interval
        self._ttl_threshold = ttl_threshold
        self._task: Optional[asyncio.Task] = None

    async def ensure_table(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_TABLE_SQL)
        logger.info("Ensured chat_sessions table exists")

    async def archive_session(
        self,
        username: str,
        delete_redis: bool = False,
    ) -> None:
        """Read the session blob from Redis and upsert into PostgreSQL."""
        session = await self._sm.get_session(username)
        if not session or not session.get("session_history"):
            return

        async with self._pool.acquire() as conn:
            await conn.execute(UPSERT_SQL, username, json.dumps(session))

        if delete_redis:
            await self._sm.delete(username)

        logger.debug("Archived chat for user %s (turns=%d)", username,
                      len(session.get("session_history", [])))

    async def _periodic_sweep(self) -> None:
        """Archive sessions whose Redis TTL is below threshold."""
        while True:
            try:
                await asyncio.sleep(self._interval)
                usernames = await self._sm.scan_sessions()
                for uname in usernames:
                    ttl = await self._sm.get_ttl(uname)
                    if 0 < ttl < self._ttl_threshold:
                        logger.info("Periodic archive: user %s (ttl=%d)", uname, ttl)
                        await self.archive_session(uname)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Periodic archiver error")

    def start(self) -> None:
        self._task = asyncio.create_task(self._periodic_sweep())
        logger.info(
            "Periodic archiver started (interval=%ds, ttl_threshold=%ds)",
            self._interval, self._ttl_threshold,
        )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Periodic archiver stopped")

    async def archive_all_remaining(self) -> None:
        """Graceful shutdown: archive every active session to Postgres."""
        usernames = await self._sm.scan_sessions()
        for uname in usernames:
            try:
                await self.archive_session(uname)
            except Exception:
                logger.exception("Failed to archive session for user %s during shutdown", uname)
        logger.info("Archived %d remaining sessions on shutdown", len(usernames))
