"""HTTP client for the mock UTM backend (University Knowledge Base + Facility Booking).

Thin wrapper over httpx that mirrors the module-level style of ``services.py``. Every call
degrades gracefully: on a connection error or non-2xx response it returns a dict with an
``"error"`` key instead of raising, so chatbot tools and the booking UI can show a friendly
message when the backend is not running.
"""

from __future__ import annotations

from typing import Any

import httpx

from constants import API_BASE_URL, DEFAULT_STUDENT_ID

_TIMEOUT = httpx.Timeout(5.0)

__all__ = [
    "DEFAULT_STUDENT_ID",
    "facility_availability",
    "facility_book",
    "facility_bookings",
    "facility_cancel",
    "facility_list",
    "ukb_clubs",
    "ukb_course",
    "ukb_courses",
    "ukb_facilities",
    "ukb_student_timetable",
]


def _request(method: str, path: str, **kwargs: Any) -> Any:
    """Perform a request, returning parsed JSON or an ``{"error": ...}`` dict."""
    url = f"{API_BASE_URL}{path}"
    try:
        resp = httpx.request(method, url, timeout=_TIMEOUT, **kwargs)
    except httpx.RequestError:
        return {
            "error": (
                "The campus service is unavailable. Make sure the mock backend is running "
                "(`docker compose up`)."
            )
        }
    if resp.status_code >= 400:
        detail = _safe_detail(resp)
        return {"error": detail, "status_code": resp.status_code}
    if resp.status_code == 204:
        return {"success": True}
    return resp.json()


def _safe_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
    except ValueError:
        pass
    return f"Request failed with status {resp.status_code}."


# --- University Knowledge Base (read-only) ---------------------------------


def ukb_courses(
    code: str | None = None, day: str | None = None, lecturer: str | None = None
) -> Any:
    params = {k: v for k, v in {"code": code, "day": day, "lecturer": lecturer}.items() if v}
    return _request("GET", "/ukb/courses", params=params)


def ukb_course(code: str) -> Any:
    return _request("GET", f"/ukb/courses/{code}")


def ukb_student_timetable(student_id: str = DEFAULT_STUDENT_ID) -> Any:
    return _request("GET", f"/ukb/students/{student_id}/timetable")


def ukb_clubs(interest: str | None = None) -> Any:
    params = {"interest": interest} if interest else {}
    return _request("GET", "/ukb/clubs", params=params)


def ukb_facilities() -> Any:
    return _request("GET", "/ukb/facilities")


# --- Facility Booking ------------------------------------------------------


def facility_list(type: str | None = None) -> Any:
    params = {"type": type} if type else {}
    return _request("GET", "/facility/facilities", params=params)


def facility_availability(facility_id: str, date: str) -> Any:
    return _request(
        "GET", "/facility/availability", params={"facility_id": facility_id, "date": date}
    )


def facility_book(
    facility_id: str,
    date: str,
    start_time: str,
    end_time: str,
    student_id: str = DEFAULT_STUDENT_ID,
) -> Any:
    return _request(
        "POST",
        "/facility/bookings",
        json={
            "student_id": student_id,
            "facility_id": facility_id,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
        },
    )


def facility_bookings(student_id: str = DEFAULT_STUDENT_ID) -> Any:
    return _request("GET", "/facility/bookings", params={"student_id": student_id})


def facility_cancel(booking_id: int) -> Any:
    return _request("DELETE", f"/facility/bookings/{booking_id}")
