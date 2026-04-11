import threading
import uuid
from datetime import UTC, datetime

from tinydb import Query, TinyDB

from constants import CHAT_DB_PATH

_DB_PATH = CHAT_DB_PATH


class SessionStore:
    def __init__(self):
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._db = TinyDB(str(_DB_PATH))
        self._lock = threading.Lock()
        self._q = Query()

    def create_session(self, title: str = "New Chat") -> dict:
        now = datetime.now(UTC).isoformat()
        session = {
            "id": str(uuid.uuid4()),
            "title": title,
            "session_type": "chat",  # "chat" or "checkin"
            "checkin_context": None,  # {"event_id": "...", "task_title": "...", "due_date": "..."}
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        with self._lock:
            self._db.insert(session)
        return session

    def get_all_sessions(self) -> list[dict]:
        with self._lock:
            sessions = self._db.all()  # type: ignore[return-value]
        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return sessions  # type: ignore[return-value]

    def get_session(self, session_id: str) -> dict | None:
        with self._lock:
            results = self._db.search(self._q.id == session_id)
        return results[0] if results else None

    def save_messages(self, session_id: str, messages: list[dict]):
        with self._lock:
            self._db.update(
                {
                    "messages": messages,
                    "updated_at": datetime.now(UTC).isoformat(),
                },
                self._q.id == session_id,
            )

    def update_event_meta(self, session_id: str, data: dict):
        with self._lock:
            self._db.update(data, self._q.id == session_id)

    def update_title(self, session_id: str, title: str):
        with self._lock:
            self._db.update({"title": title}, self._q.id == session_id)

    def delete_session(self, session_id: str):
        with self._lock:
            self._db.remove(self._q.id == session_id)
