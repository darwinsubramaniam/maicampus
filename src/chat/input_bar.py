from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from collections.abc import Callable


def create_input_bar(on_send: Callable) -> tuple[ft.Container, ft.TextField]:
    """Returns (input_bar_container, text_field_reference)."""
    message_input = ft.TextField(
        hint_text="Message MAI...",
        autofocus=True,
        shift_enter=True,
        min_lines=1,
        max_lines=5,
        filled=True,
        expand=True,
        on_submit=on_send,
        border_radius=24,
        content_padding=ft.Padding(left=16, right=16, top=10, bottom=10),
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=ft.Colors.TEAL_200,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )

    send_btn = ft.IconButton(
        icon=ft.Icons.ARROW_UPWARD_ROUNDED,
        tooltip="Send",
        on_click=on_send,
        icon_color=ft.Colors.WHITE,
        bgcolor=ft.Colors.TEAL,
        icon_size=20,
        style=ft.ButtonStyle(shape=ft.CircleBorder()),
    )

    bar = ft.Container(
        content=ft.Row(
            controls=[message_input, send_btn],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.END,
        ),
        padding=ft.Padding(left=16, right=12, top=8, bottom=12),
    )

    return bar, message_input
