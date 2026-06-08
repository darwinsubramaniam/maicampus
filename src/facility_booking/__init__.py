"""Facility Booking view (assignment Flow 6).

Search a facility, pick a date + time, and book it. Booking goes through the shared
``book_facility`` tool, which checks server availability AND the student's local calendar
before confirming and mirroring the booking onto the calendar. Conflicts surface a red
banner with suggested free slots.
"""

from __future__ import annotations

import threading
from datetime import date
from typing import TYPE_CHECKING

import flet as ft

import tools
from ui import FONT_DISPLAY, RADIUS_MD, hairline, soft_shadow, view_header

if TYPE_CHECKING:
    from collections.abc import Callable

_TYPE_LABELS = {
    "library_room": "Library Room",
    "study_pod": "Study Pod",
    "sports_court": "Sports Court",
    "seminar_room": "Seminar Room",
}


def create_facility_view(
    page: ft.Page,
    get_memory_manager: Callable,
    get_config: Callable | None = None,
    get_calendar_context_fn: Callable | None = None,
    on_tool_executed: Callable | None = None,
) -> ft.Stack:
    state: dict = {"facility": None, "items": []}

    # --- Controls -----------------------------------------------------------
    type_filter = ft.Dropdown(
        label="Type",
        value="all",
        options=[
            ft.DropdownOption(key="all", text="All facilities"),
            *[ft.DropdownOption(key=k, text=v) for k, v in _TYPE_LABELS.items()],
        ],
        expand=True,
        dense=True,
        filled=True,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST,
        color=ft.Colors.ON_SURFACE,
    )
    facilities_list = ft.ListView(expand=True, spacing=10, padding=ft.Padding(12, 4, 12, 12))

    def _field(label: str, value: str, width: int) -> ft.TextField:
        return ft.TextField(
            label=label,
            value=value,
            dense=True,
            width=width,
            filled=True,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST,
            color=ft.Colors.ON_SURFACE,
            border_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
        )

    date_field = _field("Date (YYYY-MM-DD)", date.today().isoformat(), 190)
    start_field = _field("Start (HH:MM)", "14:00", 130)
    end_field = _field("End (HH:MM)", "16:00", 130)

    selected_title = ft.Text(
        "Select a facility to book",
        size=18,
        weight=ft.FontWeight.W_700,
        font_family=FONT_DISPLAY,
        color=ft.Colors.ON_SURFACE,
    )
    selected_meta = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    slots_row = ft.Row(wrap=True, spacing=6, run_spacing=6)
    result_area = ft.Container()

    check_btn = ft.OutlinedButton("Check availability", icon=ft.Icons.SEARCH, disabled=True)
    book_btn = ft.FilledButton("Book facility", icon=ft.Icons.EVENT_AVAILABLE, disabled=True)

    # --- Helpers ------------------------------------------------------------
    def _banner(message: str, color, icon) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                [ft.Icon(icon, color=color, size=18), ft.Text(message, size=13, expand=True)],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.12, color),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.4, color)),
            border_radius=8,
            padding=10,
        )

    def _set_result(control: ft.Control | None):
        result_area.content = control
        page.update()

    def _fill_slot(slot: str):
        start, end = slot.split("-")
        start_field.value = start
        end_field.value = end
        page.update()

    def _show_slots(free_slots: list[str]):
        slots_row.controls.clear()
        if not free_slots:
            slots_row.controls.append(ft.Text("No free slots that day.", size=12, italic=True))
        else:
            for slot in free_slots:
                slots_row.controls.append(
                    ft.Chip(label=ft.Text(slot, size=12), on_click=lambda e, sl=slot: _fill_slot(sl))
                )
        page.update()

    # --- Facility list ------------------------------------------------------
    def _facility_card(f: dict) -> ft.Container:
        is_sel = bool(state["facility"]) and state["facility"]["id"] == f["id"]
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.MEETING_ROOM, size=18, color=ft.Colors.PRIMARY),
                            ft.Text(
                                f["name"],
                                size=14,
                                weight=ft.FontWeight.W_700,
                                color=ft.Colors.ON_SURFACE,
                                expand=True,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    str(_TYPE_LABELS.get(f["type"], f["type"])),
                                    size=10,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.PRIMARY,
                                ),
                                bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY),
                                border_radius=6,
                                padding=ft.Padding(8, 3, 8, 3),
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        f"{f['location']}  ·  up to {f['capacity']} pax  ·  {f['hours']}",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=6,
            ),
            padding=14,
            border_radius=RADIUS_MD,
            bgcolor=ft.Colors.PRIMARY_CONTAINER if is_sel else ft.Colors.SURFACE_CONTAINER_LOWEST,
            border=ft.Border.all(
                2 if is_sel else 1,
                ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
            ),
            shadow=None if is_sel else soft_shadow(opacity=0.05, blur=10, y=3),
            on_click=lambda e, fac=f: _select_facility(fac),
            ink=True,
        )

    def _render_facilities():
        facilities_list.controls.clear()
        items = state["items"]
        if not items:
            facilities_list.controls.append(
                ft.Container(ft.Text("No facilities found.", italic=True), padding=12)
            )
        else:
            facilities_list.controls.extend(_facility_card(f) for f in items)
        page.update()

    def _load_facilities():
        facilities_list.controls.clear()
        facilities_list.controls.append(
            ft.Container(
                ft.ProgressRing(width=20, height=20), alignment=ft.Alignment.CENTER, padding=16
            )
        )
        page.update()

        def _work():
            ftype = None if type_filter.value == "all" else type_filter.value
            # Use the shared search_facilities tool so the dict shape (incl. "hours")
            # matches what the cards render — same path the chatbot uses.
            result = tools.execute("search_facilities", {"type": ftype} if ftype else {})
            if "error" in result:
                state["items"] = []
                facilities_list.controls.clear()
                facilities_list.controls.append(
                    _banner(result["error"], ft.Colors.ORANGE, ft.Icons.CLOUD_OFF)
                )
                page.update()
                return
            state["items"] = result["facilities"]
            _render_facilities()

        threading.Thread(target=_work, daemon=True).start()

    def _select_facility(f: dict):
        state["facility"] = f
        selected_title.value = f["name"]
        selected_meta.value = f"{f['location']}  ·  open {f['hours']}"
        check_btn.disabled = False
        book_btn.disabled = False
        slots_row.controls.clear()
        result_area.content = None
        _render_facilities()  # re-highlight selection

    # --- Availability + booking --------------------------------------------
    def _on_check(e):
        f = state["facility"]
        if not f:
            return
        _set_result(_banner("Checking availability…", ft.Colors.TEAL, ft.Icons.SCHEDULE))

        def _work():
            res = tools.execute(
                "check_facility_availability", {"facility_id": f["id"], "date": date_field.value}
            )
            if "error" in res:
                _set_result(_banner(res["error"], ft.Colors.ORANGE, ft.Icons.CLOUD_OFF))
                return
            result_area.content = None
            _show_slots(res.get("free_slots", []))

        threading.Thread(target=_work, daemon=True).start()

    def _on_book(e):
        f = state["facility"]
        if not f:
            return
        book_btn.disabled = True
        _set_result(_banner("Booking…", ft.Colors.TEAL, ft.Icons.SCHEDULE))

        def _work():
            res = tools.execute(
                "book_facility",
                {
                    "facility_id": f["id"],
                    "date": date_field.value,
                    "start_time": start_field.value,
                    "end_time": end_field.value,
                },
            )
            book_btn.disabled = False

            if "error" in res:
                _set_result(_banner(res["error"], ft.Colors.ORANGE, ft.Icons.CLOUD_OFF))
            elif res.get("booked"):
                if on_tool_executed:
                    on_tool_executed("book_facility", res)
                _set_result(_banner(res["message"], ft.Colors.GREEN, ft.Icons.CHECK_CIRCLE))
            else:
                # Conflict — facility or calendar — with suggested alternatives.
                _show_slots(res.get("suggested_slots", []))
                _set_result(_banner(res["message"], ft.Colors.RED, ft.Icons.WARNING_AMBER))

        threading.Thread(target=_work, daemon=True).start()

    type_filter.on_select = lambda e: _load_facilities()
    check_btn.on_click = _on_check
    book_btn.on_click = _on_book

    # --- Layout -------------------------------------------------------------
    header = view_header("Facility Booking", ft.Icons.MEETING_ROOM)

    left = ft.Container(
        width=340,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "FACILITIES",
                                size=11,
                                weight=ft.FontWeight.W_700,
                                font_family=FONT_DISPLAY,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            type_filter,
                        ],
                        spacing=10,
                        tight=True,
                    ),
                    padding=ft.Padding(16, 16, 16, 8),
                ),
                facilities_list,
            ],
            spacing=0,
            expand=True,
        ),
    )

    form_card = ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    "WHEN",
                    size=11,
                    weight=ft.FontWeight.W_700,
                    font_family=FONT_DISPLAY,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Row([date_field, start_field, end_field], wrap=True, spacing=12, run_spacing=12),
                ft.Row([check_btn, book_btn], spacing=12),
            ],
            spacing=16,
            tight=True,
        ),
        padding=20,
        border_radius=RADIUS_MD,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border=hairline("all"),
    )

    right = ft.Container(
        content=ft.Column(
            [
                ft.Column([selected_title, selected_meta], spacing=4, tight=True),
                form_card,
                ft.Text(
                    "Suggested free slots",
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                slots_row,
                result_area,
            ],
            spacing=18,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=28,
        expand=True,
    )

    body = ft.Row(
        [left, ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)), right],
        expand=True,
        spacing=0,
    )

    content = ft.Column([header, body], spacing=0, expand=True)

    _load_facilities()

    stack_controls: list[ft.Control] = [content]
    if get_config:
        from chat.floating_chat import create_floating_chat

        floating = create_floating_chat(
            page=page,
            get_config=get_config,
            get_memory_manager=get_memory_manager,
            get_calendar_context=get_calendar_context_fn,
            on_tool_executed=on_tool_executed,
        )
        stack_controls.append(floating)

    return ft.Stack(controls=stack_controls, expand=True)
