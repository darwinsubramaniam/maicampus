from datetime import date

import flet as ft

from campus_calendar.calendar_memory import get_upcoming_context_block, index_event_to_memory
from campus_calendar.day_detail import create_day_detail
from campus_calendar.event_form import show_event_dialog
from campus_calendar.event_store import CalendarEventStore
from campus_calendar.month_grid import create_month_grid
from memory import MemoryManager


def create_calendar_view(
    page: ft.Page,
    get_memory_manager: callable,
    get_config: callable = None,
    get_calendar_context_fn: callable = None,
    on_tool_executed: callable = None,
    get_user_profile: callable = None,
) -> ft.Stack:
    store = CalendarEventStore()
    selected_date = {"value": date.today()}

    def _refresh_all():
        grid_refresh(selected=selected_date["value"])
        events = store.get_events_for_date(selected_date["value"])
        detail_refresh(selected_date["value"], events)
        page.update()

    def on_day_select(d: date):
        selected_date["value"] = d
        _refresh_all()

    def on_event_save(data: dict):
        event_id = data.pop("id", None)
        if event_id:
            store.update_event(event_id, data)
            event = store.get_event(event_id)
        else:
            event = store.create_event(data)

        mgr = get_memory_manager()
        index_event_to_memory(event, mgr)
        _refresh_all()

    def on_event_edit(event: dict):
        show_event_dialog(page, on_event_save, event)

    def on_event_delete(event_id: str):
        store.delete_event(event_id)
        _refresh_all()

    def on_add_click(e):
        show_event_dialog(page, on_event_save)

    detail_container, detail_refresh = create_day_detail(
        on_edit=on_event_edit,
        on_delete=on_event_delete,
    )

    grid_container, grid_refresh = create_month_grid(
        on_day_select=on_day_select,
        get_events_in_range=store.get_events_in_range,
    )

    # Header
    add_btn = ft.IconButton(
        icon=ft.Icons.ADD_ROUNDED,
        tooltip="Add event",
        on_click=on_add_click,
        icon_color=ft.Colors.TEAL,
        bgcolor=ft.Colors.PRIMARY_CONTAINER,
        style=ft.ButtonStyle(shape=ft.CircleBorder()),
    )

    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.CALENDAR_MONTH, color=ft.Colors.TEAL, size=20),
                ft.Text("Calendar", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.TEAL_700),
                ft.Container(expand=True),
                add_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        padding=ft.Padding(left=16, right=8, top=6, bottom=6),
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
    )

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
    events = store.get_events_for_date(selected_date["value"])
    detail_refresh(selected_date["value"], events)

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
            get_calendar_context=get_calendar_context_fn,
            on_tool_executed=on_tool_executed,
        )
        stack_controls.append(floating)

    return ft.Stack(controls=stack_controls, expand=True)


def get_calendar_context(store: CalendarEventStore) -> str:
    """Get upcoming events context block for AI system prompt."""
    return get_upcoming_context_block(store)
