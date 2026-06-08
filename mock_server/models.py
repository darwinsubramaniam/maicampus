"""SQLAlchemy ORM models for the UTM mock backend."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mock_server.db import Base


class Lecturer(Base):
    __tablename__ = "lecturers"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "L001"
    name: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, default="")  # e.g. "Dr", "Assoc. Prof. Dr"
    faculty: Mapped[str] = mapped_column(String, default="Faculty of Computing")
    email: Mapped[str] = mapped_column(String, default="")

    courses: Mapped[list[Course]] = relationship(back_populates="lecturer")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # matric, e.g. "MEC255043"
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, default="")
    year: Mapped[int] = mapped_column(Integer, default=1)
    programme: Mapped[str] = mapped_column(String, default="Bachelor of Computer Science")

    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class Course(Base):
    __tablename__ = "courses"

    code: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "MECS0033"
    title: Mapped[str] = mapped_column(String, nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=3)
    semester: Mapped[str] = mapped_column(String, default="2025/26-2")
    lecturer_id: Mapped[str | None] = mapped_column(ForeignKey("lecturers.id"), nullable=True)

    lecturer: Mapped[Lecturer | None] = relationship(back_populates="courses")
    timetable: Mapped[list[TimetableEntry]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class TimetableEntry(Base):
    __tablename__ = "timetable_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_code: Mapped[str] = mapped_column(ForeignKey("courses.code"), nullable=False)
    day: Mapped[str] = mapped_column(String, nullable=False)  # "Monday" .. "Sunday"
    start_time: Mapped[str] = mapped_column(String, nullable=False)  # "09:00"
    end_time: Mapped[str] = mapped_column(String, nullable=False)  # "11:00"
    room: Mapped[str] = mapped_column(String, default="")

    course: Mapped[Course] = relationship(back_populates="timetable")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "course_code", name="uq_enrollment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False)
    course_code: Mapped[str] = mapped_column(ForeignKey("courses.code"), nullable=False)

    student: Mapped[Student] = relationship(back_populates="enrollments")
    course: Mapped[Course] = relationship(back_populates="enrollments")


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "CLB01"
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, default="")
    interest: Mapped[str] = mapped_column(String, default="")  # tag, e.g. "technology"
    meeting_day: Mapped[str] = mapped_column(String, default="")
    meeting_time: Mapped[str] = mapped_column(String, default="")
    contact_email: Mapped[str] = mapped_column(String, default="")


class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "FAC01"
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # library_room|study_pod|sports_court|seminar_room
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    location: Mapped[str] = mapped_column(String, default="")
    open_time: Mapped[str] = mapped_column(String, default="08:00")
    close_time: Mapped[str] = mapped_column(String, default="22:00")
    booking_rules: Mapped[str] = mapped_column(String, default="")

    bookings: Mapped[list[Booking]] = relationship(
        back_populates="facility", cascade="all, delete-orphan"
    )


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String, nullable=False)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    date: Mapped[str] = mapped_column(String, nullable=False)  # "2026-06-10"
    start_time: Mapped[str] = mapped_column(String, nullable=False)  # "14:00"
    end_time: Mapped[str] = mapped_column(String, nullable=False)  # "16:00"
    status: Mapped[str] = mapped_column(String, default="confirmed")  # confirmed|cancelled
    created_at: Mapped[str] = mapped_column(String, default="")

    facility: Mapped[Facility] = relationship(back_populates="bookings")
