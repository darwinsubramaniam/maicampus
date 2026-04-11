from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import date

from campus_calendar.event_model import EVENT_LABELS, event_time_str, event_type_from_str


def create_day_detail(on_edit: Callable, on_delete: Callable) -> tuple[ft.Container, Callable]:
    """
    Returns (container, refresh(selected_date, events)).
    on_edit(event) and on_delete(event_id) are callbacks.
    """

    date_header = ft.Text("", size=18, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE)
    event_list = ft.ListView(expand=True, spacing=8, padding=ft.Padding(left=0, right=0, top=8, bottom=8))

    empty_state = ft.Container(
        content=ft.Column(
            controls=[
                ft.Icon(ft.Icons.EVENT_AVAILABLE, size=48, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.4),
                ft.Container(height=8),
                ft.Text("No events", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        alignment=ft.Alignment.CENTER,
        expand=True,
    )

    def render(selected_date: date, events: list[dict]):
        date_header.value = selected_date.strftime("%A, %B %d, %Y")
        event_list.controls.clear()

        if not events:
            event_list.controls.append(empty_state)
        else:
            for event in events:
                event_type = event_type_from_str(event.get("type", "custom"))
                label = EVENT_LABELS.get(event_type, "Event")
                color = event.get("color", "#6A1B9A")
                time_str = event_time_str(event)

                card = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(width=4, height=50, bgcolor=color, border_radius=2),
                            ft.Container(width=8),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        event.get("title", ""),
                                        size=14,
                                        weight=ft.FontWeight.W_600,
                                        color=ft.Colors.ON_SURFACE,
                                    ),
                                    ft.Row(
                                        controls=[
                                            ft.Text(time_str, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ft.Container(
                                                content=ft.Text(label, size=10, color=color),
                                                padding=ft.Padding(left=6, right=6, top=2, bottom=2),
                                                border_radius=4,
                                                bgcolor=ft.Colors.with_opacity(0.1, color),
                                            ),
                                        ],
                                        spacing=8,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                icon_size=16,
                                icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                tooltip="Edit",
                                on_click=lambda e, ev=event: on_edit(ev),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=16,
                                icon_color=ft.Colors.GREY_400,
                                tooltip="Delete",
                                on_click=lambda e, eid=event["id"]: on_delete(eid),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(left=12, right=4, top=10, bottom=10),
                    border_radius=10,
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                )
                event_list.controls.append(card)

    container = ft.Container(
        content=ft.Column(
            controls=[
                date_header,
                ft.Divider(height=1),
                event_list,
            ],
            spacing=8,
            expand=True,
        ),
        expand=True,
        padding=ft.Padding(left=16, right=16, top=12, bottom=12),
    )

    return container, render
