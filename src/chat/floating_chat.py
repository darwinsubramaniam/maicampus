"""Floating chat bubble + popup window for non-chat pages."""

import flet as ft

from chat.chat_core import ChatEngine
from chat.session_store import SessionStore
from constants import relative_time as _relative_time


def create_floating_chat(
    page: ft.Page,
    get_config: callable,
    get_memory_manager: callable,
    get_calendar_context: callable = None,
    on_tool_executed: callable = None,
    session_store: SessionStore = None,
) -> ft.Stack:
    store = session_store or SessionStore()

    engine = ChatEngine(
        page=page,
        get_config=get_config,
        get_memory_manager=get_memory_manager,
        get_calendar_context=get_calendar_context,
        on_tool_executed=on_tool_executed,
    )

    async def _load_profile():
        from settings.profile_settings import load_profile
        try:
            p = await load_profile()
            engine.user_name = p.get("name") or "You"
            engine.user_pic = p.get("pic_path") or ""
        except Exception:
            pass

    page.run_task(_load_profile)

    state = {"session": None, "open": False, "history_open": False}

    def _on_response():
        if state["session"]:
            store.save_messages(state["session"]["id"], list(engine.conversation))

    engine.on_response_complete = _on_response

    original_send = engine._send_message

    def _send_with_session(e):
        if state["session"] is None:
            state["session"] = store.create_session()
        original_send(e)
        user_msgs = [m for m in engine.conversation if m["role"] == "user"]
        if len(user_msgs) == 1:
            title = user_msgs[0]["content"][:40] + ("..." if len(user_msgs[0]["content"]) > 40 else "")
            store.update_title(state["session"]["id"], title)

    engine._send_message = _send_with_session
    from chat.input_bar import create_input_bar
    engine.input_bar, engine.message_input = create_input_bar(_send_with_session)

    # History panel
    history_list = ft.ListView(spacing=2, height=200, padding=4)

    history_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text("History", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ft.Container(expand=True),
                            ft.TextButton(
                                "New Chat",
                                on_click=lambda e: _new_chat(),
                                style=ft.ButtonStyle(color=ft.Colors.TEAL),
                            ),
                        ],
                    ),
                    padding=ft.Padding(left=8, right=4, top=4, bottom=0),
                ),
                history_list,
            ],
            tight=True,
        ),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=8,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
        visible=False,
    )

    def _refresh_history():
        sessions = store.get_all_sessions()
        current_id = state["session"]["id"] if state["session"] else None
        history_list.controls.clear()
        for session in sessions[:15]:  # Show last 15
            is_active = session["id"] == current_id
            tile = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(
                                    session.get("title", "New Chat"),
                                    size=11,
                                    weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL,
                                    color=ft.Colors.TEAL if is_active else ft.Colors.ON_SURFACE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                                ft.Text(
                                    _relative_time(session.get("updated_at", "")),
                                    size=9,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=1,
                            expand=True,
                        ),
                    ],
                ),
                padding=ft.Padding(left=8, right=8, top=6, bottom=6),
                border_radius=6,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if is_active else None,
                on_click=lambda e, s=session: _load_session(s),
                ink=True,
            )
            history_list.controls.append(tile)

    def _load_session(session: dict):
        fresh = store.get_session(session["id"])
        if not fresh:
            return
        state["session"] = fresh
        engine.clear()
        engine.load_messages(fresh.get("messages", []))
        state["history_open"] = False
        history_panel.visible = False
        page.update()

    def _new_chat():
        state["session"] = store.create_session()
        engine.clear()
        state["history_open"] = False
        history_panel.visible = False
        page.update()

    def _toggle_history(e):
        state["history_open"] = not state["history_open"]
        history_panel.visible = state["history_open"]
        if state["history_open"]:
            _refresh_history()
        page.update()

    # Chat popup
    chat_popup = ft.Container(
        content=ft.Column(
            controls=[
                # Header
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SCHOOL, color=ft.Colors.WHITE, size=18),
                            ft.Text("MAI", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.HISTORY,
                                icon_size=18,
                                icon_color=ft.Colors.WHITE,
                                on_click=_toggle_history,
                                tooltip="Chat history",
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_size=18,
                                icon_color=ft.Colors.WHITE,
                                on_click=lambda e: _toggle(e),
                                tooltip="Close",
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                    bgcolor=ft.Colors.TEAL,
                    padding=ft.Padding(left=12, right=0, top=4, bottom=4),
                    border_radius=ft.BorderRadius(top_left=12, top_right=12, bottom_left=0, bottom_right=0),
                ),
                # History panel (overlays messages when open)
                history_panel,
                # Messages
                engine.chat_list,
                # Input
                engine.input_bar,
            ],
            spacing=0,
            expand=True,
        ),
        width=360,
        height=480,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
        shadow=ft.BoxShadow(
            spread_radius=0, blur_radius=16,
            color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
        visible=False,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )

    # Floating bubble
    bubble = ft.FloatingActionButton(
        icon=ft.Icons.CHAT_BUBBLE_ROUNDED,
        bgcolor=ft.Colors.TEAL,
        on_click=lambda e: _toggle(e),
        mini=False,
        tooltip="Chat with MAI",
    )

    def _toggle(e):
        state["open"] = not state["open"]
        chat_popup.visible = state["open"]
        if not state["open"]:
            state["history_open"] = False
            history_panel.visible = False
        page.update()

    return ft.Stack(
        controls=[
            ft.Container(content=chat_popup, bottom=80, right=16),
            ft.Container(content=bubble, bottom=16, right=16),
        ],
        expand=True,
    )
