"""University Knowledge Base (UKB) — read-only endpoints over the campus dataset."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from mock_server.db import get_db
from mock_server.models import Club, Course, Facility, Student, TimetableEntry
from mock_server.schemas import (
    ClubOut,
    CourseOut,
    FacilityOut,
    StudentOut,
    TimetableEntryOut,
    TimetableSlotOut,
)

router = APIRouter(prefix="/ukb", tags=["University Knowledge Base"])


def _lecturer_label(course: Course) -> str | None:
    lec = course.lecturer
    if lec is None:
        return None
    return f"{lec.title} {lec.name}".strip()


def _course_out(course: Course) -> CourseOut:
    return CourseOut(
        code=course.code,
        title=course.title,
        credits=course.credits,
        semester=course.semester,
        lecturer=_lecturer_label(course),
        timetable=[TimetableEntryOut.model_validate(t) for t in course.timetable],
    )


@router.get("/courses", response_model=list[CourseOut])
def list_courses(
    code: str | None = Query(None, description="Filter by exact course code"),
    day: str | None = Query(None, description="Filter to courses with a class on this day"),
    lecturer: str | None = Query(None, description="Filter by lecturer name substring"),
    db: Session = Depends(get_db),
) -> list[CourseOut]:
    courses = db.scalars(select(Course)).all()
    results: list[CourseOut] = []
    for course in courses:
        if code and course.code.lower() != code.lower():
            continue
        if day and not any(t.day.lower() == day.lower() for t in course.timetable):
            continue
        if lecturer:
            label = (_lecturer_label(course) or "").lower()
            if lecturer.lower() not in label:
                continue
        results.append(_course_out(course))
    return results


@router.get("/courses/{course_code}", response_model=CourseOut)
def get_course(course_code: str, db: Session = Depends(get_db)) -> CourseOut:
    course = db.get(Course, course_code.upper())
    if course is None:
        raise HTTPException(status_code=404, detail=f"Course {course_code} not found")
    return _course_out(course)


@router.get("/students/{student_id}", response_model=StudentOut)
def get_student(student_id: str, db: Session = Depends(get_db)) -> StudentOut:
    student = db.get(Student, student_id.upper())
    if student is None:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
    codes = [e.course_code for e in student.enrollments]
    out = StudentOut.model_validate(student)
    out.enrolled_courses = sorted(codes)
    return out


@router.get("/students/{student_id}/timetable", response_model=list[TimetableSlotOut])
def get_student_timetable(student_id: str, db: Session = Depends(get_db)) -> list[TimetableSlotOut]:
    """Weekly class schedule = the student's enrolled courses joined with course timetables."""
    student = db.get(Student, student_id.upper())
    if student is None:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    codes = [e.course_code for e in student.enrollments]
    if not codes:
        return []

    entries = db.scalars(
        select(TimetableEntry).where(TimetableEntry.course_code.in_(codes))
    ).all()

    day_order = {
        "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
        "Friday": 4, "Saturday": 5, "Sunday": 6,
    }
    slots: list[TimetableSlotOut] = []
    for entry in entries:
        course = entry.course
        slots.append(
            TimetableSlotOut(
                course_code=course.code,
                course_title=course.title,
                day=entry.day,
                start_time=entry.start_time,
                end_time=entry.end_time,
                room=entry.room,
                lecturer=_lecturer_label(course),
            )
        )
    slots.sort(key=lambda s: (day_order.get(s.day, 9), s.start_time))
    return slots


@router.get("/clubs", response_model=list[ClubOut])
def list_clubs(
    interest: str | None = Query(None, description="Filter by interest tag substring"),
    db: Session = Depends(get_db),
) -> list[ClubOut]:
    clubs = db.scalars(select(Club)).all()
    if interest:
        clubs = [c for c in clubs if interest.lower() in c.interest.lower()]
    return [ClubOut.model_validate(c) for c in clubs]


@router.get("/facilities", response_model=list[FacilityOut])
def list_facility_metadata(db: Session = Depends(get_db)) -> list[FacilityOut]:
    """Read-only facility catalogue (hours, capacity, rules). Booking lives under /facility."""
    facilities = db.scalars(select(Facility)).all()
    return [FacilityOut.model_validate(f) for f in facilities]
