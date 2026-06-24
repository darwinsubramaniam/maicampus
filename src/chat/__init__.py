"""Main chat view — orchestrates ChatEngine with session management, sidebar, and notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from chat.chat_core import ChatEngine
from chat.message import ChatMessage
from chat.sidebar import create_sidebar
from ui import FONT_DISPLAY, suggestion_chip, view_header

if TYPE_CHECKING:
    from collections.abc import Callable

    from notifications import NotificationCenter


def _build_checkin_banner(task_title: str, due_date: str | None = None) -> ft.Container:
    due_text = f" — Due: {due_date}" if due_date else ""
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.FACT_CHECK, size=18, color=ft.Colors.ORANGE),
                        ft.Text("Progress Check-in", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE),
                    ],
                    spacing=6,
                ),
                ft.Text(
                    f"Task: {task_title}{due_text}", size=12, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.W_500
                ),
                ft.Text(
                    "This conversation was initiated by MAI to check on your progress. "
                    "Please keep the discussion focused on this task for best tracking.",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    italic=True,
                ),
            ],
            spacing=4,
            tight=True,
        ),
        padding=ft.Padding(left=14, right=14, top=10, bottom=10),
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ORANGE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.ORANGE)),
    )


def create_chat_view(
    page: ft.Page,
    get_config: Callable,
    get_memory_manager: Callable,
    get_session_store: Callable,
    get_calendar_context: Callable | None = None,
    get_user_context: Callable | None = None,
    notifications: NotificationCenter | None = None,
    user_name: str = "You",
    user_pic: str = "",
) -> ft.Row:
    store = get_session_store()
    profile: dict = {"name": user_name or "You", "pic_path": user_pic or ""}
    state: dict = {"session": None}

    # --- Tool execution notification ---
    def _on_tool_executed(name, result):
        if not notifications:
            return
        if name == "create_calendar_event" and result.get("success"):
            notifications.add(
                f"Added to calendar: {result.get('title', 'Event')}",
                icon=ft.Icons.CALENDAR_MONTH,
                color=ft.Colors.TEAL,
            )
        elif name == "book_facility" and result.get("booked"):
            notifications.add(
                f"Booked {result.get('facility', 'facility')} · "
                f"{result.get('date', '')} {result.get('time', '')}",
                icon=ft.Icons.EVENT_AVAILABLE,
                color=ft.Colors.TEAL,
            )
        elif name == "cancel_booking" and result.get("cancelled"):
            notifications.add(
                f"Cancelled booking #{result.get('booking_id')}",
                icon=ft.Icons.EVENT_BUSY,
                color=ft.Colors.ORANGE,
            )
        elif name == "reschedule_booking" and result.get("rescheduled"):
            notifications.add(
                f"Rescheduled {result.get('facility', 'booking')} · "
                f"{result.get('date', '')} {result.get('time', '')}",
                icon=ft.Icons.EVENT_REPEAT,
                color=ft.Colors.TEAL,
            )

    # --- ChatEngine (handles all streaming, tools, system prompt) ---
    engine = ChatEngine(
        page=page,
        get_config=get_config,
        get_memory_manager=get_memory_manager,
        get_calendar_context=get_calendar_context,
        on_tool_executed=_on_tool_executed,
        on_response_complete=lambda: _on_response_complete(),
        get_user_context=get_user_context,
        user_name=profile["name"],
        user_pic=profile["pic_path"],
    )

    def _on_response_complete():
        _save_to_db()

    # --- Welcome / empty state ---
    suggestions = [
        ("What's on my timetable today?", ft.Icons.SCHEDULE),
        ("Book a study pod for tomorrow", ft.Icons.MEETING_ROOM),
        ("When does the library close?", ft.Icons.LOCAL_LIBRARY),
        ("Help me plan my week", ft.Icons.AUTO_AWESOME),
    ]
    welcome = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        padding=32,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
            spacing=0,
            controls=[
                ft.Container(
                    content=ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=34, color=ft.Colors.PRIMARY),
                    width=72,
                    height=72,
                    border_radius=24,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=ft.Colors.PRIMARY_CONTAINER,
                ),
                ft.Container(height=20),
                ft.Text(
                    "Hi, I'm MAI",
                    size=30,
                    weight=ft.FontWeight.W_700,
                    font_family=FONT_DISPLAY,
                    color=ft.Colors.ON_SURFACE,
                ),
                ft.Container(height=6),
                ft.Text(
                    "Your campus companion — classes, deadlines,\nbookings, and everything in between.",
                    size=14,
                    text_align=ft.TextAlign.CENTER,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Container(height=28),
                ft.Container(
                    width=560,
                    content=ft.Row(
                        wrap=True,
                        spacing=10,
                        run_spacing=10,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            suggestion_chip(label, icon, lambda p=label: _auto_send(p))
                            for label, icon in suggestions
                        ],
                    ),
                ),
            ],
        ),
    )

    def _sync_empty():
        welcome.visible = len(engine.chat_list.controls) == 0

    # --- Session management ---
    def _active_session_id() -> str | None:
        s = state["session"]
        return s["id"] if s else None

    def _save_to_db():
        if state["session"]:
            store.save_messages(state["session"]["id"], list(engine.conversation))

    def new_chat():
        state["session"] = store.create_session()
        engine.clear()
        engine.checkin_context = None
        sidebar_render()
        _sync_empty()
        page.update()

    def load_session(session: dict):
        fresh = store.get_session(session["id"])
        if not fresh:
            return
        state["session"] = fresh

        # Set check-in context on engine if this is a check-in session
        if fresh.get("session_type") == "checkin":
            engine.checkin_context = fresh.get("checkin_context")
        else:
            engine.checkin_context = None

        # Update engine profile
        engine.user_name = profile["name"]
        engine.user_pic = profile["pic_path"]

        engine.clear()
        # Add check-in banner if applicable
        if fresh.get("session_type") == "checkin":
            ctx = fresh.get("checkin_context") or {}
            engine.chat_list.controls.append(_build_checkin_banner(ctx.get("task_title", "Task"), ctx.get("due_date")))
        engine.load_messages(fresh.get("messages", []))

        sidebar_render()
        _sync_empty()
        page.update()

    def delete_session(session_id: str):
        store.delete_session(session_id)
        if state["session"] and state["session"]["id"] == session_id:
            new_chat()
        else:
            sidebar_render()
            page.update()

    # --- Send message (wraps ChatEngine with session logic) ---
    def send_message(e):
        text = engine.message_input.value
        if not text or not text.strip():
            return

        config = get_config()
        if config is None:
            return

        if state["session"] is None:
            state["session"] = store.create_session()

        # Auto-title from first user message
        if not engine.conversation:
            title = text.strip()[:40] + ("..." if len(text.strip()) > 40 else "")
            store.update_title(state["session"]["id"], title)
            state["session"]["title"] = title

        # Update engine profile before sending
        engine.user_name = profile["name"]
        engine.user_pic = profile["pic_path"]

        engine._send_message(e)
        _sync_empty()

    # Replace engine's input bar with our session-aware version
    from chat.input_bar import create_input_bar

    engine.input_bar, engine.message_input = create_input_bar(send_message)

    # --- Sidebar ---
    sidebar_container, sidebar_render = create_sidebar(
        on_new_chat=new_chat,
        on_select_session=load_session,
        on_delete_session=delete_session,
        get_sessions=store.get_all_sessions,
        active_session_id=_active_session_id,
    )
    sidebar_container.visible = False
    sidebar_divider = ft.VerticalDivider(width=1, visible=False)

    def toggle_sidebar(e=None):
        sidebar_container.visible = not sidebar_container.visible
        sidebar_divider.visible = sidebar_container.visible
        if sidebar_container.visible:
            sidebar_render()
        page.update()

    # --- Header ---
    toggle_btn = ft.IconButton(
        icon=ft.Icons.MENU,
        tooltip="Chat history",
        on_click=toggle_sidebar,
        icon_color=ft.Colors.ON_SURFACE_VARIANT,
    )

    chat_header = view_header(
        "MAI Campus",
        ft.Icons.SCHOOL,
        leading=toggle_btn,
        trailing=[notifications.bell_button] if notifications else None,
    )

    # --- Scroll-to-bottom button ---
    scroll_down_btn = ft.IconButton(
        icon=ft.Icons.KEYBOARD_ARROW_DOWN,
        icon_size=22,
        bgcolor=ft.Colors.TEAL,
        icon_color=ft.Colors.WHITE,
        visible=False,
        on_click=lambda e: page.run_task(_scroll_to_bottom),
        style=ft.ButtonStyle(shape=ft.CircleBorder(), shadow_color=ft.Colors.BLACK, elevation=4),
    )

    async def _scroll_to_bottom():
        await engine.chat_list.scroll_to(offset=-1)
        scroll_down_btn.visible = False
        page.update()

    def on_chat_scroll(e: ft.OnScrollEvent):
        at_bottom = e.pixels >= e.max_scroll_extent - 50
        if scroll_down_btn.visible == at_bottom:
            scroll_down_btn.visible = not at_bottom
            page.update()

    engine.chat_list.on_scroll = on_chat_scroll

    chat_area = ft.Stack(
        controls=[
            engine.chat_list,
            welcome,
            ft.Container(content=scroll_down_btn, alignment=ft.Alignment.BOTTOM_CENTER, bottom=10, right=0, left=0),
        ],
        expand=True,
    )

    chat_column = ft.Column(expand=True, controls=[chat_header, chat_area, engine.input_bar])

    # Notification panel floating on top
    chat_stack_controls = [chat_column]
    if notifications:
        chat_stack_controls.append(
            ft.Container(content=notifications.panel, right=8, top=48),  # type: ignore[arg-type]
        )
    chat_panel = ft.Stack(controls=chat_stack_controls, expand=True)  # type: ignore[arg-type]

    # --- Restore the most recent session for this user ---
    # Profile (name/pic) comes from the authenticated Google identity passed in by main().
    sessions = store.get_all_sessions()
    if sessions:
        load_session(sessions[0])

    # --- Build view ---
    view = ft.Row(
        expand=True,
        controls=[sidebar_container, sidebar_divider, chat_panel],
        spacing=0,
    )

    view.send_prompt = lambda prompt: _auto_send(prompt)  # type: ignore[attr-defined]
    view.start_checkin = lambda title, mai_message, event_id=None, due_date=None: _start_checkin(  # type: ignore[attr-defined]
        title, mai_message, event_id, due_date
    )

    def _auto_send(prompt: str):
        engine.message_input.value = prompt
        send_message(None)

    def _start_checkin(title: str, mai_message: str, event_id: str | None = None, due_date: str | None = None):
        session = store.create_session(title=f"[Check-in] {title}")
        state["session"] = session

        checkin_ctx = {"task_title": title, "event_id": event_id, "due_date": due_date}
        store.update_event_meta(session["id"], {"session_type": "checkin", "checkin_context": checkin_ctx})
        state["session"]["session_type"] = "checkin"
        state["session"]["checkin_context"] = checkin_ctx

        engine.checkin_context = checkin_ctx
        engine.clear()
        engine.chat_list.controls.append(_build_checkin_banner(title, due_date))

        engine.conversation.append({"role": "assistant", "content": mai_message, "provider": "MAI"})
        engine.chat_list.controls.append(ChatMessage("MAI", mai_message))

        _save_to_db()
        sidebar_render()
        _sync_empty()
        page.update()

    return view
