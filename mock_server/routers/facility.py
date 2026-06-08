"""Facility Booking API (SurrealDB) — search, availability, and booking with conflict prevention."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from mock_server.db import query, thing
from mock_server.schemas import (
    AvailabilityOut,
    BookingCreate,
    BookingOut,
    FacilityOut,
    SlotOut,
)

router = APIRouter(prefix="/facility", tags=["Facility Booking"])


def _to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return _to_min(a_start) < _to_min(b_end) and _to_min(b_start) < _to_min(a_end)


def _facility_out(f: dict) -> FacilityOut:
    return FacilityOut(
        id=f["id"], name=f["name"], type=f["type"], capacity=f.get("capacity", 1),
        location=f.get("location", ""), open_time=f.get("open_time", "08:00"),
        close_time=f.get("close_time", "22:00"), booking_rules=f.get("booking_rules", ""),
    )


def _booking_out(b: dict) -> BookingOut:
    return BookingOut(
        id=int(b["id"]), student_id=b["student_id"], facility_id=b["facility_id"], date=b["date"],
        start_time=b["start_time"], end_time=b["end_time"], status=b["status"],
        created_at=b.get("created_at", ""),
    )


def _get_facility(facility_id: str) -> dict | None:
    rows = query("SELECT * FROM $rid", {"rid": thing("facility", facility_id.upper())})
    return rows[0] if rows else None


def _active_bookings(facility_id: str, date: str) -> list[dict]:
    return query(
        "SELECT * FROM booking WHERE facility_id = $f AND date = $d AND status = 'confirmed'",
        {"f": facility_id, "d": date},
    )


@router.get("/facilities", response_model=list[FacilityOut])
def search_facilities(
    type: str | None = Query(None, description="library_room | study_pod | sports_court | seminar_room"),
) -> list[FacilityOut]:
    facilities = query("SELECT * FROM facility")
    if type:
        facilities = [f for f in facilities if str(f.get("type", "")).lower() == type.lower()]
    return [_facility_out(f) for f in facilities]


@router.get("/availability", response_model=AvailabilityOut)
def availability(
    facility_id: str = Query(..., description="Facility id, e.g. FAC01"),
    date: str = Query(..., description="Target date YYYY-MM-DD"),
) -> AvailabilityOut:
    facility = _get_facility(facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail=f"Facility {facility_id} not found")

    booked = _active_bookings(facility["id"], date)
    open_min = _to_min(facility["open_time"])
    close_min = _to_min(facility["close_time"])

    slots: list[SlotOut] = []
    for start in range(open_min, close_min, 60):
        s = f"{start // 60:02d}:{start % 60:02d}"
        e = f"{(start + 60) // 60:02d}:{(start + 60) % 60:02d}"
        is_free = not any(_overlaps(s, e, b["start_time"], b["end_time"]) for b in booked)
        slots.append(SlotOut(start_time=s, end_time=e, available=is_free))

    return AvailabilityOut(
        facility_id=facility["id"], facility_name=facility["name"], date=date, slots=slots
    )


@router.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(payload: BookingCreate) -> BookingOut:
    facility = _get_facility(payload.facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail=f"Facility {payload.facility_id} not found")

    if _to_min(payload.start_time) >= _to_min(payload.end_time):
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    if _to_min(payload.start_time) < _to_min(facility["open_time"]) or _to_min(
        payload.end_time
    ) > _to_min(facility["close_time"]):
        raise HTTPException(
            status_code=400,
            detail=f"{facility['name']} is open {facility['open_time']}-{facility['close_time']}",
        )

    # Conflict prevention: reject if the slot overlaps an existing confirmed booking.
    for b in _active_bookings(facility["id"], payload.date):
        if _overlaps(payload.start_time, payload.end_time, b["start_time"], b["end_time"]):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{facility['name']} is already booked {b['start_time']}-{b['end_time']} "
                    f"on {payload.date}"
                ),
            )

    ids = query("SELECT VALUE meta::id(id) FROM booking")
    next_id = (max(int(i) for i in ids) + 1) if ids else 1
    rows = query(
        "CREATE $rid CONTENT $data",
        {
            "rid": thing("booking", next_id),
            "data": {
                "student_id": payload.student_id,
                "facility_id": facility["id"],
                "date": payload.date,
                "start_time": payload.start_time,
                "end_time": payload.end_time,
                "status": "confirmed",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        },
    )
    return _booking_out(rows[0])


@router.get("/bookings", response_model=list[BookingOut])
def list_bookings(
    student_id: str = Query(..., description="Matric number, e.g. MEC255043"),
) -> list[BookingOut]:
    bookings = query(
        "SELECT * FROM booking WHERE student_id = $s AND status = 'confirmed'",
        {"s": student_id.upper()},
    )
    return [_booking_out(b) for b in bookings]


@router.delete("/bookings/{booking_id}", status_code=204)
def cancel_booking(booking_id: int) -> None:
    rows = query("SELECT id FROM $rid", {"rid": thing("booking", booking_id)})
    if not rows:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
    query("UPDATE $rid SET status = 'cancelled'", {"rid": thing("booking", booking_id)})
