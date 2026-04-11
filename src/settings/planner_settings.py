from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from collections.abc import Callable


def create_planner_settings(page: ft.Page, on_scan: Callable | None = None) -> ft.Container:
    status_text = ft.Text("", color=ft.Colors.ON_SURFACE_VARIANT)
    scan_btn_text = ft.Text("Run Scan Now", color=ft.Colors.WHITE)

    def do_scan(e):
        if not on_scan:
            status_text.value = "Planner not initialized yet."
            status_text.color = ft.Colors.ERROR
            page.update()
            return

        scan_btn_text.value = "Scanning..."
        page.update()

        import threading

        def _run():
            try:
                on_scan()  # type: ignore[misc]
                scan_btn_text.value = "Run Scan Now"
                status_text.value = "Scan complete! Check notifications for alerts."
                status_text.color = ft.Colors.TEAL
            except Exception as ex:
                scan_btn_text.value = "Run Scan Now"
                status_text.value = f"Scan failed: {ex}"
                status_text.color = ft.Colors.ERROR
            page.update()

        threading.Thread(target=_run, daemon=True).start()

    return ft.Container(
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.AUTO_AWESOME, size=40, color=ft.Colors.TEAL),
                ft.Container(height=10),
                ft.Text(
                    "Smart Planner",
                    size=16,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.ON_SURFACE,
                ),
                ft.Container(height=8),
                ft.Text(
                    "MAI automatically scans your calendar every 5 hours to check on "
                    "upcoming assignments and exams. You can trigger a scan manually below.",
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=16),
                ft.Column(
                    controls=[
                        ft.Text("What the scan does:", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                        ft.Text(
                            "  - Checks upcoming assignments & exams (next 14 days)",
                            size=12,
                            color=ft.Colors.ON_SURFACE,
                        ),
                        ft.Text("  - Marks overdue tasks automatically", size=12, color=ft.Colors.ON_SURFACE),
                        ft.Text(
                            "  - Creates check-in notifications for pending tasks", size=12, color=ft.Colors.ON_SURFACE
                        ),
                        ft.Text("  - Learns from your completion patterns", size=12, color=ft.Colors.ON_SURFACE),
                    ],
                    spacing=4,
                ),
                ft.Container(height=20),
                ft.FilledButton(
                    content=scan_btn_text,
                    icon=ft.Icons.RADAR,
                    on_click=do_scan,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.TEAL, color=ft.Colors.WHITE),
                ),
                ft.Container(height=10),
                status_text,
            ],
        ),
        padding=20,
    )
