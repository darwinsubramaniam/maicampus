from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from collections.abc import Callable

from campus_calendar.event_model import EVENT_COLORS, EventType, event_type_from_str

_DAY_ABBRS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
_DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def show_event_dialog(page: ft.Page, on_save: Callable, event: dict | None = None):
    """Show add/edit event dialog. on_save(data: dict) called with form data."""
    is_edit = event is not None

    title_field = ft.TextField(
        label="Title",
        value=event.get("title", "") if event else "",
        autofocus=True,
        color=ft.Colors.ON_SURFACE,
    )

    type_dropdown = ft.Dropdown(
        label="Type",
        options=[ft.DropdownOption(key=t.value, text=t.value.capitalize()) for t in EventType],
        value=event.get("type", EventType.CUSTOM.value) if event else EventType.CUSTOM.value,
        width=200,
    )

    # Date display
    selected_date = {"value": None}
    if event:
        selected_date["value"] = datetime.fromisoformat(event["start_datetime"]).date()  # type: ignore[arg-type]
    date_text = ft.Text(
        selected_date["value"].strftime("%b %d, %Y") if selected_date["value"] else "Select date",
        color=ft.Colors.ON_SURFACE,
    )

    def on_date_change(e):
        selected_date["value"] = e.control.value
        date_text.value = e.control.value.strftime("%b %d, %Y")
        e.control.open = False
        page.update()

    date_picker = ft.DatePicker(
        value=selected_date["value"],
        on_change=on_date_change,
        on_dismiss=lambda e: setattr(e.control, "open", False) or page.update(),
    )
    page.overlay.append(date_picker)

    def pick_date(e):
        date_picker.open = True
        page.update()

    date_btn = ft.OutlinedButton("Pick Date", icon=ft.Icons.CALENDAR_MONTH, on_click=pick_date)

    # Time fields
    start_time = ft.TextField(
        label="Start time (HH:MM)",
        value=datetime.fromisoformat(event["start_datetime"]).strftime("%H:%M") if event else "09:00",
        width=130,
        color=ft.Colors.ON_SURFACE,
    )
    end_time = ft.TextField(
        label="End time (HH:MM)",
        value=datetime.fromisoformat(event["end_datetime"]).strftime("%H:%M") if event else "10:00",
        width=130,
        color=ft.Colors.ON_SURFACE,
    )

    # Recurrence
    rec_rule = event.get("recurrence_rule") if event else None
    rec_days = set()
    if rec_rule and ":" in rec_rule:
        rec_days = set(rec_rule.split(":")[1].split(","))

    rec_enabled = ft.Checkbox(
        label="Repeat weekly",
        value=bool(rec_days),
        label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE),
    )

    day_chips = []
    for abbr, label in zip(_DAY_ABBRS, _DAY_LABELS, strict=True):
        chip = ft.Chip(
            label=ft.Text(label),
            selected=abbr in rec_days,
            on_select=lambda e: None,
            show_checkmark=False,
        )
        day_chips.append((abbr, chip))

    day_row = ft.Row(
        controls=[chip for _, chip in day_chips],
        spacing=4,
        visible=bool(rec_days),
    )

    def toggle_rec(e):
        day_row.visible = rec_enabled.value  # type: ignore[assignment]
        page.update()

    rec_enabled.on_change = toggle_rec

    # Description
    desc_field = ft.TextField(
        label="Description (optional)",
        value=event.get("description", "") if event else "",
        multiline=True,
        min_lines=2,
        max_lines=4,
        color=ft.Colors.ON_SURFACE,
    )

    # Color picker
    current_type = event_type_from_str(event.get("type", "custom")) if event else EventType.CUSTOM
    selected_color = {
        "value": (event.get("color") if event else None)
        or EVENT_COLORS.get(current_type, EVENT_COLORS[EventType.CUSTOM])
    }

    color_swatches = []
    for et in EventType:
        c = EVENT_COLORS[et]
        swatch = ft.Container(
            width=28,
            height=28,
            border_radius=14,
            bgcolor=c,
            border=ft.Border.all(3, ft.Colors.ON_SURFACE if c == selected_color["value"] else ft.Colors.TRANSPARENT),
            on_click=lambda e, color=c: _select_color(color),
            tooltip=et.value.capitalize(),
        )
        color_swatches.append(swatch)

    def _select_color(color):
        selected_color["value"] = color
        for swatch, et in zip(color_swatches, EventType, strict=True):
            c = EVENT_COLORS[et]
            swatch.border = ft.Border.all(3, ft.Colors.ON_SURFACE if c == color else ft.Colors.TRANSPARENT)
        page.update()

    error_text = ft.Text("", color=ft.Colors.ERROR, visible=False)

    def on_type_change(e):
        et = event_type_from_str(type_dropdown.value or "")
        _select_color(EVENT_COLORS.get(et, EVENT_COLORS[EventType.CUSTOM]))

    type_dropdown.on_select = on_type_change

    def save_click(e):
        if not title_field.value.strip():
            error_text.value = "Title is required."
            error_text.visible = True
            page.update()
            return
        if not selected_date["value"]:
            error_text.value = "Please select a date."
            error_text.visible = True
            page.update()
            return

        error_text.visible = False
        d = selected_date["value"]

        # Parse times
        try:
            sh, sm = map(int, start_time.value.strip().split(":"))
            eh, em = map(int, end_time.value.strip().split(":"))
        except ValueError, AttributeError:
            error_text.value = "Invalid time format. Use HH:MM."
            error_text.visible = True
            page.update()
            return

        start_dt = datetime(d.year, d.month, d.day, sh, sm, tzinfo=UTC)
        end_dt = datetime(d.year, d.month, d.day, eh, em, tzinfo=UTC)

        # Build recurrence rule
        rec = None
        if rec_enabled.value:
            chosen = [abbr for abbr, chip in day_chips if chip.selected]
            if chosen:
                rec = f"WEEKLY:{','.join(chosen)}"

        data = {
            "title": title_field.value.strip(),
            "type": type_dropdown.value,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "recurrence_rule": rec,
            "description": desc_field.value.strip(),
            "color": selected_color["value"],
        }

        if is_edit and event is not None:
            data["id"] = event["id"]

        if date_picker in page.overlay:
            page.overlay.remove(date_picker)
        page.pop_dialog()
        page.update()
        on_save(data)

    def cancel_click(e):
        if date_picker in page.overlay:
            page.overlay.remove(date_picker)
        page.pop_dialog()
        page.update()

    dialog = ft.AlertDialog(
        title=ft.Text("Edit Event" if is_edit else "Add Event", color=ft.Colors.ON_SURFACE),
        content=ft.Column(
            controls=[
                title_field,
                ft.Container(height=8),
                type_dropdown,
                ft.Container(height=8),
                ft.Row(controls=[date_btn, date_text], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=8),
                ft.Row(controls=[start_time, end_time], spacing=12),
                ft.Container(height=8),
                rec_enabled,
                day_row,
                ft.Container(height=8),
                desc_field,
                ft.Container(height=8),
                ft.Text("Color", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Row(controls=color_swatches, spacing=8),
                error_text,
            ],
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            width=400,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=cancel_click),
            ft.FilledButton("Save", on_click=save_click),
        ],
    )

    page.show_dialog(dialog)
    page.update()
