"""Database engine and session wiring for the mock backend."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# In Docker this is provided by docker-compose; the localhost default is a dev fallback.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://maicampus:maicampus@localhost:5432/maicampus",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def wait_for_db(max_attempts: int = 30, delay: float = 2.0) -> None:
    """Block until Postgres accepts connections (compose healthcheck usually wins first)."""
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return
        except OperationalError as err:  # pragma: no cover - startup timing
            last_err = err
            print(f"[mock_server] waiting for database ({attempt}/{max_attempts})...")
            time.sleep(delay)
    raise RuntimeError(f"Database not reachable after {max_attempts} attempts: {last_err}")
