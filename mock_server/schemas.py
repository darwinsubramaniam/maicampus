"""Pydantic request/response schemas for the mock backend API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LecturerOut(_ORM):
    id: str
    name: str
    title: str
    faculty: str
    email: str


class TimetableEntryOut(_ORM):
    day: str
    start_time: str
    end_time: str
    room: str


class CourseOut(_ORM):
    code: str
    title: str
    credits: int
    semester: str
    lecturer: str | None = None
    timetable: list[TimetableEntryOut] = []


class StudentOut(_ORM):
    id: str
    name: str
    email: str
    year: int
    programme: str
    enrolled_courses: list[str] = []


class TimetableSlotOut(BaseModel):
    """A concrete class occurrence in a student's weekly schedule."""

    course_code: str
    course_title: str
    day: str
    start_time: str
    end_time: str
    room: str
    lecturer: str | None = None


class ClubOut(_ORM):
    id: str
    name: str
    description: str
    interest: str
    meeting_day: str
    meeting_time: str
    contact_email: str


class FacilityOut(_ORM):
    id: str
    name: str
    type: str
    capacity: int
    location: str
    open_time: str
    close_time: str
    booking_rules: str


class SlotOut(BaseModel):
    start_time: str
    end_time: str
    available: bool


class AvailabilityOut(BaseModel):
    facility_id: str
    facility_name: str
    date: str
    slots: list[SlotOut]


class BookingCreate(BaseModel):
    student_id: str
    facility_id: str
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM


class BookingOut(_ORM):
    id: int
    student_id: str
    facility_id: str
    date: str
    start_time: str
    end_time: str
    status: str
    created_at: str
