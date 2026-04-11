from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from collections.abc import Callable

from constants import relative_time as _relative_time


def create_sidebar(
    on_new_chat: Callable,
    on_select_session: Callable,
    on_delete_session: Callable,
    get_sessions: Callable,
    active_session_id: Callable,
) -> tuple[ft.Container, Callable]:

    session_list = ft.ListView(expand=True, spacing=2, padding=ft.Padding(left=8, right=8, top=4, bottom=8))

    def render():
        sessions = get_sessions()
        current_id = active_session_id()
        session_list.controls.clear()
        for session in sessions:
            is_active = session["id"] == current_id
            is_checkin = session.get("session_type") == "checkin"
            title_controls = []
            if is_checkin:
                title_controls.append(
                    ft.Container(
                        content=ft.Text("CHECK-IN", size=8, color=ft.Colors.ORANGE, weight=ft.FontWeight.BOLD),
                        padding=ft.Padding(left=4, right=4, top=1, bottom=1),
                        border_radius=3,
                        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.ORANGE),
                    )
                )
            tile = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            [
                                *title_controls,
                                ft.Text(
                                    session.get("title", "New Chat"),
                                    size=13,
                                    weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL,
                                    color=ft.Colors.TEAL_700 if is_active else ft.Colors.ON_SURFACE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                                ft.Text(
                                    _relative_time(session.get("updated_at", "")),
                                    size=10,
                                    color=ft.Colors.GREY_500,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=14,
                            icon_color=ft.Colors.GREY_400,
                            tooltip="Delete",
                            on_click=lambda e, sid=session["id"]: on_delete_session(sid),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(left=12, right=4, top=8, bottom=8),
                border_radius=10,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if is_active else None,
                on_click=lambda e, s=session: on_select_session(s),
                ink=True,
            )
            session_list.controls.append(tile)

    new_chat_btn = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.ADD_ROUNDED, size=18, color=ft.Colors.TEAL),
                ft.Text("New Chat", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.TEAL_700),
            ],
            spacing=8,
        ),
        padding=ft.Padding(left=14, right=14, top=10, bottom=10),
        border_radius=10,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.TEAL)),
        ink=True,
        on_click=lambda e: on_new_chat(),
    )

    sidebar = ft.Container(
        width=260,
        border=ft.Border(right=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
        content=ft.Column(
            controls=[
                ft.Container(
                    content=ft.Text("History", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500),
                    padding=ft.Padding(left=16, right=16, top=14, bottom=4),
                ),
                ft.Container(content=new_chat_btn, padding=ft.Padding(left=8, right=8, top=0, bottom=4)),
                session_list,
            ],
            spacing=0,
            expand=True,
        ),
    )

    render()
    return sidebar, render
