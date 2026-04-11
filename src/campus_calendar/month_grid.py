from __future__ import annotations

import calendar as pycal
from datetime import date, timedelta
from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from collections.abc import Callable

from campus_calendar.event_model import EVENT_COLORS, event_type_from_str

_WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def create_month_grid(
    on_day_select: Callable,
    get_events_in_range: Callable,
) -> tuple[ft.Container, Callable]:
    """
    Returns (container, refresh(year, month, selected_date)).
    on_day_select(date) called when a day is tapped.
    get_events_in_range(start, end) -> dict[date, list[dict]]
    """

    state = {"year": date.today().year, "month": date.today().month, "selected": date.today()}
    month_label = ft.Text("", size=18, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE)
    grid_column = ft.Column(spacing=2)

    def _build_grid():
        year, month = state["year"], state["month"]
        selected = state["selected"]
        today = date.today()

        month_label.value = f"{pycal.month_name[month]} {year}"

        # Get first day and number of days
        first_weekday, num_days = pycal.monthrange(year, month)
        # Monday = 0 in our grid
        first_date = date(year, month, 1)
        last_date = date(year, month, num_days)

        # Extend window to fill grid rows
        grid_start = first_date - timedelta(days=first_weekday)
        remaining = (7 - ((first_weekday + num_days) % 7)) % 7
        grid_end = last_date + timedelta(days=remaining)

        # Fetch events for the visible window
        events_by_date = get_events_in_range(grid_start, grid_end)

        grid_column.controls.clear()

        # Weekday header row
        header_row = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(
                        label,
                        size=11,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    height=28,
                )
                for label in _WEEKDAY_LABELS
            ],
            spacing=2,
        )
        grid_column.controls.append(header_row)

        # Day cells in rows of 7
        current = grid_start
        while current <= grid_end:
            row_controls = []
            for _ in range(7):
                is_current_month = current.month == month
                is_today = current == today
                is_selected = current == selected
                day_events = events_by_date.get(current, [])

                # Event dots (max 3)
                dots = []
                for ev in day_events[:3]:
                    et = event_type_from_str(ev.get("type", "custom"))
                    color = ev.get("color") or EVENT_COLORS.get(et, "#6A1B9A")
                    dots.append(ft.Container(width=6, height=6, border_radius=3, bgcolor=color))
                if len(day_events) > 3:
                    dots.append(ft.Text(f"+{len(day_events) - 3}", size=8, color=ft.Colors.ON_SURFACE_VARIANT))

                dot_row = (
                    ft.Row(controls=dots, spacing=2, alignment=ft.MainAxisAlignment.CENTER)
                    if dots
                    else ft.Container(height=6)
                )

                day_num_color = (
                    ft.Colors.WHITE
                    if is_selected
                    else ft.Colors.ON_SURFACE
                    if is_current_month
                    else ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)
                )

                cell = ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                str(current.day),
                                size=13,
                                weight=ft.FontWeight.W_600 if is_today else ft.FontWeight.NORMAL,
                                color=day_num_color,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            dot_row,
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    expand=True,
                    height=52,
                    border_radius=8,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=ft.Colors.TEAL if is_selected else None,
                    border=ft.Border.all(1.5, ft.Colors.TEAL) if is_today and not is_selected else None,
                    on_click=lambda e, d=current: on_day_select(d),
                    ink=True,
                )
                row_controls.append(cell)
                current += timedelta(days=1)

            grid_column.controls.append(ft.Row(controls=row_controls, spacing=2))

    def prev_month(e):
        if state["month"] == 1:
            state["year"] -= 1
            state["month"] = 12
        else:
            state["month"] -= 1
        _build_grid()
        e.page.update()

    def next_month(e):
        if state["month"] == 12:
            state["year"] += 1
            state["month"] = 1
        else:
            state["month"] += 1
        _build_grid()
        e.page.update()

    def go_today(e):
        today = date.today()
        state["year"] = today.year
        state["month"] = today.month
        state["selected"] = today
        _build_grid()
        on_day_select(today)
        e.page.update()

    header = ft.Row(
        controls=[
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=prev_month, icon_color=ft.Colors.ON_SURFACE),
            month_label,
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=next_month, icon_color=ft.Colors.ON_SURFACE),
            ft.Container(expand=True),
            ft.TextButton("Today", on_click=go_today),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def render(year: int | None = None, month: int | None = None, selected: date | None = None):
        if year is not None:
            state["year"] = year
        if month is not None:
            state["month"] = month
        if selected is not None:
            state["selected"] = selected
        _build_grid()

    container = ft.Container(
        content=ft.Column(
            controls=[header, grid_column],
            spacing=8,
        ),
        padding=ft.Padding(left=12, right=12, top=8, bottom=8),
        width=380,
    )

    _build_grid()
    return container, render
