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
from observability import get_logger
from services import UserContext

if TYPE_CHECKING:
    from flet.auth.user import User

log = get_logger("session")


def _find_student_by_email(email: str) -> str | None:
    if not email:
        return None
    # The campus `student` table is owned/seeded by the API service and may not exist yet on a
    # fresh DB (the server raises NotFoundError, unlike the embedded engine). Treat that as "no
    # match" so login never fails on the lookup.
    try:
        # Return the bare matric (e.g. MEC255043), not the record id (student:MEC255043) —
        # `meta::id()` strips the table prefix. The bare matric is what booking/UKB calls match on.
        rows = get_db().query(
            "SELECT meta::id(id) AS matric FROM student WHERE email = $email LIMIT 1",
            {"email": email},
        )
    except Exception:
        return None
    return str(rows[0]["matric"]) if rows else None


def resolve_user_context(user: User) -> UserContext:
    """Upsert the user and return their ``UserContext`` (user_id + linked student_id)."""
    db = get_db()
    user_id = str(user.id)
    email = str(user.get("email", "") or "")
    rid = RecordID("user", user_id)
    log.debug("resolve_user_context: user_id=%s email=%r", user_id, email)

    existing = db.query("SELECT student_id FROM $rid", {"rid": rid})
    student_id = existing[0].get("student_id") if existing else None
    if not student_id:
        student_id = _find_student_by_email(email) or DEFAULT_STUDENT_ID
        log.info("Linking %r → student_id=%s (%s)", email, student_id,
                 "existing match" if existing else "new user")

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
    log.debug("resolve_user_context: upserted user %s", user_id)
    return UserContext(user_id=user_id, student_id=str(student_id))
