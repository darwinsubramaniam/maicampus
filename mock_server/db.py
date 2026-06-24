"""SurrealDB connection for the campus backend (UKB + Facility Booking).

Campus reference data lives in the same SurrealDB instance the Flet app uses for per-user data
(namespace ``maicampus`` / database ``app``), but in its own tables: ``lecturer``, ``student``,
``course`` (with an embedded ``timetable`` and a ``lecturer`` record link), ``club``,
``facility``, ``booking`` — plus a graph edge ``student->enrolled->course``.

A single blocking connection is shared and serialized with a lock (FastAPI runs sync endpoint
functions in a threadpool, so this is safe and simple).
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from surrealdb import RecordID, Surreal

_NS = os.environ.get("MAICAMPUS_SURREAL_NS", "maicampus")
_DB = os.environ.get("MAICAMPUS_SURREAL_DB", "app")
# In Docker this is ws://surreal:8000/rpc; the default is a local-dev fallback.
_URL = os.environ.get("MAICAMPUS_SURREAL_URL", "ws://localhost:8000/rpc")
_USER = os.environ.get("MAICAMPUS_SURREAL_USER", "root")
_PASS = os.environ.get("MAICAMPUS_SURREAL_PASS", "root")

_conn: Any = None
_lock = threading.RLock()


def _connect() -> Any:
    conn = Surreal(_URL)
    if _URL.startswith(("ws", "http")):
        conn.signin({"username": _USER, "password": _PASS})
    conn.use(_NS, _DB)
    return conn


def wait_for_db(max_attempts: int = 60, delay: float = 2.0) -> None:
    """Block until SurrealDB accepts connections (it boots alongside this service)."""
    global _conn
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            conn = _connect()
            conn.query("RETURN 1")
            with _lock:
                _conn = conn
            return
        except Exception as err:  # pragma: no cover - startup timing
            last_err = err
            print(f"[mock_server] waiting for SurrealDB ({attempt}/{max_attempts})...", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"SurrealDB not reachable after {max_attempts} attempts: {last_err}")


def _ensure() -> Any:
    global _conn
    if _conn is None:
        _conn = _connect()
    return _conn


# The real SurrealDB server is strict: SELECT from an undefined table raises NotFoundError
# (unlike the embedded engine, which returns []). Define the campus tables up front so the
# idempotent seed check and the read endpoints work on a fresh database.
_SCHEMA = [
    "DEFINE TABLE IF NOT EXISTS lecturer SCHEMALESS",
    "DEFINE TABLE IF NOT EXISTS student SCHEMALESS",
    "DEFINE TABLE IF NOT EXISTS course SCHEMALESS",
    "DEFINE TABLE IF NOT EXISTS club SCHEMALESS",
    "DEFINE TABLE IF NOT EXISTS facility SCHEMALESS",
    "DEFINE TABLE IF NOT EXISTS booking SCHEMALESS",
    "DEFINE TABLE IF NOT EXISTS enrolled SCHEMALESS",
]


def define_schema() -> None:
    for stmt in _SCHEMA:
        query(stmt)


def query(sql: str, params: dict[str, Any] | None = None) -> list[dict]:
    with _lock:
        result = _ensure().query(sql, params or {})
    return _normalize(result)


def thing(table: str, ident: Any) -> RecordID:
    return RecordID(table, ident)


def _normalize(value: Any) -> Any:
    if isinstance(value, RecordID):
        return value.id
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    return value
