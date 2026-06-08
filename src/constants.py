"""Shared constants and utility functions for MAI Campus."""

import os
from datetime import UTC, datetime
from pathlib import Path

import flet as ft

# Application data directory
APP_DIR = Path.home() / ".maicampus"
BOOTSTRAP_FLAG = APP_DIR / ".bootstrapped"
CHAT_DB_PATH = APP_DIR / "chat_history.json"
CALENDAR_DB_PATH = APP_DIR / "calendar_events.json"
CHROMA_DB_PATH = APP_DIR / "chroma_db"
PROFILE_CACHE_PATH = APP_DIR / "profile.json"

# Mock UTM backend (University Knowledge Base + Facility Booking).
# Run it with `docker compose up --build`; see mock_server/ and docker-compose.yml.
# Host port is 28000 (the in-container webapp overrides this to http://api:8000).
API_BASE_URL = os.environ.get("MAICAMPUS_API_BASE", "http://localhost:28000")
# Demo student identity — Darwin Subramaniam, the FOL-proof scenario student.
DEFAULT_STUDENT_ID = os.environ.get("MAICAMPUS_STUDENT_ID", "MEC255043")


def relative_time(iso_str: str) -> str:
    """Format an ISO timestamp as a relative time string."""
    try:
        dt = datetime.fromisoformat(iso_str)
        now = datetime.now(UTC)
        delta = now - dt
        if delta.days == 0:
            return "Today"
        elif delta.days == 1:
            return "Yesterday"
        elif delta.days < 7:
            return f"{delta.days} days ago"
        else:
            return dt.strftime("%b %d")
    except (ValueError, TypeError):
        return ""


def make_avatar(pic_path: str = "", radius: int = 40) -> ft.CircleAvatar:
    """Create a user avatar with optional profile picture."""
    if pic_path:
        return ft.CircleAvatar(foreground_image_src=pic_path, radius=radius)
    return ft.CircleAvatar(
        content=ft.Icon(ft.Icons.PERSON, size=int(radius * 0.8)),
        radius=radius,
        bgcolor=ft.Colors.PRIMARY_CONTAINER,
    )
