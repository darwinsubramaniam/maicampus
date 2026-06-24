"""Chatbot tools backed by the Facility Booking mock service.

`book_facility` implements the assignment's Flow 6 chain: check facility availability (server),
check the student's local calendar for a clash, and only then confirm — saving the booking on the
server and mirroring it onto the calendar. Conflicts come back with suggested free slots.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import campus_api
from campus_calendar.calendar_memory import index_event_to_memory
from campus_calendar.event_model import booking_id_of
from services import get_calendar_store as _get_store
from services import get_memory_manager as _get_mgr
from tools import ToolDefinition, register

_BOOKING_COLOR = "#00897B"  # teal — distinguishes bookings from other calendar events


def _err(result):
    if isinstance(result, dict) and "error" in result:
        return {"error": result["error"]}
    return None


def _to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return _to_min(a_start) < _to_min(b_end) and _to_min(b_start) < _to_min(a_end)


def _free_slots(availability: dict, limit: int = 4) -> list[str]:
    return [
        f"{s['start_time']}-{s['end_time']}"
        for s in availability.get("slots", [])
        if s.get("available")
    ][:limit]


def _calendar_clash(target: date, start_time: str, end_time: str) -> dict | None:
    """Return the first local calendar event overlapping the requested slot on `target`, else None."""
    for event in _get_store().get_events_for_date(target):
        try:
            ev_start = datetime.fromisoformat(event["start_datetime"]).strftime("%H:%M")
            ev_end = datetime.fromisoformat(event["end_datetime"]).strftime("%H:%M")
        except (ValueError, KeyError):
            continue
        if _overlaps(start_time, end_time, ev_start, ev_end):
            return {"title": event.get("title", "an event"), "time": f"{ev_start}-{ev_end}"}
    return None


def _facility_name_map() -> dict[str, str]:
    """Map facility_id → friendly name (bookings only carry the id)."""
    facilities = campus_api.facility_list()
    if isinstance(facilities, dict):  # {"error": ...}
        return {}
    return {f["id"]: f["name"] for f in facilities}


def _find_booking_event(booking_id: int) -> dict | None:
    """Find the calendar event mirrored from a booking by its stored ``booking_id`` link."""
    for event in _get_store().get_all_events():
        if booking_id_of(event) == booking_id:
            return event
    return None


def _delete_booking_event(booking_id: int) -> bool:
    """Remove the booking's mirrored calendar event, if one exists. Returns True if removed."""
    event = _find_booking_event(booking_id)
    if event is None:
        return False
    _get_store().delete_event(event["id"])
    return True


def _handle_search_facilities(args: dict) -> dict:
    facilities = campus_api.facility_list(type=args.get("type"))
    if (err := _err(facilities)) is not None:
        return err
    return {
        "facilities": [
            {
                "id": f["id"],
                "name": f["name"],
                "type": f["type"],
                "capacity": f["capacity"],
                "location": f["location"],
                "hours": f"{f['open_time']}-{f['close_time']}",
            }
            for f in facilities
        ],
        "count": len(facilities),
    }


def _handle_check_availability(args: dict) -> dict:
    facility_id = args.get("facility_id", "").strip()
    day = args.get("date", date.today().isoformat())
    if not facility_id:
        return {"error": "Provide a facility_id (e.g. FAC01). Use search_facilities to find one."}
    availability = campus_api.facility_availability(facility_id, day)
    if (err := _err(availability)) is not None:
        return err
    return {
        "facility_id": availability["facility_id"],
        "facility_name": availability["facility_name"],
        "date": day,
        "free_slots": _free_slots(availability, limit=12),
    }


def _handle_book_facility(args: dict) -> dict:
    facility_id = args.get("facility_id", "").strip()
    day_str = args.get("date", "").strip()
    start_time = args.get("start_time", "").strip()
    end_time = args.get("end_time", "").strip()

    if not (facility_id and day_str and start_time and end_time):
        return {"error": "Need facility_id, date (YYYY-MM-DD), start_time and end_time (HH:MM)."}
    try:
        target = date.fromisoformat(day_str)
    except ValueError:
        return {"error": "Invalid date. Use YYYY-MM-DD."}

    # 1. Check facility availability on the server.
    availability = campus_api.facility_availability(facility_id, day_str)
    if (err := _err(availability)) is not None:
        return err
    facility_name = availability["facility_name"]

    slot_taken = any(
        _overlaps(start_time, end_time, s["start_time"], s["end_time"]) and not s["available"]
        for s in availability.get("slots", [])
    )
    if slot_taken:
        return {
            "booked": False,
            "conflict": "facility",
            "message": f"{facility_name} is already booked at {start_time}-{end_time} on {day_str}.",
            "suggested_slots": _free_slots(availability),
        }

    # 2. Check the student's own calendar for a clash.
    clash = _calendar_clash(target, start_time, end_time)
    if clash is not None:
        return {
            "booked": False,
            "conflict": "calendar",
            "message": (
                f"You already have '{clash['title']}' at {clash['time']} on {day_str}, "
                f"which clashes with this booking."
            ),
            "suggested_slots": _free_slots(availability),
        }

    # 3. Confirm: save the booking on the server.
    booking = campus_api.facility_book(facility_id, day_str, start_time, end_time)
    if (err := _err(booking)) is not None:
        return err

    # 4. Mirror the booking onto the student's calendar.
    sh, sm = map(int, start_time.split(":"))
    eh, em = map(int, end_time.split(":"))
    start_dt = datetime(target.year, target.month, target.day, sh, sm, tzinfo=UTC)
    end_dt = datetime(target.year, target.month, target.day, eh, em, tzinfo=UTC)
    event = _get_store().create_event(
        {
            "title": f"Booking: {facility_name}",
            "type": "custom",
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "description": f"Facility booking #{booking['id']} at {facility_name}.",
            "color": _BOOKING_COLOR,
            "booking_id": booking["id"],
            "facility_id": facility_id,
        }
    )
    index_event_to_memory(event, _get_mgr())

    return {
        "booked": True,
        "success": True,
        "booking_id": booking["id"],
        "facility": facility_name,
        "date": day_str,
        "time": f"{start_time}-{end_time}",
        "message": (
            f"Booked {facility_name} on {day_str} from {start_time} to {end_time}. "
            "Added to your calendar."
        ),
    }


def _handle_list_my_bookings(args: dict) -> dict:
    bookings = campus_api.facility_bookings()
    if (err := _err(bookings)) is not None:
        return err
    names = _facility_name_map()
    items = [
        {
            "booking_id": b["id"],
            "facility_id": b["facility_id"],
            "facility": names.get(b["facility_id"], b["facility_id"]),
            "date": b["date"],
            "time": f"{b['start_time']}-{b['end_time']}",
        }
        for b in bookings
    ]
    items.sort(key=lambda x: (x["date"], x["time"]))
    return {
        "bookings": items,
        "count": len(items),
        "message": "You have no facility bookings yet." if not items else None,
    }


def _coerce_booking_id(raw) -> int | None:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _handle_cancel_booking(args: dict) -> dict:
    booking_id = _coerce_booking_id(args.get("booking_id"))
    if booking_id is None:
        return {"error": "Provide a numeric booking_id to cancel. Use list_my_bookings to find it."}

    result = campus_api.facility_cancel(booking_id)
    if (err := _err(result)) is not None:
        return err

    removed = _delete_booking_event(booking_id)
    return {
        "cancelled": True,
        "success": True,
        "booking_id": booking_id,
        "calendar_updated": removed,
        "message": (
            f"Cancelled booking #{booking_id}."
            + (" Removed it from your calendar." if removed else "")
        ),
    }


def _handle_reschedule_booking(args: dict) -> dict:
    booking_id = _coerce_booking_id(args.get("booking_id"))
    if booking_id is None:
        return {"error": "Provide a numeric booking_id. Use list_my_bookings to find it."}

    new_start = args.get("start_time", "").strip()
    new_end = args.get("end_time", "").strip()
    if not (new_start and new_end):
        return {"error": "Provide the new start_time and end_time (HH:MM) for the reschedule."}

    # Look up the current booking for its facility, the default date, and rollback details.
    bookings = campus_api.facility_bookings()
    if (err := _err(bookings)) is not None:
        return err
    current = next((b for b in bookings if b["id"] == booking_id), None)
    if current is None:
        return {"error": f"Booking #{booking_id} isn't in your active bookings. Use list_my_bookings."}

    facility_id = current["facility_id"]
    new_date = args.get("date", "").strip() or current["date"]

    # Cancel the old slot first so it frees up (and its calendar mirror is removed), then book the
    # new slot through the same Flow-6 chain (server availability + calendar clash + confirm + mirror).
    cancel = campus_api.facility_cancel(booking_id)
    if (err := _err(cancel)) is not None:
        return err
    _delete_booking_event(booking_id)

    new_booking = _handle_book_facility(
        {"facility_id": facility_id, "date": new_date, "start_time": new_start, "end_time": new_end}
    )
    if new_booking.get("booked"):
        return {
            "rescheduled": True,
            "success": True,
            "booking_id": new_booking["booking_id"],
            "previous_booking_id": booking_id,
            "facility": new_booking["facility"],
            "date": new_date,
            "time": f"{new_start}-{new_end}",
            "message": (
                f"Rescheduled to {new_booking['facility']} on {new_date} "
                f"from {new_start} to {new_end}. Your calendar is updated."
            ),
        }

    # The new slot was unavailable or clashed — roll back to the original booking so nothing is lost.
    rollback = _handle_book_facility(
        {
            "facility_id": facility_id,
            "date": current["date"],
            "start_time": current["start_time"],
            "end_time": current["end_time"],
        }
    )
    kept = bool(rollback.get("booked"))
    return {
        "rescheduled": False,
        "conflict": new_booking.get("conflict"),
        "booking_id": rollback.get("booking_id", booking_id) if kept else booking_id,
        "suggested_slots": new_booking.get("suggested_slots", []),
        "message": (
            f"Couldn't reschedule — {new_booking.get('message', 'the new slot is unavailable')} "
            + (
                f"Your original booking ({current['date']} "
                f"{current['start_time']}-{current['end_time']}) is unchanged."
                if kept
                else "Please re-check your bookings."
            )
        ),
    }


register(
    ToolDefinition(
        name="search_facilities",
        description=(
            "Search bookable campus facilities. Optionally filter by type"
            " (library_room, study_pod, sports_court, seminar_room). Returns facility ids to book with."
        ),
        parameters={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Optional facility type filter.",
                    "enum": ["library_room", "study_pod", "sports_court", "seminar_room"],
                }
            },
            "required": [],
        },
        handler=_handle_search_facilities,
    )
)

register(
    ToolDefinition(
        name="check_facility_availability",
        description=(
            "Check which time slots are free for a facility on a given date."
            " Use before booking to find an open slot."
        ),
        parameters={
            "type": "object",
            "properties": {
                "facility_id": {"type": "string", "description": "Facility id, e.g. FAC01"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
            },
            "required": ["facility_id", "date"],
        },
        handler=_handle_check_availability,
    )
)

register(
    ToolDefinition(
        name="book_facility",
        description=(
            "Book a campus facility for the student. Checks facility availability AND the student's"
            " calendar for clashes before confirming; on success it saves the booking and adds it to"
            " the calendar. If there is a conflict it returns suggested free slots instead."
        ),
        parameters={
            "type": "object",
            "properties": {
                "facility_id": {"type": "string", "description": "Facility id, e.g. FAC01 (from search_facilities)"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "start_time": {"type": "string", "description": "Start time in HH:MM 24-hour format"},
                "end_time": {"type": "string", "description": "End time in HH:MM 24-hour format"},
            },
            "required": ["facility_id", "date", "start_time", "end_time"],
        },
        handler=_handle_book_facility,
    )
)

register(
    ToolDefinition(
        name="list_my_bookings",
        description=(
            "List the student's current (confirmed) facility bookings, each with its booking_id,"
            " facility, date and time. Use this to show what they have booked and to find a"
            " booking_id before cancelling or rescheduling."
        ),
        parameters={"type": "object", "properties": {}, "required": []},
        handler=_handle_list_my_bookings,
    )
)

register(
    ToolDefinition(
        name="cancel_booking",
        description=(
            "Cancel one of the student's facility bookings by its booking_id (from"
            " list_my_bookings). Frees the slot on the server and removes the mirrored calendar"
            " event. Confirm with the student before cancelling."
        ),
        parameters={
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "integer",
                    "description": "The booking id to cancel (from list_my_bookings).",
                }
            },
            "required": ["booking_id"],
        },
        handler=_handle_cancel_booking,
    )
)

register(
    ToolDefinition(
        name="reschedule_booking",
        description=(
            "Move an existing facility booking to a new time (and optionally a new date) on the same"
            " facility. Identify it by booking_id (from list_my_bookings). Re-checks facility"
            " availability and the student's calendar for the new slot; if it clashes the original"
            " booking is kept unchanged and suggested free slots are returned. Confirm the new time"
            " with the student first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "integer",
                    "description": "The booking id to reschedule (from list_my_bookings).",
                },
                "start_time": {"type": "string", "description": "New start time in HH:MM 24-hour format"},
                "end_time": {"type": "string", "description": "New end time in HH:MM 24-hour format"},
                "date": {
                    "type": "string",
                    "description": "Optional new date in YYYY-MM-DD; defaults to the booking's current date.",
                },
            },
            "required": ["booking_id", "start_time", "end_time"],
        },
        handler=_handle_reschedule_booking,
    )
)
