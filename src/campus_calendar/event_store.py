"""Calendar event persistence, scoped per authenticated user, backed by SurrealDB.

Every event record carries an ``owner`` (``user:<id>``) link; all reads/writes filter by it,
so calendars are fully isolated between users. Recurrence expansion stays in Python
(``expand_occurrences``) exactly as before — SurrealDB just replaces the TinyDB file. Public
signatures are unchanged apart from the new ``user_id`` constructor argument.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from surrealdb import RecordID

from campus_calendar.event_model import expand_occurrences
from db import get_db, user_ref

_TABLE = "calendar_event"


def _now() -> str:
    return datetime.now(UTC).isoformat()


class CalendarEventStore:
    def __init__(self, user_id: str):
        self._uid = user_id
        self._db = get_db()

    def _owner(self) -> RecordID:
        return user_ref(self._uid)

    def _rid(self, event_id: str) -> RecordID:
        return RecordID(_TABLE, event_id)

    def create_event(self, data: dict) -> dict:
        now = _now()
        event = {
            "owner": self._owner(),
            "title": data.get("title", ""),
            "type": data.get("type", "custom"),
            "start_datetime": data.get("start_datetime", now),
            "end_datetime": data.get("end_datetime", data.get("start_datetime", now)),
            "recurrence_rule": data.get("recurrence_rule"),
            "recurrence_end_date": data.get("recurrence_end_date"),
            "description": data.get("description", ""),
            "color": data.get("color", ""),
            "status": data.get("status"),
            "time_estimate_hours": data.get("time_estimate_hours"),
            "actual_hours_spent": data.get("actual_hours_spent"),
            "priority": data.get("priority"),
            "subject": data.get("subject"),
            "completed_at": data.get("completed_at"),
            "created_at": now,
            "updated_at": now,
        }
        rows = self._db.query("CREATE $rid CONTENT $data", {"rid": self._rid(str(uuid.uuid4())), "data": event})
        return rows[0]

    def get_event(self, event_id: str) -> dict | None:
        rows = self._db.query(
            "SELECT * FROM $rid WHERE owner = $owner",
            {"rid": self._rid(event_id), "owner": self._owner()},
        )
        return rows[0] if rows else None

    def get_all_events(self) -> list[dict]:
        return self._db.query(f"SELECT * FROM {_TABLE} WHERE owner = $owner", {"owner": self._owner()})

    def get_events_for_date(self, target: date) -> list[dict]:
        """Get all events (including recurring) that occur on a specific date."""
        result = []
        for event in self.get_all_events():
            if expand_occurrences(event, target, target):
                result.append(event)
        result.sort(key=lambda e: e.get("start_datetime", ""))
        return result

    def get_events_in_range(self, start: date, end: date) -> dict[date, list[dict]]:
        """Get events grouped by date for a date range (expanding recurrences)."""
        by_date: dict[date, list[dict]] = {}
        for event in self.get_all_events():
            for d in expand_occurrences(event, start, end):
                by_date.setdefault(d, []).append(event)
        for events in by_date.values():
            events.sort(key=lambda e: e.get("start_datetime", ""))
        return by_date

    def get_upcoming_events(self, days: int = 7) -> list[tuple[date, dict]]:
        """Get upcoming events as (date, event) pairs sorted by date."""
        today = date.today()
        end = today + timedelta(days=days)
        by_date = self.get_events_in_range(today, end)
        result = []
        for d in sorted(by_date):
            for event in by_date[d]:
                result.append((d, event))
        return result

    def update_event(self, event_id: str, data: dict):
        data = {**data, "updated_at": _now()}
        self._db.query(
            "UPDATE $rid MERGE $data WHERE owner = $owner",
            {"rid": self._rid(event_id), "data": data, "owner": self._owner()},
        )

    def get_actionable_tasks(self, days: int = 14) -> list[tuple[date, dict]]:
        """Get upcoming assignments/exams that need attention."""
        upcoming = self.get_upcoming_events(days=days)
        return [
            (d, e) for d, e in upcoming if e.get("type") in ("assignment", "exam") and e.get("status") != "completed"
        ]

    def delete_event(self, event_id: str):
        self._db.query(
            "DELETE $rid WHERE owner = $owner",
            {"rid": self._rid(event_id), "owner": self._owner()},
        )
