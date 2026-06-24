"""Account section — sign out of the current Google session.

In the multi-user server build there is no destructive "wipe all data" action (it would affect
every user's shared SurrealDB). This panel signs the current user out and returns to the login
screen; their data stays safely on the server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from collections.abc import Callable


def create_logout_settings(page: ft.Page, on_logout: Callable) -> ft.Container:
    def do_sign_out(e):
        on_logout()

    return ft.Container(
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.LOGOUT, size=40, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Container(height=10),
                ft.Text("Sign out", weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Container(height=8),
                ft.Text(
                    "Sign out of your Google account on this device. Your chats, calendar, and "
                    "memories stay safely on the server and will be here when you sign back in.",
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=20),
                ft.FilledButton(
                    "Sign out",
                    icon=ft.Icons.LOGOUT,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.ERROR, color=ft.Colors.ON_ERROR),
                    on_click=do_sign_out,
                ),
            ],
        ),
        padding=20,
    )
