"""Chatbot tools backed by the University Knowledge Base (UKB) mock service.

These let MAI answer questions about courses, timetables, clubs and facility metadata, and
sync the student's enrolled classes from the UKB into the local calendar (Flow 5 / Flow 8).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import campus_api
from campus_calendar.calendar_memory import index_event_to_memory
from campus_calendar.event_model import EVENT_COLORS, EventType
from services import get_calendar_store as _get_store
from services import get_memory_manager as _get_mgr
from tools import ToolDefinition, register

# Full day name -> (weekday index, recurrence abbreviation)
_DAY_INFO = {
    "Monday": (0, "MO"),
    "Tuesday": (1, "TU"),
    "Wednesday": (2, "WE"),
    "Thursday": (3, "TH"),
    "Friday": (4, "FR"),
    "Saturday": (5, "SA"),
    "Sunday": (6, "SU"),
}


def _err(result):
    """Return the error dict if the API call failed, else None."""
    if isinstance(result, dict) and "error" in result:
        return {"error": result["error"]}
    return None


def _handle_query_timetable(args: dict) -> dict:
    day = args.get("day")
    slots = campus_api.ukb_student_timetable()
    if (err := _err(slots)) is not None:
        return err

    if day:
        slots = [s for s in slots if s["day"].lower() == day.lower()]

    if not slots:
        scope = f" on {day}" if day else ""
        return {"classes": [], "count": 0, "message": f"You have no classes{scope}."}

    classes = [
        {
            "course": f"{s['course_code']} {s['course_title']}",
            "day": s["day"],
            "time": f"{s['start_time']}-{s['end_time']}",
            "room": s["room"],
            "lecturer": s["lecturer"],
        }
        for s in slots
    ]
    return {"classes": classes, "count": len(classes)}


def _handle_lookup_course(args: dict) -> dict:
    code = args.get("code", "").strip()
    if not code:
        return {"error": "Provide a course code, e.g. MECS0033."}
    course = campus_api.ukb_course(code)
    if (err := _err(course)) is not None:
        return err
    return course


def _handle_list_clubs(args: dict) -> dict:
    clubs = campus_api.ukb_clubs(interest=args.get("interest"))
    if (err := _err(clubs)) is not None:
        return err
    return {
        "clubs": [
            {
                "name": c["name"],
                "description": c["description"],
                "interest": c["interest"],
                "meets": f"{c['meeting_day']} {c['meeting_time']}",
                "contact": c["contact_email"],
            }
            for c in clubs
        ],
        "count": len(clubs),
    }


def _handle_get_facility_info(args: dict) -> dict:
    facilities = campus_api.ukb_facilities()
    if (err := _err(facilities)) is not None:
        return err
    name = args.get("name")
    if name:
        facilities = [f for f in facilities if name.lower() in f["name"].lower()]
    return {
        "facilities": [
            {
                "name": f["name"],
                "type": f["type"],
                "capacity": f["capacity"],
                "location": f["location"],
                "hours": f"{f['open_time']}-{f['close_time']}",
                "rules": f["booking_rules"],
            }
            for f in facilities
        ],
        "count": len(facilities),
    }


def _next_weekday_date(weekday: int) -> date:
    """Date of the next occurrence of `weekday` (0=Mon), including today."""
    today = date.today()
    delta = (weekday - today.weekday()) % 7
    return today + timedelta(days=delta)


def sync_timetable_from_ukb() -> dict:
    """Pull the student's UKB timetable and create recurring CLASS events. Idempotent by title+day."""
    slots = campus_api.ukb_student_timetable()
    if (err := _err(slots)) is not None:
        return err

    store = _get_store()
    existing = store.get_all_events()
    existing_keys = {
        (e.get("title", ""), datetime.fromisoformat(e["start_datetime"]).weekday())
        for e in existing
        if e.get("type") == "class"
    }

    created = 0
    for s in slots:
        day = s["day"]
        if day not in _DAY_INFO:
            continue
        weekday, abbr = _DAY_INFO[day]
        title = f"{s['course_code']} {s['course_title']}"
        if (title, weekday) in existing_keys:
            continue

        anchor = _next_weekday_date(weekday)
        sh, sm = map(int, s["start_time"].split(":"))
        eh, em = map(int, s["end_time"].split(":"))
        start_dt = datetime(anchor.year, anchor.month, anchor.day, sh, sm, tzinfo=UTC)
        end_dt = datetime(anchor.year, anchor.month, anchor.day, eh, em, tzinfo=UTC)

        room = s.get("room") or ""
        lecturer = s.get("lecturer") or ""
        event = store.create_event(
            {
                "title": title,
                "type": "class",
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
                "recurrence_rule": f"WEEKLY:{abbr}",
                "description": f"Room {room}. Lecturer: {lecturer}.".strip(),
                "color": EVENT_COLORS[EventType.CLASS],
            }
        )
        index_event_to_memory(event, _get_mgr())
        existing_keys.add((title, weekday))
        created += 1

    return {
        "success": True,
        "created": created,
        "message": (
            f"Synced {created} class(es) from the Knowledge Base into your calendar."
            if created
            else "Your calendar is already up to date with the Knowledge Base."
        ),
    }


def _handle_sync_classes(args: dict) -> dict:
    return sync_timetable_from_ukb()


register(
    ToolDefinition(
        name="query_my_timetable",
        description=(
            "Get the student's weekly class timetable from the University Knowledge Base."
            " Use this to answer questions like 'Do I have class on Monday?' or 'What's my schedule?'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "day": {
                    "type": "string",
                    "description": "Optional day filter, e.g. 'Monday'. Omit for the full week.",
                }
            },
            "required": [],
        },
        handler=_handle_query_timetable,
    )
)

register(
    ToolDefinition(
        name="lookup_course",
        description=(
            "Look up a course in the University Knowledge Base by its code (e.g. MECS0033)."
            " Returns title, credits, lecturer, and timetable (day, time, room)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Course code, e.g. MECS0033"},
            },
            "required": ["code"],
        },
        handler=_handle_lookup_course,
    )
)

register(
    ToolDefinition(
        name="list_clubs",
        description=(
            "List student clubs and societies from the University Knowledge Base."
            " Optionally filter by interest (e.g. technology, sports, arts, business)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "interest": {
                    "type": "string",
                    "description": "Optional interest tag to filter by, e.g. 'technology'.",
                }
            },
            "required": [],
        },
        handler=_handle_list_clubs,
    )
)

register(
    ToolDefinition(
        name="get_facility_info",
        description=(
            "Get campus facility information (opening hours, capacity, location, booking rules)"
            " from the University Knowledge Base. Use for questions like 'when does the library close?'."
            " To actually book a facility, use the booking tools instead."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Optional facility name filter, e.g. 'library' or 'badminton'.",
                }
            },
            "required": [],
        },
        handler=_handle_get_facility_info,
    )
)

register(
    ToolDefinition(
        name="sync_my_classes",
        description=(
            "Sync the student's enrolled classes from the University Knowledge Base into their"
            " calendar as recurring weekly events. Use when the student asks to import or sync their"
            " class schedule."
        ),
        parameters={"type": "object", "properties": {}, "required": []},
        handler=_handle_sync_classes,
    )
)
