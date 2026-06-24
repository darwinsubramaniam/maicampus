"""SurrealDB connection + helpers — single source of truth for the per-user data layer.

Two run modes, chosen by ``MAICAMPUS_SURREAL_URL``:

* **Server** (env set, e.g. ``ws://surreal:8000/rpc``): connect over the network, sign in
  with root credentials, and select the namespace/database. This is how the Docker stack runs.
* **Local dev** (env unset): an embedded, file-backed store under ``~/.maicampus/surreal.db``
  via the ``surrealkv://`` engine bundled with the Python SDK. ``uv run flet run`` works
  fully offline — no server, no Docker.

The SurrealDB Python SDK is async-first, but every store in this app is called from
synchronous code (background streaming threads, tool execution), so we use the **blocking**
client and serialize all access through one shared connection + a re-entrant lock. That keeps
``SessionStore`` / ``CalendarEventStore`` / ``MemoryManager`` synchronous with unchanged
public signatures.

Per-user isolation is enforced by an ``owner`` field (a ``user:<id>`` record link) on every
per-user record; every query filters ``WHERE owner = $owner``. Campus relationships
(enrollments, clubs, bookings) use graph edges; AI memory uses a vector (HNSW) index.
"""

from __future__ import annotations

import os
import threading
from typing import Any

from surrealdb import RecordID, Surreal

from constants import APP_DIR

# Vector dimension of the memory embeddings. Defaults to 1536 (OpenAI text-embedding-3-small).
# Must match MAICAMPUS_EMBED_MODEL/DIM in memory/embedder.py; changing it needs a fresh DB
# (the HNSW index dimension is fixed at creation).
EMBED_DIM = int(os.environ.get("MAICAMPUS_EMBED_DIM", "1536"))

_NS = os.environ.get("MAICAMPUS_SURREAL_NS", "maicampus")
_DB_NAME = os.environ.get("MAICAMPUS_SURREAL_DB", "app")
_URL = os.environ.get("MAICAMPUS_SURREAL_URL")  # unset → embedded file-backed store
_USER = os.environ.get("MAICAMPUS_SURREAL_USER", "root")
_PASS = os.environ.get("MAICAMPUS_SURREAL_PASS", "root")

# Schema is idempotent (IF NOT EXISTS), so it is safe to (re)apply on every connect.
_SCHEMA = [
    "DEFINE TABLE IF NOT EXISTS user SCHEMALESS",
    "DEFINE TABLE IF NOT EXISTS chat_session SCHEMALESS",
    "DEFINE TABLE IF NOT EXISTS calendar_event SCHEMALESS",
    "DEFINE TABLE IF NOT EXISTS memory SCHEMALESS",
    "DEFINE TABLE IF NOT EXISTS usage_daily SCHEMALESS",
    "DEFINE INDEX IF NOT EXISTS chat_owner ON chat_session FIELDS owner",
    "DEFINE INDEX IF NOT EXISTS cal_owner ON calendar_event FIELDS owner",
    "DEFINE INDEX IF NOT EXISTS mem_owner ON memory FIELDS owner",
    f"DEFINE INDEX IF NOT EXISTS mem_vec ON memory FIELDS embedding "
    f"HNSW DIMENSION {EMBED_DIM} DIST COSINE",
]


class SurrealDB:
    """Thread-safe blocking wrapper around one SurrealDB connection."""

    def __init__(self) -> None:
        self._conn: Any = None  # a blocking SurrealDB connection (Surreal() returns a union)
        self._lock = threading.RLock()

    def _connect(self) -> Any:
        if _URL:
            conn = Surreal(_URL)
            # Network engines need authentication; embedded engines (mem/file/surrealkv) do not.
            if _URL.startswith(("ws", "http")):
                conn.signin({"username": _USER, "password": _PASS})
        else:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            conn = Surreal(f"surrealkv://{APP_DIR / 'surreal.db'}")
        conn.use(_NS, _DB_NAME)
        for stmt in _SCHEMA:
            conn.query(stmt)
        return conn

    def _ensure(self) -> Any:
        if self._conn is None:
            self._conn = self._connect()
        return self._conn

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Run a SurrealQL statement and return normalized rows (RecordID → plain values).

        Use only for a single statement that yields rows; multi-statement scripts return the
        last statement's result.
        """
        with self._lock:
            conn = self._ensure()
            result = conn.query(sql, params or {})
        return _normalize(result)

    def health(self) -> bool:
        try:
            self.query("RETURN 1")
            return True
        except Exception:
            return False

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None


_db_singleton: SurrealDB | None = None
_singleton_lock = threading.Lock()


def get_db() -> SurrealDB:
    """Return the process-wide SurrealDB handle (lazily connected)."""
    global _db_singleton
    if _db_singleton is None:
        with _singleton_lock:
            if _db_singleton is None:
                _db_singleton = SurrealDB()
    return _db_singleton


def user_ref(user_id: str) -> RecordID:
    """A ``user:<id>`` record link, used as the ``owner`` of per-user records."""
    return RecordID("user", user_id)


def _normalize(value: Any) -> Any:
    """Recursively convert SDK types to plain Python for app code.

    ``RecordID`` → its id part (e.g. ``chat_session:<uuid>`` → ``<uuid>``), so the app keeps
    treating ``id`` as the bare string/array it always was. Owner links the app ignores
    collapse the same way (harmless).
    """
    if isinstance(value, RecordID):
        return value.id
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    return value
