"""Main chat view — orchestrates ChatEngine with session management, sidebar, and notifications."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import flet as ft

from chat.chat_core import ChatEngine
from chat.message import ChatMessage
from chat.session_store import SessionStore
from chat.sidebar import create_sidebar
from constants import PROFILE_CACHE_PATH
from settings.profile_settings import load_profile

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
    get_calendar_context: Callable | None = None,
    notifications: NotificationCenter | None = None,
) -> ft.Row:
    store = SessionStore()
    profile: dict = {"name": "You", "pic_path": ""}
    state: dict = {"session": None}

    # --- Tool execution notification ---
    def _on_tool_executed(name, result):
        if name == "create_calendar_event" and result.get("success") and notifications:
            notifications.add(
                f"Added to calendar: {result.get('title', 'Event')}",
                icon=ft.Icons.CALENDAR_MONTH,
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
    )

    def _on_response_complete():
        _save_to_db()

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
        icon_color=ft.Colors.TEAL_700,
    )

    header_controls = [
        toggle_btn,
        ft.Icon(ft.Icons.SCHOOL, color=ft.Colors.TEAL, size=20),
        ft.Text("MAI Campus", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.TEAL_700),
        ft.Container(expand=True),
    ]
    if notifications:
        header_controls.append(notifications.bell_button)

    chat_header = ft.Container(
        content=ft.Row(controls=header_controls, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
        padding=ft.Padding(left=4, right=8, top=6, bottom=6),
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
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

    # --- Profile loading ---
    if PROFILE_CACHE_PATH.exists():
        try:
            cached = json.loads(PROFILE_CACHE_PATH.read_text())
            profile["name"] = cached.get("name") or "You"
            profile["pic_path"] = cached.get("pic_path") or ""
        except Exception:
            pass

    async def _init_chat():
        try:
            p = await load_profile()
            profile["name"] = p.get("name") or "You"
            profile["pic_path"] = p.get("pic_path") or ""
            PROFILE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            PROFILE_CACHE_PATH.write_text(json.dumps({"name": profile["name"], "pic_path": profile["pic_path"]}))
        except Exception:
            pass

        sessions = store.get_all_sessions()
        if sessions:
            load_session(sessions[0])
        page.update()

    page.run_task(_init_chat)

    # Sync session restore with cached profile
    if profile["name"] != "You" or profile["pic_path"]:
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
        page.update()

    return view
