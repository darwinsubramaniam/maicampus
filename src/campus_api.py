"""HTTP client for the mock UTM backend (University Knowledge Base + Facility Booking).

Thin wrapper over httpx that mirrors the module-level style of ``services.py``. Every call
degrades gracefully: on a connection error or non-2xx response it returns a dict with an
``"error"`` key instead of raising, so chatbot tools and the booking UI can show a friendly
message when the backend is not running.
"""

from __future__ import annotations

from typing import Any

import httpx

from constants import API_BASE_URL
from observability import get_logger

_TIMEOUT = httpx.Timeout(5.0)
_log = get_logger("campus_api")

__all__ = [
    "facility_availability",
    "facility_book",
    "facility_bookings",
    "facility_cancel",
    "facility_health",
    "facility_list",
    "ukb_clubs",
    "ukb_course",
    "ukb_courses",
    "ukb_facilities",
    "ukb_health",
    "ukb_student_timetable",
]


def _request(method: str, path: str, **kwargs: Any) -> Any:
    """Perform a request, returning parsed JSON or an ``{"error": ...}`` dict."""
    url = f"{API_BASE_URL}{path}"
    try:
        resp = httpx.request(method, url, timeout=_TIMEOUT, **kwargs)
    except httpx.RequestError as exc:
        _log.warning("campus API unreachable: %s %s (%s)", method, path, exc)
        return {
            "error": "The campus service is currently unavailable. Please try again later."
        }
    if resp.status_code >= 400:
        detail = _safe_detail(resp)
        _log.warning("campus API %s %s → HTTP %d: %s", method, path, resp.status_code, detail)
        return {"error": detail, "status_code": resp.status_code}
    _log.info("campus API %s %s → HTTP %d", method, path, resp.status_code)
    if resp.status_code == 204:
        return {"success": True}
    return resp.json()


def _student_id(explicit: str | None) -> str:
    """Resolve the campus matric for the call: an explicit value, else the current user's
    linked student id (set by ``tools.execute``)."""
    if explicit:
        return explicit
    import services

    return services.current_student_id()


def _safe_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
    except ValueError:
        pass
    return f"Request failed with status {resp.status_code}."


# --- Health checks ---------------------------------------------------------


def _health(path: str) -> dict[str, Any]:
    """Ping a service endpoint and report reachability + round-trip latency.

    Returns ``{"ok": bool, "status_code": int | None, "latency_ms": int | None,
    "detail": str}`` — never raises, so the Settings health panel can render a
    status for both the "up" and "down" cases.
    """
    url = f"{API_BASE_URL}{path}"
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(url)
        latency_ms = round(resp.elapsed.total_seconds() * 1000)
    except httpx.RequestError:
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": None,
            "detail": "Unreachable — the campus service is offline.",
        }
    ok = resp.status_code < 500
    return {
        "ok": ok,
        "status_code": resp.status_code,
        "latency_ms": latency_ms,
        "detail": "Online" if ok else _safe_detail(resp),
    }


def ukb_health() -> dict[str, Any]:
    """Health check for the University Knowledge Base API."""
    return _health("/ukb/facilities")


def facility_health() -> dict[str, Any]:
    """Health check for the Facility Booking API."""
    return _health("/facility/facilities")


# --- University Knowledge Base (read-only) ---------------------------------


def ukb_courses(
    code: str | None = None, day: str | None = None, lecturer: str | None = None
) -> Any:
    params = {k: v for k, v in {"code": code, "day": day, "lecturer": lecturer}.items() if v}
    return _request("GET", "/ukb/courses", params=params)


def ukb_course(code: str) -> Any:
    return _request("GET", f"/ukb/courses/{code}")


def ukb_student_timetable(student_id: str | None = None) -> Any:
    return _request("GET", f"/ukb/students/{_student_id(student_id)}/timetable")


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
    student_id: str | None = None,
) -> Any:
    return _request(
        "POST",
        "/facility/bookings",
        json={
            "student_id": _student_id(student_id),
            "facility_id": facility_id,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
        },
    )


def facility_bookings(student_id: str | None = None) -> Any:
    return _request("GET", "/facility/bookings", params={"student_id": _student_id(student_id)})


def facility_cancel(booking_id: int) -> Any:
    return _request("DELETE", f"/facility/bookings/{booking_id}")
