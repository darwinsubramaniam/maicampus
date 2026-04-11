import threading
import uuid
from datetime import UTC, date, datetime, timedelta

from tinydb import Query, TinyDB

from campus_calendar.event_model import expand_occurrences
from constants import CALENDAR_DB_PATH

_DB_PATH = CALENDAR_DB_PATH


class CalendarEventStore:
    def __init__(self):
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._db = TinyDB(str(_DB_PATH))
        self._lock = threading.Lock()
        self._q = Query()

    def create_event(self, data: dict) -> dict:
        now = datetime.now(UTC).isoformat()
        event = {
            "id": str(uuid.uuid4()),
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
        with self._lock:
            self._db.insert(event)
        return event

    def get_event(self, event_id: str) -> dict | None:
        with self._lock:
            results = self._db.search(self._q.id == event_id)
        return results[0] if results else None

    def get_all_events(self) -> list[dict]:
        with self._lock:
            return self._db.all()  # type: ignore[return-value]

    def get_events_for_date(self, target: date) -> list[dict]:
        """Get all events (including recurring) that occur on a specific date."""
        all_events = self.get_all_events()
        result = []
        for event in all_events:
            dates = expand_occurrences(event, target, target)
            if dates:
                result.append(event)
        result.sort(key=lambda e: e.get("start_datetime", ""))
        return result

    def get_events_in_range(self, start: date, end: date) -> dict[date, list[dict]]:
        """Get events grouped by date for a date range (expanding recurrences)."""
        all_events = self.get_all_events()
        by_date: dict[date, list[dict]] = {}
        for event in all_events:
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
        data["updated_at"] = datetime.now(UTC).isoformat()
        with self._lock:
            self._db.update(data, self._q.id == event_id)

    def get_actionable_tasks(self, days: int = 14) -> list[tuple[date, dict]]:
        """Get upcoming assignments/exams that need attention."""
        upcoming = self.get_upcoming_events(days=days)
        return [
            (d, e) for d, e in upcoming if e.get("type") in ("assignment", "exam") and e.get("status") != "completed"
        ]

    def delete_event(self, event_id: str):
        with self._lock:
            self._db.remove(self._q.id == event_id)
