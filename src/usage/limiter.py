"""Per-user daily AI usage limits, tracked in SurrealDB.

Each user gets one ``usage_daily`` record per calendar day, keyed by ``[user_id, "YYYY-MM-DD"]``
so counters self-reset at midnight (no cron). The chat path calls ``check_and_increment`` before
streaming; once the day's request count reaches ``DAILY_LIMIT`` the call is refused with a
friendly message instead of hitting the (server-funded) AI provider.

The SurrealDB wrapper serializes all queries process-wide, so the read-then-write here is atomic
within a single app process. Multiple webapp replicas would need a server-side conditional UPDATE;
that is a noted hardening step, not required for the current single-process deployment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime

from surrealdb import RecordID

from db import get_db, user_ref

DAILY_LIMIT = int(os.environ.get("MAICAMPUS_DAILY_LIMIT", "50"))

_TABLE = "usage_daily"


@dataclass
class UsageStatus:
    allowed: bool
    used: int
    limit: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


def _rid(user_id: str) -> RecordID:
    return RecordID(_TABLE, [user_id, date.today().isoformat()])


def check_and_increment(user_id: str) -> UsageStatus:
    """Reserve one request for ``user_id`` today. If already at the limit, returns
    ``allowed=False`` and does not increment."""
    db = get_db()
    rid = _rid(user_id)
    rows = db.query("SELECT requests FROM $rid", {"rid": rid})
    used = int(rows[0]["requests"]) if rows and rows[0].get("requests") is not None else 0

    if used >= DAILY_LIMIT:
        return UsageStatus(allowed=False, used=used, limit=DAILY_LIMIT)

    db.query(
        "UPSERT $rid SET requests = $requests, owner = $owner, day = $day, updated_at = $now",
        {
            "rid": rid,
            "requests": used + 1,
            "owner": user_ref(user_id),
            "day": date.today().isoformat(),
            "now": datetime.now(UTC).isoformat(),
        },
    )
    return UsageStatus(allowed=True, used=used + 1, limit=DAILY_LIMIT)


def record_tokens(user_id: str, tokens: int) -> None:
    """Best-effort accounting of streamed tokens for the day (does not gate)."""
    if tokens <= 0:
        return
    db = get_db()
    rid = _rid(user_id)
    rows = db.query("SELECT tokens FROM $rid", {"rid": rid})
    current = int(rows[0]["tokens"]) if rows and rows[0].get("tokens") is not None else 0
    db.query("UPSERT $rid SET tokens = $tokens", {"rid": rid, "tokens": current + tokens})
