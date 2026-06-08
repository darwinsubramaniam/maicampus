from __future__ import annotations

import json
from typing import TYPE_CHECKING

import flet as ft

from constants import PROFILE_CACHE_PATH, make_avatar
from db import get_db, user_ref

if TYPE_CHECKING:
    from collections.abc import Callable

_KEY_PREFIX = "maicampus.profile."


async def load_profile(page: ft.Page | None = None) -> dict:
    """Load saved profile from client storage."""
    from prefs import get_prefs

    prefs = get_prefs()
    name = await prefs.get(f"{_KEY_PREFIX}name") or ""
    email = await prefs.get(f"{_KEY_PREFIX}email") or ""
    pic_path = await prefs.get(f"{_KEY_PREFIX}pic_path") or ""
    return {"name": name, "email": email, "pic_path": pic_path}


async def save_profile(page: ft.Page | None = None, name: str = "", email: str = "", pic_path: str = ""):
    """Persist profile to client storage."""
    from prefs import get_prefs

    prefs = get_prefs()
    await prefs.set(f"{_KEY_PREFIX}name", name)
    await prefs.set(f"{_KEY_PREFIX}email", email)
    await prefs.set(f"{_KEY_PREFIX}pic_path", pic_path)
    # File cache for sync loading
    PROFILE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_CACHE_PATH.write_text(json.dumps({"name": name, "email": email, "pic_path": pic_path}))


def _load_user(user_id: str) -> dict:
    """Read the signed-in user's profile from the SurrealDB `user` record."""
    try:
        rows = get_db().query(
            "SELECT name, email, picture, student_id FROM $rid", {"rid": user_ref(user_id)}
        )
    except Exception:
        return {}
    return rows[0] if rows else {}


def create_profile_settings(page: ft.Page, get_user_context: Callable | None = None) -> ft.Container:
    """Read-only profile, sourced from the authenticated Google account (the `user` record).

    Name, email and photo come from Google SSO and are not editable here — users change them in
    their Google account. This replaces the old per-device editable form (which stored to a
    shared file and didn't reflect the signed-in identity)."""
    ctx = get_user_context() if get_user_context else None
    data = _load_user(ctx.user_id) if ctx else {}

    name = (data.get("name") or "").strip() or "—"
    email = (data.get("email") or "").strip() or "—"
    picture = (data.get("picture") or "").strip()
    matric = (data.get("student_id") or (ctx.student_id if ctx else "") or "").strip()

    def _row(label: str, value: str) -> ft.Container:
        return ft.Container(
            width=420,
            padding=ft.Padding(16, 12, 16, 12),
            border_radius=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(label, size=12, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(value, size=14, color=ft.Colors.ON_SURFACE, selectable=True),
                ],
            ),
        )

    controls = [
        ft.Container(content=make_avatar(picture, radius=44)),
        ft.Container(height=12),
        ft.Text(name, size=20, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
        ft.Container(height=4),
        ft.Text(email, size=13, color=ft.Colors.ON_SURFACE_VARIANT, selectable=True),
        ft.Container(height=20),
        _row("Email", email),
    ]
    if matric:
        controls += [ft.Container(height=10), _row("Student ID", matric)]
    controls += [
        ft.Container(height=18),
        ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
            controls=[
                ft.Icon(ft.Icons.VERIFIED_USER_OUTLINED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(
                    "Synced from your UTM Google account.",
                    size=12, italic=True, color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
        ),
    ]

    return ft.Container(
        content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=controls),
        padding=20,
    )
