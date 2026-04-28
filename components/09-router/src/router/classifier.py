"""
Intent classification components.

- BERTClassifier: calls the fine-tuned BERT /classify endpoint.
- Taxonomy: approved intent labels loaded from a file.
- StubBackend: maps intent → canned reply from a JSON file.
- UserLookup: resolves an email to a user profile from PostgreSQL.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
import httpx

logger = logging.getLogger("router")


# ── User Lookup ───────────────────────────────────────────────────────

class UserLookup:
    """Resolve email to user profile from the userinfo database."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def resolve(self, email: str) -> Optional[Dict[str, Any]]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT u.user_id, u.external_id, u.username, u.user_name, u.email,
                       s.mobile_number, s.account_number, s.status,
                       p.plan_name
                FROM users u
                LEFT JOIN subscriptions s ON u.user_id = s.user_id
                LEFT JOIN user_plans up ON s.subscription_id = up.subscription_id
                    AND CURRENT_DATE BETWEEN up.start_date AND up.end_date
                LEFT JOIN plans p ON up.plan_id = p.plan_id
                WHERE u.email = $1 OR u.username = $1 OR u.external_id = $1
                LIMIT 1
            """, email)
        if not row:
            return None
        return {
            "user_id": row["user_id"],
            "external_id": row["external_id"],
            "username": row["username"],
            "display_name": row["user_name"],
            "email": row["email"],
            "mobile_number": row["mobile_number"],
            "account_number": row["account_number"],
            "status": row["status"],
            "plan_name": row["plan_name"],
        }


# ── Taxonomy ──────────────────────────────────────────────────────────

class Taxonomy:
    """Approved intents loaded from a newline-delimited file with periodic refresh."""

    def __init__(self, path: str, refresh_interval: float = 60.0):
        self._path = path
        self._refresh_interval = refresh_interval
        self._labels: set = set()
        self._last_load: float = 0.0
        self._load()

    def _load(self) -> None:
        try:
            text = Path(self._path).read_text()
            self._labels = {
                line.strip()
                for line in text.splitlines()
                if line.strip() and not line.startswith("#")
            }
            self._last_load = time.time()
            logger.info("Loaded %d approved intents from %s", len(self._labels), self._path)
        except FileNotFoundError:
            logger.warning("Intents file not found: %s — all labels will be UNKNOWN", self._path)

    def refresh_if_needed(self) -> None:
        if time.time() - self._last_load > self._refresh_interval:
            self._load()

    def __contains__(self, label: str) -> bool:
        self.refresh_if_needed()
        return label in self._labels


# ── Stub Backend ──────────────────────────────────────────────────────

class StubBackend:
    """Maps intent → (reply, backend_data) from a JSON file.

    Rereads on every call so ConfigMap updates propagate without restart.
    """

    SYSTEM_ERROR_REPLY = (
        "ขออภัยค่ะ ระบบขัดข้อง กรุณาลองใหม่อีกครั้งค่ะ "
        "Sorry, we encountered a system error. Please try again."
    )
    UNKNOWN_REPLY = (
        "ขออภัยค่ะ ไม่เข้าใจคำถาม กรุณาลองถามใหม่อีกครั้งค่ะ "
        "I'm sorry, I didn't understand that. Could you please rephrase?"
    )

    def __init__(self, path: str):
        self._path = path

    def get_response(self, intent: str) -> tuple:
        if intent == "SYSTEM_ERROR":
            return self.SYSTEM_ERROR_REPLY, None
        if intent == "UNKNOWN":
            return self.UNKNOWN_REPLY, None

        stubs = self._read_file()
        if intent in stubs:
            entry = stubs[intent]
            return entry.get("reply", ""), entry.get("backend_data")

        return (
            f"Your request has been noted. Routing to {intent}.",
            {"type": "intent_routing", "target_system": intent},
        )

    def _read_file(self) -> dict:
        try:
            return json.loads(Path(self._path).read_text())
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("Could not load stubs from %s: %s", self._path, exc)
            return {}


# ── BERT Classifier ───────────────────────────────────────────────────

class BERTClassifier:
    """Calls the fine-tuned BERT model /classify endpoint."""

    def __init__(self, base_url: str, model: str, token: str = ""):
        self._url = f"{base_url.rstrip('/')}/classify"
        self._model = model
        self._headers = {"Content-Type": "application/json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    async def classify(self, text: str) -> tuple:
        """Return (intent_label, confidence_score)."""
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            resp = await client.post(
                self._url,
                headers=self._headers,
                json={"model": self._model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            top = data["data"][0]
            label = top["label"]
            confidence = max(top.get("probs", [0.0]))
            return label, confidence

    @staticmethod
    def build_input(history: List[Dict[str, str]], current_message: str) -> str:
        """Format session history + current message for BERT.

        Uses ``[SEP]`` to separate context from the target message,
        matching the format the model was fine-tuned on.
        """
        parts: List[str] = []
        for msg in history:
            role = msg.get("role", "user").capitalize()
            parts.append(f"{role}: {msg.get('content', '')}")

        history_str = " | ".join(parts) if parts else ""
        if history_str:
            return f"History: {history_str} [SEP] Current: {current_message}"
        return f"Current: {current_message}"
