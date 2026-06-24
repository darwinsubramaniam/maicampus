"""Knowledge Base settings — sync the student's timetable from the UKB into the calendar."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import flet as ft

from constants import API_BASE_URL

if TYPE_CHECKING:
    from collections.abc import Callable


def _health_row(label: str) -> tuple[ft.Row, ft.Icon, ft.Text]:
    """Build a status row (icon + service name + detail) for the health panel."""
    icon = ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED, size=18, color=ft.Colors.ON_SURFACE_VARIANT)
    detail = ft.Text("Not checked", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Row(
                spacing=8,
                controls=[
                    icon,
                    ft.Text(label, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                ],
            ),
            detail,
        ],
    )
    return row, icon, detail


def create_knowledge_settings(page: ft.Page, get_user_context: Callable | None = None) -> ft.Container:
    status_text = ft.Text("", color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER)
    sync_btn_text = ft.Text("Sync from Knowledge Base", color=ft.Colors.WHITE)

    # --- API health check ---
    ukb_row, ukb_icon, ukb_detail = _health_row("Knowledge Base API")
    fac_row, fac_icon, fac_detail = _health_row("Facility Booking API")
    health_btn_text = ft.Text("Check API Health", color=ft.Colors.TEAL)

    def _apply_health(icon: ft.Icon, detail: ft.Text, result: dict) -> None:
        if result.get("ok"):
            icon.icon = ft.Icons.CHECK_CIRCLE
            icon.color = ft.Colors.TEAL
            latency = result.get("latency_ms")
            detail.value = f"Online · {latency} ms" if latency is not None else "Online"
            detail.color = ft.Colors.TEAL
        else:
            icon.icon = ft.Icons.ERROR
            icon.color = ft.Colors.ERROR
            detail.value = result.get("detail", "Offline")
            detail.color = ft.Colors.ERROR

    def do_health_check(e):
        health_btn_text.value = "Checking..."
        for icon, detail in ((ukb_icon, ukb_detail), (fac_icon, fac_detail)):
            icon.icon = ft.Icons.RADIO_BUTTON_UNCHECKED
            icon.color = ft.Colors.ON_SURFACE_VARIANT
            detail.value = "Checking..."
            detail.color = ft.Colors.ON_SURFACE_VARIANT
        page.update()

        def _run():
            from campus_api import facility_health, ukb_health

            _apply_health(ukb_icon, ukb_detail, ukb_health())
            _apply_health(fac_icon, fac_detail, facility_health())
            health_btn_text.value = "Check API Health"
            page.update()

        threading.Thread(target=_run, daemon=True).start()

    def do_sync(e):
        sync_btn_text.value = "Syncing..."
        status_text.value = ""
        page.update()

        def _run():
            import tools

            # Run through the tool registry so the sync is scoped to the authenticated user.
            ctx = get_user_context() if get_user_context else None
            result = tools.execute("sync_my_classes", {}, ctx)
            sync_btn_text.value = "Sync from Knowledge Base"
            if "error" in result:
                status_text.value = result["error"]
                status_text.color = ft.Colors.ERROR
            else:
                status_text.value = result.get("message", "Sync complete.")
                status_text.color = ft.Colors.TEAL
            page.update()

        threading.Thread(target=_run, daemon=True).start()

    return ft.Container(
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.SCHOOL, size=40, color=ft.Colors.TEAL),
                ft.Container(height=10),
                ft.Text(
                    "University Knowledge Base",
                    size=16,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.ON_SURFACE,
                ),
                ft.Container(height=8),
                ft.Text(
                    "Pull your enrolled classes from the campus Knowledge Base and add them to your "
                    "calendar as recurring weekly events. Run it again any time — existing classes "
                    "are not duplicated.",
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=20),
                ft.FilledButton(
                    content=sync_btn_text,
                    icon=ft.Icons.SYNC,
                    on_click=do_sync,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.TEAL, color=ft.Colors.WHITE),
                ),
                ft.Container(height=10),
                status_text,
                ft.Container(height=16),
                ft.Text(
                    f"Connected to: {API_BASE_URL}",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    italic=True,
                ),
                ft.Container(height=20),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                ft.Container(height=16),
                ft.Text(
                    "Service Status",
                    size=16,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.ON_SURFACE,
                ),
                ft.Container(height=12),
                ft.Container(
                    content=ft.Column(spacing=12, controls=[ukb_row, fac_row]),
                    width=360,
                ),
                ft.Container(height=16),
                ft.OutlinedButton(
                    content=health_btn_text,
                    icon=ft.Icons.MONITOR_HEART_OUTLINED,
                    on_click=do_health_check,
                    style=ft.ButtonStyle(side=ft.BorderSide(1, ft.Colors.TEAL)),
                ),
            ],
        ),
        padding=20,
    )
