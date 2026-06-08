from datetime import UTC, date, datetime

from campus_calendar.calendar_memory import index_event_to_memory
from campus_calendar.event_model import EVENT_COLORS, EVENT_LABELS, event_time_str, event_type_from_str
from services import get_calendar_store as _get_store
from services import get_memory_manager as _get_mgr
from tools import ToolDefinition, register


def _handle_create_event(args: dict) -> dict:
    d = args.get("date", date.today().isoformat())
    st = args.get("start_time", "09:00")
    et = args.get("end_time", "10:00")

    try:
        sh, sm = map(int, st.split(":"))
        eh, em = map(int, et.split(":"))
    except (ValueError, AttributeError):
        return {"error": "Invalid time format. Use HH:MM."}

    start_dt = datetime(int(d[:4]), int(d[5:7]), int(d[8:10]), sh, sm, tzinfo=UTC)
    end_dt = datetime(int(d[:4]), int(d[5:7]), int(d[8:10]), eh, em, tzinfo=UTC)

    event_type = args.get("type", "custom")
    et_enum = event_type_from_str(event_type)
    rec = args.get("recurrence")
    if rec and rec.upper() == "NONE":
        rec = None

    event_data = {
        "title": args.get("title", "Untitled"),
        "type": event_type,
        "start_datetime": start_dt.isoformat(),
        "end_datetime": end_dt.isoformat(),
        "recurrence_rule": rec,
        "description": args.get("description", ""),
        "color": EVENT_COLORS.get(et_enum, EVENT_COLORS[et_enum]),
    }

    event = _get_store().create_event(event_data)
    index_event_to_memory(event, _get_mgr())

    return {
        "success": True,
        "event_id": event["id"],
        "title": event["title"],
        "message": f"Event '{event['title']}' has been added to the calendar.",
    }


def _handle_get_upcoming(args: dict) -> dict:
    days = int(args.get("days", 7))
    upcoming = _get_store().get_upcoming_events(days=days)

    events = []
    for d, event in upcoming:
        et = event_type_from_str(event.get("type", "custom"))
        events.append(
            {
                "event_id": event.get("id", ""),
                "date": d.isoformat(),
                "title": event.get("title", ""),
                "type": EVENT_LABELS.get(et, "Event"),
                "time": event_time_str(event),
            }
        )

    return {"events": events, "count": len(events)}


def _handle_get_events_for_date(args: dict) -> dict:
    target = date.fromisoformat(args.get("date", date.today().isoformat()))
    events_list = _get_store().get_events_for_date(target)

    events = []
    for event in events_list:
        et = event_type_from_str(event.get("type", "custom"))
        events.append(
            {
                "event_id": event.get("id", ""),
                "title": event.get("title", ""),
                "type": EVENT_LABELS.get(et, "Event"),
                "time": event_time_str(event),
                "description": event.get("description", ""),
            }
        )

    return {"date": target.isoformat(), "events": events, "count": len(events)}


def _handle_delete_event(args: dict) -> dict:
    store = _get_store()
    event_id = args.get("event_id")

    # Preferred path: delete a specific event by id.
    if event_id:
        event = store.get_event(event_id)
        if not event:
            return {"success": False, "error": f"No event found with id '{event_id}'."}
        store.delete_event(event_id)
        return {
            "success": True,
            "deleted_count": 1,
            "deleted": [{"event_id": event_id, "title": event.get("title", "")}],
            "message": f"Deleted '{event.get('title', 'event')}' from the calendar.",
        }

    # Fallback: delete by title (case-insensitive), optionally narrowed to a date.
    title = (args.get("title") or "").strip()
    if not title:
        return {"success": False, "error": "Provide either an event_id or a title to delete."}

    date_filter = args.get("date")
    if date_filter:
        try:
            candidates = store.get_events_for_date(date.fromisoformat(date_filter))
        except ValueError:
            return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}
    else:
        candidates = store.get_all_events()

    title_lower = title.lower()
    matches = [e for e in candidates if e.get("title", "").lower() == title_lower]
    if not matches:
        return {"success": False, "error": f"No events found matching title '{title}'."}

    deleted = []
    for e in matches:
        store.delete_event(e["id"])
        deleted.append({"event_id": e["id"], "title": e.get("title", "")})

    scope = f" on {date_filter}" if date_filter else ""
    return {
        "success": True,
        "deleted_count": len(deleted),
        "deleted": deleted,
        "message": f"Deleted {len(deleted)} event(s) titled '{title}'{scope} from the calendar.",
    }


# Register tools
register(
    ToolDefinition(
        name="create_calendar_event",
        description=(
            "Create a new event in the student's calendar. Use this when the student wants to add"
            " a class, assignment, exam, club activity, or any event to their schedule."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Name of the event (e.g. 'Math 101', 'Physics Lab Report')"},
                "date": {"type": "string", "description": "Event date in YYYY-MM-DD format"},
                "start_time": {"type": "string", "description": "Start time in HH:MM 24-hour format"},
                "end_time": {"type": "string", "description": "End time in HH:MM 24-hour format"},
                "type": {
                    "type": "string",
                    "description": "Type of event",
                    "enum": ["class", "assignment", "exam", "club", "custom"],
                },
                "recurrence": {
                    "type": "string",
                    "description": (
                        "Recurrence rule. Use WEEKLY:MO,WE for weekly on Monday and Wednesday,"
                        " or NONE for one-time events."
                    ),
                },
                "description": {"type": "string", "description": "Optional description or notes"},
            },
            "required": ["title", "date", "start_time", "end_time", "type"],
        },
        handler=_handle_create_event,
    )
)

register(
    ToolDefinition(
        name="get_upcoming_events",
        description=(
            "Get the student's upcoming calendar events for the next N days."
            " Use this to check schedule, find conflicts, or answer questions about what's coming up."
        ),
        parameters={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Number of days to look ahead (default: 7)"},
            },
            "required": [],
        },
        handler=_handle_get_upcoming,
    )
)

register(
    ToolDefinition(
        name="delete_calendar_event",
        description=(
            "Delete one or more events from the student's calendar. Prefer passing the exact"
            " 'event_id' returned by get_upcoming_events or get_events_for_date. If you don't"
            " have an id, pass the event 'title' (and optionally a 'date') to remove all matching"
            " events — useful for clearing a recurring/repeated series the student no longer wants."
        ),
        parameters={
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The id of the specific event to delete (preferred).",
                },
                "title": {
                    "type": "string",
                    "description": (
                        "Exact event title to match when no event_id is known."
                        " Deletes all events with this title."
                    ),
                },
                "date": {
                    "type": "string",
                    "description": "Optional YYYY-MM-DD date to narrow a title-based delete to a single day.",
                },
            },
            "required": [],
        },
        handler=_handle_delete_event,
    )
)

register(
    ToolDefinition(
        name="get_events_for_date",
        description=(
            "Get all calendar events for a specific date."
            " Use this when the student asks about a specific day's schedule."
        ),
        parameters={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "The date to check in YYYY-MM-DD format"},
            },
            "required": ["date"],
        },
        handler=_handle_get_events_for_date,
    )
)
