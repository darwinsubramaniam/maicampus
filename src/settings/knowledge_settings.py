"""Knowledge Base settings — sync the student's timetable from the UKB into the calendar."""

from __future__ import annotations

import threading

import flet as ft

from constants import API_BASE_URL


def create_knowledge_settings(page: ft.Page) -> ft.Container:
    status_text = ft.Text("", color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER)
    sync_btn_text = ft.Text("Sync from Knowledge Base", color=ft.Colors.WHITE)

    def do_sync(e):
        sync_btn_text.value = "Syncing..."
        status_text.value = ""
        page.update()

        def _run():
            from tools.ukb_tools import sync_timetable_from_ukb

            result = sync_timetable_from_ukb()
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
            ],
        ),
        padding=20,
    )
