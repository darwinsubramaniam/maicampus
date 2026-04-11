from __future__ import annotations

import contextlib
import threading
from datetime import datetime
from typing import TYPE_CHECKING

from campus_calendar.event_model import EVENT_LABELS, event_type_from_str

if TYPE_CHECKING:
    from campus_calendar.event_store import CalendarEventStore
    from memory import MemoryManager


def index_event_to_memory(event: dict, mgr: MemoryManager | None):
    """Index a calendar event into Mem0 as a synthetic conversation turn."""
    if not mgr:
        return

    event_type = event_type_from_str(event.get("type", "custom"))
    label = EVENT_LABELS.get(event_type, "Event")
    start = datetime.fromisoformat(event["start_datetime"])
    title = event.get("title", "Untitled")

    recurrence = event.get("recurrence_rule")
    rec_text = ""
    if recurrence and recurrence != "NONE":
        days = recurrence.split(":")[1] if ":" in recurrence else ""
        rec_text = f" (recurring weekly on {days})"

    user_text = f"Add to my calendar: {title} - {label} on {start.strftime('%B %d, %Y at %I:%M %p')}{rec_text}"
    assistant_text = f"Noted! I've added '{title}' ({label}) to your calendar for {start.strftime('%B %d, %Y')}."

    def _do():
        with contextlib.suppress(Exception):
            mgr.add_turn(user_text, assistant_text)

    threading.Thread(target=_do, daemon=True).start()


def get_upcoming_context_block(store: CalendarEventStore) -> str:
    """Build a context block of upcoming events for AI system prompt."""
    upcoming = store.get_upcoming_events(days=7)
    if not upcoming:
        return ""

    lines = ["Upcoming events (next 7 days):"]
    for d, event in upcoming:
        event_type = event_type_from_str(event.get("type", "custom"))
        label = EVENT_LABELS.get(event_type, "Event").upper()
        title = event.get("title", "Untitled")
        start = datetime.fromisoformat(event["start_datetime"])
        end = datetime.fromisoformat(event["end_datetime"])

        if start == end:
            time_str = "All day"
        else:
            time_str = f"{start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}".lstrip("0").replace(" 0", " ")

        lines.append(f"- [{label}] {title} — {d.strftime('%a %b %d')}, {time_str}")

    return "\n".join(lines)
