"""Chat session persistence, scoped per authenticated user, backed by SurrealDB.

Every session record carries an ``owner`` (``user:<id>``) link and every query filters by it,
so one user can never read or mutate another user's sessions — even by guessing a session id.
Public method signatures are unchanged from the previous TinyDB implementation; the only
difference is that a ``SessionStore`` is now constructed with the owning ``user_id``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from surrealdb import RecordID

from db import get_db, user_ref

_TABLE = "chat_session"


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SessionStore:
    def __init__(self, user_id: str):
        self._uid = user_id
        self._db = get_db()

    def _owner(self) -> RecordID:
        return user_ref(self._uid)

    def _rid(self, session_id: str) -> RecordID:
        return RecordID(_TABLE, session_id)

    def create_session(self, title: str = "New Chat") -> dict:
        now = _now()
        session = {
            "owner": self._owner(),
            "title": title,
            "session_type": "chat",  # "chat" or "checkin"
            "checkin_context": None,  # {"event_id": "...", "task_title": "...", "due_date": "..."}
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        rows = self._db.query("CREATE $rid CONTENT $data", {"rid": self._rid(str(uuid.uuid4())), "data": session})
        return rows[0]

    def get_all_sessions(self) -> list[dict]:
        return self._db.query(
            f"SELECT * FROM {_TABLE} WHERE owner = $owner ORDER BY updated_at DESC",
            {"owner": self._owner()},
        )

    def get_session(self, session_id: str) -> dict | None:
        rows = self._db.query(
            "SELECT * FROM $rid WHERE owner = $owner",
            {"rid": self._rid(session_id), "owner": self._owner()},
        )
        return rows[0] if rows else None

    def save_messages(self, session_id: str, messages: list[dict]):
        self._db.query(
            "UPDATE $rid SET messages = $messages, updated_at = $now WHERE owner = $owner",
            {"rid": self._rid(session_id), "messages": messages, "now": _now(), "owner": self._owner()},
        )

    def update_event_meta(self, session_id: str, data: dict):
        self._db.query(
            "UPDATE $rid MERGE $data WHERE owner = $owner",
            {"rid": self._rid(session_id), "data": data, "owner": self._owner()},
        )

    def update_title(self, session_id: str, title: str):
        self._db.query(
            "UPDATE $rid SET title = $title WHERE owner = $owner",
            {"rid": self._rid(session_id), "title": title, "owner": self._owner()},
        )

    def delete_session(self, session_id: str):
        self._db.query(
            "DELETE $rid WHERE owner = $owner",
            {"rid": self._rid(session_id), "owner": self._owner()},
        )
