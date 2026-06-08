"""Shared UI primitives — design tokens, fonts, and reusable building blocks.

Centralizes the look-and-feel so every view is pixel-consistent and on-brand.
Import these instead of re-styling headers / cards / chips ad hoc in each view.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from collections.abc import Callable

# --- Type system --------------------------------------------------------------
# Two distinctive variable fonts (weights interpolate, so `weight=` keeps working):
#   Display — Sora: confident, geometric; used for branding + headings.
#   Body    — Plus Jakarta Sans: warm, highly legible; used for everything else.
# Loaded from the Fontsource CDN; Flet falls back to the platform font if offline.
FONT_DISPLAY = "Display"
FONT_BODY = "Body"

_FONTS = {
    FONT_DISPLAY: "https://cdn.jsdelivr.net/fontsource/fonts/sora:vf@latest/latin-wght-normal.ttf",
    FONT_BODY: "https://cdn.jsdelivr.net/fontsource/fonts/plus-jakarta-sans:vf@latest/latin-wght-normal.ttf",
}

# --- Layout tokens ------------------------------------------------------------
HEADER_HEIGHT = 56
RADIUS_SM = 10
RADIUS_MD = 14
RADIUS_LG = 20


def register_fonts(page: ft.Page) -> None:
    """Register the app's custom fonts. Safe to call once at startup."""
    page.fonts = {**(page.fonts or {}), **_FONTS}


def hairline(side: str = "bottom") -> ft.Border:
    """A subtle 1px divider that reads in both light and dark themes."""
    color = ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)
    bs = ft.BorderSide(1, color)
    if side == "bottom":
        return ft.Border(bottom=bs)
    if side == "right":
        return ft.Border(right=bs)
    return ft.Border.all(1, color)


def soft_shadow(opacity: float = 0.12, blur: int = 16, y: int = 6) -> ft.BoxShadow:
    """A restrained drop shadow for floating surfaces (panels, cards)."""
    return ft.BoxShadow(
        spread_radius=0,
        blur_radius=blur,
        color=ft.Colors.with_opacity(opacity, ft.Colors.BLACK),
        offset=ft.Offset(0, y),
    )


def view_header(
    title: str,
    icon: ft.IconData,
    *,
    leading: ft.Control | None = None,
    trailing: list[ft.Control] | None = None,
    subtitle: str | None = None,
) -> ft.Container:
    """A consistent top bar shared by every primary view.

    Fixed height + unified typography means tabs no longer visually jump when
    the user switches between Chat / Calendar / Booking.
    """
    title_block: ft.Control = ft.Text(
        title,
        size=17,
        weight=ft.FontWeight.W_700,
        font_family=FONT_DISPLAY,
        color=ft.Colors.ON_SURFACE,
    )
    if subtitle:
        title_block = ft.Column(
            controls=[
                title_block,
                ft.Text(subtitle, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            spacing=0,
            tight=True,
        )

    row_controls: list[ft.Control] = []
    if leading is not None:
        row_controls.append(leading)
    row_controls.append(
        ft.Container(
            content=ft.Icon(icon, color=ft.Colors.PRIMARY, size=20),
            padding=ft.Padding(left=0, right=0, top=0, bottom=0),
        )
    )
    row_controls.append(title_block)
    row_controls.append(ft.Container(expand=True))
    if trailing:
        row_controls.extend(trailing)

    return ft.Container(
        height=HEADER_HEIGHT,
        content=ft.Row(
            controls=row_controls,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        ),
        padding=ft.Padding(left=12 if leading else 18, right=10, top=0, bottom=0),
        border=hairline("bottom"),
    )


def section_card(content: ft.Control, *, max_width: int = 640, padding: int = 28) -> ft.Container:
    """A framed surface for settings / forms — gives content a crafted container."""
    return ft.Container(
        content=content,
        width=max_width,
        padding=padding,
        border_radius=RADIUS_LG,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        shadow=soft_shadow(opacity=0.06, blur=20, y=8),
    )


def suggestion_chip(label: str, icon: ft.IconData, on_click: Callable) -> ft.Container:
    """A tappable prompt suggestion used in the chat welcome state."""
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(icon, size=16, color=ft.Colors.PRIMARY),
                ft.Text(label, size=13, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.W_500),
            ],
            spacing=8,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(left=14, right=16, top=10, bottom=10),
        border_radius=RADIUS_LG,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
        on_click=lambda e: on_click(),
        ink=True,
    )
