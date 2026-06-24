from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import flet as ft

from campus_calendar.calendar_memory import get_upcoming_context_block, index_event_to_memory
from campus_calendar.day_detail import create_day_detail
from campus_calendar.event_form import show_event_dialog
from campus_calendar.month_grid import create_month_grid
from memory import MemoryManager as MemoryManager
from ui import view_header

if TYPE_CHECKING:
    from collections.abc import Callable

    from campus_calendar.event_store import CalendarEventStore


def create_calendar_view(
    page: ft.Page,
    get_memory_manager: Callable,
    get_calendar_store: Callable,
    get_config: Callable | None = None,
    get_calendar_context_fn: Callable | None = None,
    on_tool_executed: Callable | None = None,
    get_session_store: Callable | None = None,
    get_user_context: Callable | None = None,
    user_name: str = "You",
    user_pic: str = "",
) -> ft.Stack:
    selected_date = {"value": date.today()}

    def _refresh_all():
        grid_render(selected=selected_date["value"])
        events = get_calendar_store().get_events_for_date(selected_date["value"])
        detail_render(selected_date["value"], events)
        page.update()

    def on_day_select(d: date):
        selected_date["value"] = d
        _refresh_all()

    def on_event_save(data: dict):
        store = get_calendar_store()
        event_id = data.pop("id", None)
        if event_id:
            store.update_event(event_id, data)
            event = store.get_event(event_id)
        else:
            event = store.create_event(data)

        mgr = get_memory_manager()
        if mgr is None or event is None:
            _refresh_all()
            return
        index_event_to_memory(event, mgr)
        _refresh_all()

    def on_event_edit(event: dict):
        show_event_dialog(page, on_event_save, event)

    def on_event_delete(event_id: str):
        get_calendar_store().delete_event(event_id)
        _refresh_all()

    def on_add_click(e):
        show_event_dialog(page, on_event_save)

    detail_container, detail_render = create_day_detail(
        on_edit=on_event_edit,
        on_delete=on_event_delete,
    )

    grid_container, grid_render = create_month_grid(
        on_day_select=on_day_select,
        get_events_in_range=lambda s, e: get_calendar_store().get_events_in_range(s, e),
    )

    # Header
    add_btn = ft.IconButton(
        icon=ft.Icons.ADD_ROUNDED,
        tooltip="Add event",
        on_click=on_add_click,
        icon_color=ft.Colors.PRIMARY,
        bgcolor=ft.Colors.PRIMARY_CONTAINER,
        style=ft.ButtonStyle(shape=ft.CircleBorder()),
    )

    header = view_header("Calendar", ft.Icons.CALENDAR_MONTH, trailing=[add_btn])

    # Layout: grid on left, detail on right
    body = ft.Row(
        controls=[
            grid_container,
            ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
            detail_container,
        ],
        expand=True,
        spacing=0,
    )

    # Initial load
    events = get_calendar_store().get_events_for_date(selected_date["value"])
    detail_render(selected_date["value"], events)

    calendar_content = ft.Column(
        expand=True,
        controls=[header, body],
        spacing=0,
    )

    # Add floating chat if config is available
    stack_controls = [calendar_content]
    if get_config:
        from chat.floating_chat import create_floating_chat

        floating = create_floating_chat(
            page=page,
            get_config=get_config,
            get_memory_manager=get_memory_manager,
            get_session_store=get_session_store,
            get_calendar_context=get_calendar_context_fn,
            on_tool_executed=on_tool_executed,
            get_user_context=get_user_context,
            user_name=user_name,
            user_pic=user_pic,
        )
        stack_controls.append(floating)  # type: ignore[arg-type]

    return ft.Stack(controls=stack_controls, expand=True)  # type: ignore[arg-type]


def get_calendar_context(store: CalendarEventStore) -> str:
    """Get upcoming events context block for AI system prompt."""
    return get_upcoming_context_block(store)
