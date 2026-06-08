"""Resolve a Flet OAuth login into a persisted user + a per-request ``UserContext``.

On each successful Google login we upsert a ``user`` record (owner of all that person's
chat/calendar/memory data) and resolve the campus ``student_id`` used by UKB/booking calls:

1. an id already linked on the ``user`` record (a returning user), else
2. a campus ``student`` whose email matches the Google email (auto-link), else
3. the demo matric fallback (``constants.DEFAULT_STUDENT_ID``) so the FOL-anchored demo works
   out of the box.

The chosen ``student_id`` is stored back on the ``user`` record, so it can later be changed
from Settings (a lightweight "confirm your matric" flow) without re-resolving every login.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from surrealdb import RecordID

from constants import DEFAULT_STUDENT_ID
from db import get_db
from services import UserContext

if TYPE_CHECKING:
    from flet.auth.user import User


def _find_student_by_email(email: str) -> str | None:
    if not email:
        return None
    # The campus `student` table is owned/seeded by the API service and may not exist yet on a
    # fresh DB (the server raises NotFoundError, unlike the embedded engine). Treat that as "no
    # match" so login never fails on the lookup.
    try:
        rows = get_db().query(
            "SELECT id FROM student WHERE email = $email LIMIT 1", {"email": email}
        )
    except Exception:
        return None
    return str(rows[0]["id"]) if rows else None


def resolve_user_context(user: User) -> UserContext:
    """Upsert the user and return their ``UserContext`` (user_id + linked student_id)."""
    db = get_db()
    user_id = str(user.id)
    email = str(user.get("email", "") or "")
    rid = RecordID("user", user_id)

    existing = db.query("SELECT student_id FROM $rid", {"rid": rid})
    student_id = existing[0].get("student_id") if existing else None
    if not student_id:
        student_id = _find_student_by_email(email) or DEFAULT_STUDENT_ID

    db.query(
        "UPSERT $rid SET email = $email, name = $name, picture = $picture, "
        "student_id = $student_id, updated_at = $now",
        {
            "rid": rid,
            "email": email,
            "name": str(user.get("name", "") or ""),
            "picture": str(user.get("picture", "") or ""),
            "student_id": student_id,
            "now": datetime.now(UTC).isoformat(),
        },
    )
    return UserContext(user_id=user_id, student_id=str(student_id))
