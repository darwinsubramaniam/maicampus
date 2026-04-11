from datetime import date, datetime, timezone

from campus_calendar.calendar_memory import index_event_to_memory
from campus_calendar.event_model import EVENT_COLORS, EVENT_LABELS, event_time_str, event_type_from_str
from services import calendar_store as _store, get_memory_manager as _get_mgr
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

    start_dt = datetime(int(d[:4]), int(d[5:7]), int(d[8:10]), sh, sm, tzinfo=timezone.utc)
    end_dt = datetime(int(d[:4]), int(d[5:7]), int(d[8:10]), eh, em, tzinfo=timezone.utc)

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

    event = _store.create_event(event_data)
    index_event_to_memory(event, _get_mgr())

    return {
        "success": True,
        "event_id": event["id"],
        "title": event["title"],
        "message": f"Event '{event['title']}' has been added to the calendar.",
    }


def _handle_get_upcoming(args: dict) -> dict:
    days = int(args.get("days", 7))
    upcoming = _store.get_upcoming_events(days=days)

    events = []
    for d, event in upcoming:
        et = event_type_from_str(event.get("type", "custom"))
        events.append({
            "date": d.isoformat(),
            "title": event.get("title", ""),
            "type": EVENT_LABELS.get(et, "Event"),
            "time": event_time_str(event),
        })

    return {"events": events, "count": len(events)}


def _handle_get_events_for_date(args: dict) -> dict:
    target = date.fromisoformat(args.get("date", date.today().isoformat()))
    events_list = _store.get_events_for_date(target)

    events = []
    for event in events_list:
        et = event_type_from_str(event.get("type", "custom"))
        events.append({
            "title": event.get("title", ""),
            "type": EVENT_LABELS.get(et, "Event"),
            "time": event_time_str(event),
            "description": event.get("description", ""),
        })

    return {"date": target.isoformat(), "events": events, "count": len(events)}


# Register tools
register(ToolDefinition(
    name="create_calendar_event",
    description="Create a new event in the student's calendar. Use this when the student wants to add a class, assignment, exam, club activity, or any event to their schedule.",
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
                "description": "Recurrence rule. Use WEEKLY:MO,WE for weekly on Monday and Wednesday, or NONE for one-time events.",
            },
            "description": {"type": "string", "description": "Optional description or notes"},
        },
        "required": ["title", "date", "start_time", "end_time", "type"],
    },
    handler=_handle_create_event,
))

register(ToolDefinition(
    name="get_upcoming_events",
    description="Get the student's upcoming calendar events for the next N days. Use this to check schedule, find conflicts, or answer questions about what's coming up.",
    parameters={
        "type": "object",
        "properties": {
            "days": {"type": "integer", "description": "Number of days to look ahead (default: 7)"},
        },
        "required": [],
    },
    handler=_handle_get_upcoming,
))

register(ToolDefinition(
    name="get_events_for_date",
    description="Get all calendar events for a specific date. Use this when the student asks about a specific day's schedule.",
    parameters={
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "The date to check in YYYY-MM-DD format"},
        },
        "required": ["date"],
    },
    handler=_handle_get_events_for_date,
))
