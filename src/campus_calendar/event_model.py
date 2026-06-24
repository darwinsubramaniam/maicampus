import re
from datetime import date, datetime, timedelta
from enum import Enum


class EventType(Enum):
    CLASS = "class"
    ASSIGNMENT = "assignment"
    EXAM = "exam"
    CLUB = "club"
    CUSTOM = "custom"


class EventStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"


EVENT_COLORS = {
    EventType.CLASS: "#1565C0",
    EventType.ASSIGNMENT: "#E65100",
    EventType.EXAM: "#B71C1C",
    EventType.CLUB: "#2E7D32",
    EventType.CUSTOM: "#6A1B9A",
}

EVENT_LABELS = {
    EventType.CLASS: "Class",
    EventType.ASSIGNMENT: "Assignment",
    EventType.EXAM: "Exam",
    EventType.CLUB: "Club",
    EventType.CUSTOM: "Event",
}

_DAY_MAP = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def parse_recurrence(rule: str | None) -> list[int]:
    """Parse 'WEEKLY:MO,WE' into weekday ints (0=Mon)."""
    if not rule or rule == "NONE":
        return []
    parts = rule.split(":")
    if len(parts) != 2 or parts[0] != "WEEKLY":
        return []
    return [_DAY_MAP[d] for d in parts[1].split(",") if d in _DAY_MAP]


def expand_occurrences(event: dict, window_start: date, window_end: date) -> list[date]:
    """Expand an event into concrete dates within the given window."""
    start_dt = datetime.fromisoformat(event["start_datetime"])
    event_date = start_dt.date()

    rule = event.get("recurrence_rule")
    if not rule or rule == "NONE":
        if window_start <= event_date <= window_end:
            return [event_date]
        return []

    weekdays = parse_recurrence(rule)
    if not weekdays:
        if window_start <= event_date <= window_end:
            return [event_date]
        return []

    rec_end = window_end
    if event.get("recurrence_end_date"):
        rec_end = min(rec_end, date.fromisoformat(event["recurrence_end_date"]))

    scan_start = max(event_date, window_start)
    results = []
    current = scan_start
    while current <= min(window_end, rec_end):
        if current.weekday() in weekdays:
            results.append(current)
        current += timedelta(days=1)

    return results


def event_time_str(event: dict) -> str:
    """Format event time as 'HH:MM AM - HH:MM PM' or 'All day'."""
    start = datetime.fromisoformat(event["start_datetime"])
    end = datetime.fromisoformat(event["end_datetime"])
    if start == end:
        return "All day"
    return f"{start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}".lstrip("0").replace(" 0", " ")


def event_type_from_str(s: str) -> EventType:
    try:
        return EventType(s)
    except ValueError:
        return EventType.CUSTOM


# Description marker used by older booking mirrors that predate the structured ``booking_id``
# field (e.g. "Facility booking #12 at Library Room A.").
_BOOKING_DESC_RE = re.compile(r"#(\d+) at ")


def booking_id_of(event: dict) -> int | None:
    """Return the facility booking id this calendar event mirrors, or ``None`` for a normal event.

    Booking mirrors carry a structured ``booking_id`` field; events created before that field
    existed only encode it in the description, so we fall back to parsing that marker. This is
    the single source of truth for "is this event a facility booking?" across the UI and tools.
    """
    bid = event.get("booking_id")
    if bid is not None:
        try:
            return int(bid)
        except (TypeError, ValueError):
            return None
    match = _BOOKING_DESC_RE.search(event.get("description") or "")
    return int(match.group(1)) if match else None
