"""Seed a realistic demo profile into the isolated capture store.

Run with the app's environment (so MAICAMPUS_SURREAL_URL points at the capture store) and
cwd=src (so ``from db import …`` resolves). The demo auto-login uses user id ``dev-local`` but
never writes a profile record, so the Profile screen would otherwise show empty placeholders.
This gives it a representative student identity (the FOL scenario student).
"""

from __future__ import annotations

from db import get_db, user_ref

get_db().query(
    "UPSERT $rid SET name = $name, email = $email, picture = $picture, student_id = $sid",
    {
        "rid": user_ref("dev-local"),
        "name": "Darwin Subramaniam",
        "email": "darwin@graduate.utm.my",
        "picture": "",
        "sid": "MEC255043",
    },
)
print("[seed] demo profile written")
