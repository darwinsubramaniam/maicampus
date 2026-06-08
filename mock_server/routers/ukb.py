"""University Knowledge Base (UKB) — read-only endpoints over the SurrealDB campus dataset."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from mock_server.db import query, thing
from mock_server.schemas import (
    ClubOut,
    CourseOut,
    FacilityOut,
    StudentOut,
    TimetableEntryOut,
    TimetableSlotOut,
)

router = APIRouter(prefix="/ukb", tags=["University Knowledge Base"])

_DAY_ORDER = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
    "Friday": 4, "Saturday": 5, "Sunday": 6,
}


def _lecturer_label(course: dict) -> str | None:
    lec = course.get("lecturer")
    if isinstance(lec, dict):
        return f"{lec.get('title', '')} {lec.get('name', '')}".strip()
    return None


def _course_out(course: dict) -> CourseOut:
    return CourseOut(
        code=course["id"],
        title=course["title"],
        credits=course["credits"],
        semester=course["semester"],
        lecturer=_lecturer_label(course),
        timetable=[TimetableEntryOut(**t) for t in (course.get("timetable") or [])],
    )


def _enrolled_codes(student_id: str) -> list[str]:
    rows = query("SELECT ->enrolled->course AS codes FROM $rid", {"rid": thing("student", student_id)})
    return list(rows[0]["codes"]) if rows and rows[0].get("codes") else []


@router.get("/courses", response_model=list[CourseOut])
def list_courses(
    code: str | None = Query(None, description="Filter by exact course code"),
    day: str | None = Query(None, description="Filter to courses with a class on this day"),
    lecturer: str | None = Query(None, description="Filter by lecturer name substring"),
) -> list[CourseOut]:
    courses = query("SELECT * FROM course FETCH lecturer")
    results: list[CourseOut] = []
    for course in courses:
        if code and str(course["id"]).lower() != code.lower():
            continue
        if day and not any(t["day"].lower() == day.lower() for t in (course.get("timetable") or [])):
            continue
        if lecturer and lecturer.lower() not in (_lecturer_label(course) or "").lower():
            continue
        results.append(_course_out(course))
    return results


@router.get("/courses/{course_code}", response_model=CourseOut)
def get_course(course_code: str) -> CourseOut:
    rows = query("SELECT * FROM $rid FETCH lecturer", {"rid": thing("course", course_code.upper())})
    if not rows:
        raise HTTPException(status_code=404, detail=f"Course {course_code} not found")
    return _course_out(rows[0])


@router.get("/students/{student_id}", response_model=StudentOut)
def get_student(student_id: str) -> StudentOut:
    rows = query("SELECT * FROM $rid", {"rid": thing("student", student_id.upper())})
    if not rows:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
    s = rows[0]
    return StudentOut(
        id=s["id"], name=s["name"], email=s.get("email", ""), year=s.get("year", 1),
        programme=s.get("programme", ""), enrolled_courses=sorted(_enrolled_codes(student_id.upper())),
    )


@router.get("/students/{student_id}/timetable", response_model=list[TimetableSlotOut])
def get_student_timetable(student_id: str) -> list[TimetableSlotOut]:
    """Weekly class schedule = the student's enrolled courses (graph) joined with course timetables."""
    sid = student_id.upper()
    student = query("SELECT id FROM $rid", {"rid": thing("student", sid)})
    if not student:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    codes = _enrolled_codes(sid)
    if not codes:
        return []

    courses = query(
        "SELECT * FROM course WHERE id IN $ids FETCH lecturer",
        {"ids": [thing("course", c) for c in codes]},
    )
    slots: list[TimetableSlotOut] = []
    for course in courses:
        label = _lecturer_label(course)
        for t in course.get("timetable") or []:
            slots.append(
                TimetableSlotOut(
                    course_code=course["id"],
                    course_title=course["title"],
                    day=t["day"],
                    start_time=t["start_time"],
                    end_time=t["end_time"],
                    room=t.get("room", ""),
                    lecturer=label,
                )
            )
    slots.sort(key=lambda s: (_DAY_ORDER.get(s.day, 9), s.start_time))
    return slots


@router.get("/clubs", response_model=list[ClubOut])
def list_clubs(
    interest: str | None = Query(None, description="Filter by interest tag substring"),
) -> list[ClubOut]:
    clubs = query("SELECT * FROM club")
    if interest:
        clubs = [c for c in clubs if interest.lower() in str(c.get("interest", "")).lower()]
    return [ClubOut(id=c["id"], **{k: c.get(k, "") for k in
                                   ("name", "description", "interest", "meeting_day", "meeting_time", "contact_email")})
            for c in clubs]


@router.get("/facilities", response_model=list[FacilityOut])
def list_facility_metadata() -> list[FacilityOut]:
    """Read-only facility catalogue (hours, capacity, rules). Booking lives under /facility."""
    facilities = query("SELECT * FROM facility")
    return [_facility_out(f) for f in facilities]


def _facility_out(f: dict) -> FacilityOut:
    return FacilityOut(
        id=f["id"], name=f["name"], type=f["type"], capacity=f.get("capacity", 1),
        location=f.get("location", ""), open_time=f.get("open_time", "08:00"),
        close_time=f.get("close_time", "22:00"), booking_rules=f.get("booking_rules", ""),
    )
