"""Seed the mock backend with a believable UTM / Malaysian dataset.

Anchored to the assignment's FOL proof: course MECS0033 (Artificial Intelligence), taught by
Dr Shafaatunnur Hasan, Monday 09:00-11:00 in Room N28, with student Darwin Subramaniam (MEC255043)
enrolled. Broadened with more lecturers, students, courses, clubs and facilities so features can
actually be exercised.

seed() is idempotent: it no-ops once the students table is populated.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from mock_server.models import (
    Booking,
    Club,
    Course,
    Enrollment,
    Facility,
    Lecturer,
    Student,
    TimetableEntry,
)

# --- Lecturers (Faculty of Computing, UTM) ---------------------------------
LECTURERS = [
    ("L001", "Shafaatunnur Hasan", "Dr"),
    ("L002", "Mohd Faizal bin Abdullah", "Dr"),
    ("L003", "Nurul Aini binti Ismail", "Dr"),
    ("L004", "Tan Wei Ming", "Assoc. Prof. Dr"),
    ("L005", "Siti Mariam binti Yusof", "Dr"),
    ("L006", "Rajesh Kumar a/l Subramaniam", "Dr"),
    ("L007", "Lim Chee Keong", "Dr"),
]

# --- Courses: code, title, credits, lecturer_id, [ (day, start, end, room), ... ] ---
COURSES = [
    ("MECS0033", "Artificial Intelligence", 3, "L001", [("Monday", "09:00", "11:00", "N28")]),
    ("MECS0011", "Data Structures & Algorithms", 3, "L002",
     [("Tuesday", "10:00", "12:00", "BK1"), ("Thursday", "14:00", "16:00", "Lab-CS2")]),
    ("MECS0022", "Database Systems", 3, "L003",
     [("Wednesday", "14:00", "16:00", "MPK4"), ("Friday", "14:00", "16:00", "Lab-DB1")]),
    ("MECS0044", "Software Engineering", 3, "L004", [("Thursday", "09:00", "11:00", "N24")]),
    ("MECS0055", "Computer Networks", 3, "L005", [("Tuesday", "14:00", "16:00", "BK3")]),
    ("MECS0066", "Machine Learning", 3, "L001", [("Wednesday", "09:00", "11:00", "N28")]),
    ("MECS0077", "Human-Computer Interaction", 2, "L006", [("Friday", "10:00", "12:00", "MPK2")]),
    ("MECS0088", "Operating Systems", 3, "L007", [("Monday", "14:00", "16:00", "N24")]),
]

# --- Students: matric, name, year ---
STUDENTS = [
    ("MEC255055", "Aisy Mikhail", 1),
    ("MEC255043", "Darwin Subramaniam", 1),
    ("MEC255060", "Tian Zhi Fung", 1),
    ("MEC255068", "Mohan Mahendren", 1),
    ("MEC255012", "Nurul Izzah binti Ahmad", 2),
    ("MEC255019", "Muhammad Haziq bin Rahman", 2),
    ("MEC255027", "Lim Wei Jie", 2),
    ("MEC255034", "Priya a/p Maniam", 3),
    ("MEC255041", "Wong Mei Ling", 3),
    ("MEC255049", "Arjun a/l Devan", 1),
    ("MEC255053", "Farah Nabilah binti Zainal", 2),
    ("MEC255071", "Tan Jia Hui", 1),
]

# --- Enrollments: student_id -> [course codes]. Darwin MUST include MECS0033 (FOL anchor). ---
ENROLLMENTS = {
    "MEC255043": ["MECS0033", "MECS0011", "MECS0022", "MECS0044"],  # Darwin
    "MEC255055": ["MECS0033", "MECS0066", "MECS0077"],
    "MEC255060": ["MECS0033", "MECS0011", "MECS0088"],
    "MEC255068": ["MECS0033", "MECS0055", "MECS0044"],
    "MEC255012": ["MECS0022", "MECS0055", "MECS0066"],
    "MEC255019": ["MECS0011", "MECS0088", "MECS0077"],
    "MEC255027": ["MECS0033", "MECS0066", "MECS0044", "MECS0055"],
    "MEC255034": ["MECS0022", "MECS0077"],
    "MEC255041": ["MECS0044", "MECS0088", "MECS0011"],
    "MEC255049": ["MECS0033", "MECS0022"],
    "MEC255053": ["MECS0055", "MECS0066", "MECS0077"],
    "MEC255071": ["MECS0033", "MECS0011", "MECS0066"],
}

# --- Clubs: id, name, description, interest, meeting_day, meeting_time ---
CLUBS = [
    ("CLB01", "AI Club UTM", "Workshops, talks and hackathons on artificial intelligence and data science.",
     "technology", "Wednesday", "17:00"),
    ("CLB02", "GDSC UTM", "Google Developer Student Club — build with Google technologies and ship projects.",
     "technology", "Thursday", "18:00"),
    ("CLB03", "Robotics Club UTM", "Design and compete with autonomous robots; Arduino and ROS sessions.",
     "engineering", "Tuesday", "17:00"),
    ("CLB04", "Persatuan Mahasiswa Fakulti Komputeran", "Faculty student body — welfare, events and representation.",
     "community", "Friday", "16:00"),
    ("CLB05", "Photography Club", "Campus photowalks, editing workshops and exhibitions.",
     "arts", "Saturday", "10:00"),
    ("CLB06", "Entrepreneurship Society", "Startup pitching, mentorship and the annual demo day.",
     "business", "Monday", "18:00"),
]

# --- Facilities: id, name, type, capacity, location, open, close, rules ---
FACILITIES = [
    ("FAC01", "PSZ Discussion Room A", "library_room", 6, "Perpustakaan Sultanah Zanariah, Level 2",
     "08:00", "22:00", "Max 2 hours per booking. Valid UTM matric required."),
    ("FAC02", "PSZ Discussion Room B", "library_room", 8, "Perpustakaan Sultanah Zanariah, Level 3",
     "08:00", "22:00", "Max 2 hours per booking. Min 3 students."),
    ("FAC03", "Study Pod N28-1", "study_pod", 2, "N28 Block, Faculty of Computing",
     "07:00", "23:00", "Max 3 hours per booking. Single or pair use."),
    ("FAC04", "Study Pod N28-2", "study_pod", 2, "N28 Block, Faculty of Computing",
     "07:00", "23:00", "Max 3 hours per booking. Single or pair use."),
    ("FAC05", "Badminton Court 1", "sports_court", 4, "Pusat Sukan UTM (Sports Complex)",
     "08:00", "23:00", "Max 2 hours per booking. Bring your own racket."),
    ("FAC06", "Futsal Court A", "sports_court", 10, "Pusat Sukan UTM (Sports Complex)",
     "08:00", "23:00", "Max 2 hours per booking. Non-marking shoes only."),
    ("FAC07", "Seminar Room MPK4", "seminar_room", 30, "Faculty of Computing, Level 1",
     "08:00", "18:00", "For registered events only. Book 24 hours ahead."),
    ("FAC08", "PSZ Discussion Room C", "library_room", 4, "Perpustakaan Sultanah Zanariah, Level 2",
     "08:00", "22:00", "Max 2 hours per booking. Valid UTM matric required."),
]


def _email_from_name(name: str) -> str:
    first = name.split()[0].lower()
    return f"{first}@graduate.utm.my"


def seed(db: Session) -> None:
    """Populate the database once. No-op if students already exist."""
    if db.query(Student).count() > 0:
        return

    # Lecturers
    for lid, name, title in LECTURERS:
        db.add(Lecturer(id=lid, name=name, title=title, email=f"{lid.lower()}@utm.my"))

    # Courses + timetable
    for code, title, credits, lecturer_id, slots in COURSES:
        db.add(Course(code=code, title=title, credits=credits, lecturer_id=lecturer_id))
        for day, start, end, room in slots:
            db.add(TimetableEntry(course_code=code, day=day, start_time=start, end_time=end, room=room))

    # Students
    for sid, name, year in STUDENTS:
        db.add(Student(id=sid, name=name, email=_email_from_name(name), year=year))

    # Enrollments
    for sid, codes in ENROLLMENTS.items():
        for code in codes:
            db.add(Enrollment(student_id=sid, course_code=code))

    # Clubs
    for cid, name, desc, interest, mday, mtime in CLUBS:
        slug = name.split()[0].lower()
        db.add(Club(id=cid, name=name, description=desc, interest=interest,
                    meeting_day=mday, meeting_time=mtime, contact_email=f"{slug}@club.utm.my"))

    # Facilities
    for fid, name, ftype, cap, loc, opn, cls, rules in FACILITIES:
        db.add(Facility(id=fid, name=name, type=ftype, capacity=cap, location=loc,
                        open_time=opn, close_time=cls, booking_rules=rules))

    # A few pre-existing bookings so availability / conflict (409) is demonstrable.
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    db.add(Booking(student_id="MEC255043", facility_id="FAC01", date=today,
                   start_time="14:00", end_time="16:00", status="confirmed", created_at=now))
    db.add(Booking(student_id="MEC255060", facility_id="FAC03", date=today,
                   start_time="10:00", end_time="12:00", status="confirmed", created_at=now))
    db.add(Booking(student_id="MEC255068", facility_id="FAC05", date=tomorrow,
                   start_time="18:00", end_time="19:00", status="confirmed", created_at=now))

    db.commit()
    print("[mock_server] database seeded with UTM mock data.")
