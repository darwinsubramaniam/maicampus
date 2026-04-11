import asyncio
import json
import threading
from datetime import date

import flet as ft

from ai_providers import Provider, ProviderConfig, TextChunk, ToolCall, stream_response
from notifications import NotificationCenter
from chat.input_bar import create_input_bar
from chat.message import ChatMessage
from chat.session_store import SessionStore
from chat.sidebar import create_sidebar
from memory import MemoryManager
from settings.profile_settings import load_profile
from tools import execute as execute_tool, get_all as get_all_tools
from tools.converters import get_tools_for_provider


def create_chat_view(page: ft.Page, get_config: callable, get_memory_manager: callable, get_calendar_context: callable = None, notifications: NotificationCenter = None) -> ft.Row:
    store = SessionStore()
    chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True, padding=20)

    profile: dict = {"name": "You", "pic_path": ""}
    conversation: list[dict] = []
    state: dict = {"session": None}

    def _build_checkin_banner(task_title: str, due_date: str = None) -> ft.Container:
        due_text = f" — Due: {due_date}" if due_date else ""
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.FACT_CHECK, size=18, color=ft.Colors.ORANGE),
                            ft.Text(
                                "Progress Check-in",
                                size=13,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.ORANGE,
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Text(
                        f"Task: {task_title}{due_text}",
                        size=12,
                        color=ft.Colors.ON_SURFACE,
                        weight=ft.FontWeight.W_500,
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

    def _active_session_id() -> str | None:
        s = state["session"]
        return s["id"] if s else None

    def _save_to_db():
        if state["session"]:
            store.save_messages(state["session"]["id"], list(conversation))

    def new_chat():
        state["session"] = store.create_session()
        conversation.clear()
        chat_list.controls.clear()
        sidebar_refresh()
        page.update()

    def load_session(session: dict):
        fresh = store.get_session(session["id"])
        if not fresh:
            return
        state["session"] = fresh
        conversation.clear()
        conversation.extend(fresh.get("messages", []))

        chat_list.controls.clear()

        # Show check-in banner if this is a check-in session
        if fresh.get("session_type") == "checkin":
            ctx = fresh.get("checkin_context") or {}
            chat_list.controls.append(
                _build_checkin_banner(ctx.get("task_title", "Task"), ctx.get("due_date"))
            )

        for msg in conversation:
            if msg["role"] == "user":
                chat_list.controls.append(
                    ChatMessage(profile["name"], msg["content"], is_user=True, user_pic=profile["pic_path"])
                )
            elif msg["role"] == "assistant":
                chat_list.controls.append(ChatMessage("MAI", msg["content"]))

        sidebar_refresh()
        page.update()

    def delete_session(session_id: str):
        store.delete_session(session_id)
        if state["session"] and state["session"]["id"] == session_id:
            new_chat()
        else:
            sidebar_refresh()
            page.update()

    def _build_system_prompt(user_text: str) -> str:
        today_str = date.today().isoformat()
        base_prompt = (
            "You are MAI, a friendly and proactive student companion for campus life. "
            "You help students manage their classes, assignments, project deadlines, "
            "facility bookings, social club activities, and general well-being on campus. "
            "Be warm, encouraging, and practical. "
            "When relevant, proactively remind students about deadlines or suggest campus resources.\n\n"
            f"Today's date is {today_str}.\n\n"
            "You have access to tools for managing the student's calendar. "
            "Before creating a calendar event, ask the student to confirm all the details. "
            "When the student confirms, use the create_calendar_event tool. "
            "Use get_upcoming_events or get_events_for_date to check the schedule when asked."
        )

        mgr: MemoryManager | None = get_memory_manager()
        if mgr:
            try:
                memories = mgr.search_relevant(user_text)
                if memories:
                    memory_block = "\n".join(f"- {m}" for m in memories)
                    base_prompt += (
                        "\n\nHere are relevant things you remember about this student:\n"
                        f"{memory_block}\n\n"
                        "Use this context to personalize your response."
                    )
            except Exception:
                pass

        if get_calendar_context:
            try:
                cal_block = get_calendar_context()
                if cal_block:
                    base_prompt += f"\n\n{cal_block}"
            except Exception:
                pass

        # Check-in context
        session = state.get("session")
        if session and session.get("session_type") == "checkin":
            ctx = session.get("checkin_context") or {}
            task_title = ctx.get("task_title", "their task")
            event_id = ctx.get("event_id", "")
            due_date = ctx.get("due_date", "")

            base_prompt += (
                "\n\nIMPORTANT: This is a PROGRESS CHECK-IN session that YOU (MAI) initiated.\n"
                f"You are checking on: \"{task_title}\"\n"
            )
            if event_id:
                base_prompt += f"Event ID: {event_id} (use this when calling update_task_status or log_task_completion)\n"
            if due_date:
                base_prompt += f"Due date: {due_date}\n"
            base_prompt += (
                "\nYour role in this check-in:\n"
                "1. Understand where the student is with this specific task\n"
                "2. Use update_task_status tool to record their progress (use the event_id above)\n"
                "3. If completed, ask how many hours it took and use log_task_completion\n"
                "4. If struggling, offer encouragement and help plan\n"
                "5. Stay focused on THIS task\n"
                "Remember: YOU initiated this conversation."
            )

        return base_prompt

    def _append_tool_turn(provider: Provider, messages: list[dict], tool_calls: list[ToolCall], results: list[dict]):
        """Append tool call + results to messages in provider-specific format."""
        if provider == Provider.OPENAI:
            # OpenAI: assistant message with tool_calls, then tool messages
            openai_tool_calls = []
            for tc in tool_calls:
                openai_tool_calls.append({
                    "id": tc.call_id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                })
            messages.append({"role": "assistant", "tool_calls": openai_tool_calls, "content": None})
            for tc, result in zip(tool_calls, results):
                messages.append({"role": "tool", "tool_call_id": tc.call_id, "content": json.dumps(result)})

        elif provider == Provider.CLAUDE:
            # Claude: assistant content with tool_use blocks, then user with tool_result
            content_blocks = []
            for tc in tool_calls:
                content_blocks.append({"type": "tool_use", "id": tc.call_id, "name": tc.name, "input": tc.arguments})
            messages.append({"role": "assistant", "content": content_blocks})
            tool_results = []
            for tc, result in zip(tool_calls, results):
                tool_results.append({"type": "tool_result", "tool_use_id": tc.call_id, "content": json.dumps(result)})
            messages.append({"role": "user", "content": tool_results})

        elif provider == Provider.GEMINI:
            # Gemini: model turn with function_call parts, user turn with function_response
            fc_parts = [{"function_call": {"name": tc.name, "args": tc.arguments}} for tc in tool_calls]
            messages.append({"role": "assistant", "content": fc_parts})
            fr_parts = [{"function_response": {"name": tc.name, "response": result}} for tc, result in zip(tool_calls, results)]
            messages.append({"role": "user", "content": fr_parts})

    def send_message(e):
        text = message_input.value.strip()
        if not text:
            return

        config: ProviderConfig | None = get_config()
        if config is None:
            page.snack_bar = ft.SnackBar(ft.Text("Configure your AI provider in Settings first."), open=True)
            page.update()
            return

        if state["session"] is None:
            state["session"] = store.create_session()

        conversation.append({"role": "user", "content": text})
        chat_list.controls.append(
            ChatMessage(profile["name"], text, is_user=True, user_pic=profile["pic_path"])
        )
        message_input.value = ""

        if len(conversation) == 1:
            title = text[:40] + ("..." if len(text) > 40 else "")
            store.update_title(state["session"]["id"], title)
            state["session"]["title"] = title

        ai_msg = ChatMessage("MAI", "", is_loading=True)
        chat_list.controls.append(ai_msg)
        page.update()

        async def do_stream_async():
            collected = []
            streaming_started = False
            try:
                system_prompt = _build_system_prompt(text)
                messages_to_send = [{"role": "system", "content": system_prompt}] + list(conversation)
                provider_tools = get_tools_for_provider(config.provider)

                max_tool_rounds = 5
                tool_round = 0

                while tool_round < max_tool_rounds:
                    tool_calls_this_turn: list[ToolCall] = []
                    loop = asyncio.get_event_loop()
                    queue: asyncio.Queue[StreamItem | Exception | None] = asyncio.Queue()

                    def _produce(msgs=messages_to_send, tls=provider_tools):
                        try:
                            for item in stream_response(config, msgs, tools=tls):
                                loop.call_soon_threadsafe(queue.put_nowait, item)
                            loop.call_soon_threadsafe(queue.put_nowait, None)
                        except Exception as ex:
                            loop.call_soon_threadsafe(queue.put_nowait, ex)

                    threading.Thread(target=_produce, daemon=True).start()

                    while True:
                        item = await queue.get()
                        if item is None:
                            break
                        if isinstance(item, Exception):
                            raise item
                        if isinstance(item, TextChunk):
                            if not streaming_started:
                                ai_msg.start_streaming()
                                streaming_started = True
                            collected.append(item.text)
                            ai_msg.body_text.value = "".join(collected)
                            page.update()
                        elif isinstance(item, ToolCall):
                            tool_calls_this_turn.append(item)

                    if not tool_calls_this_turn:
                        break  # No tools called, done

                    # Execute tools and show toast for calendar events
                    results = []
                    for tc in tool_calls_this_turn:
                        result = execute_tool(tc.name, tc.arguments)
                        results.append(result)
                        if tc.name == "create_calendar_event" and result.get("success") and notifications:
                            notifications.add(
                                f"Added to calendar: {result.get('title', 'Event')}",
                                icon=ft.Icons.CALENDAR_MONTH,
                                color=ft.Colors.TEAL,
                            )

                    # Append tool turn to messages
                    _append_tool_turn(config.provider, messages_to_send, tool_calls_this_turn, results)
                    tool_round += 1

                    # Show brief status
                    if not streaming_started:
                        ai_msg.start_streaming()
                        streaming_started = True

                assistant_response = "".join(collected)
                conversation.append({
                    "role": "assistant",
                    "content": assistant_response,
                    "provider": config.provider.value,
                })

                _save_to_db()
                page.update()

                mgr = get_memory_manager()
                if mgr:
                    def _store():
                        try:
                            mgr.add_turn(text, assistant_response)
                        except Exception:
                            pass
                    threading.Thread(target=_store, daemon=True).start()

            except Exception as ex:
                ai_msg.set_error(str(ex))
                page.update()

        page.run_task(do_stream_async)

    input_bar, message_input = create_input_bar(send_message)

    sidebar_container, sidebar_refresh = create_sidebar(
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
            sidebar_refresh()
        page.update()

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

    chat_header_row = ft.Row(
        controls=header_controls,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=8,
    )

    chat_header = ft.Container(
        content=chat_header_row,
        padding=ft.Padding(left=4, right=8, top=6, bottom=6),
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
    )

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
        await chat_list.scroll_to(offset=-1)
        scroll_down_btn.visible = False
        page.update()

    def on_chat_scroll(e: ft.OnScrollEvent):
        at_bottom = e.pixels >= e.max_scroll_extent - 50
        if scroll_down_btn.visible == at_bottom:
            scroll_down_btn.visible = not at_bottom
            page.update()

    chat_list.on_scroll = on_chat_scroll

    chat_area = ft.Stack(
        controls=[
            chat_list,
            ft.Container(content=scroll_down_btn, alignment=ft.Alignment.BOTTOM_CENTER, bottom=10, right=0, left=0),
        ],
        expand=True,
    )

    chat_column = ft.Column(expand=True, controls=[chat_header, chat_area, input_bar])

    # Wrap chat column + notification panel in a Stack so notifications float on top
    chat_stack_controls = [chat_column]
    if notifications:
        chat_stack_controls.append(
            ft.Container(
                content=notifications.panel,
                right=8,
                top=48,
            ),
        )

    chat_panel = ft.Stack(controls=chat_stack_controls, expand=True)

    # Load profile from file-based cache (sync, instant)
    from pathlib import Path
    _profile_cache = Path.home() / ".maicampus" / "profile.json"
    if _profile_cache.exists():
        try:
            import json as _json
            cached = _json.loads(_profile_cache.read_text())
            profile["name"] = cached.get("name") or "You"
            profile["pic_path"] = cached.get("pic_path") or ""
        except Exception:
            pass

    # Load from SharedPreferences async, then restore session
    async def _init_chat():
        try:
            p = await load_profile()
            profile["name"] = p.get("name") or "You"
            profile["pic_path"] = p.get("pic_path") or ""
            # Cache for next sync load
            import json as _json
            _profile_cache.parent.mkdir(parents=True, exist_ok=True)
            _profile_cache.write_text(_json.dumps({"name": profile["name"], "pic_path": profile["pic_path"]}))
        except Exception:
            pass

        # Restore most recent session AFTER profile is loaded
        sessions = store.get_all_sessions()
        if sessions:
            load_session(sessions[0])
        page.update()

    page.run_task(_init_chat)

    # Also restore session sync with cached profile (immediate, no wait)
    if profile["name"] != "You" or profile["pic_path"]:
        sessions = store.get_all_sessions()
        if sessions:
            load_session(sessions[0])

    view = ft.Row(
        expand=True,
        controls=[sidebar_container, sidebar_divider, chat_panel],
        spacing=0,
    )

    # Expose for external access (e.g. planner deep-link)
    view.send_prompt = lambda prompt: _auto_send(prompt)
    view.start_checkin = lambda title, mai_message, event_id=None, due_date=None: _start_checkin(title, mai_message, event_id, due_date)

    def _auto_send(prompt: str):
        message_input.value = prompt
        send_message(None)

    def _start_checkin(title: str, mai_message: str, event_id: str = None, due_date: str = None):
        """Start a progress check-in session initiated by MAI."""
        session = store.create_session(title=f"[Check-in] {title}")
        state["session"] = session

        # Store check-in context in session
        checkin_ctx = {
            "task_title": title,
            "event_id": event_id,
            "due_date": due_date,
        }
        store.update_event_meta(session["id"], {
            "session_type": "checkin",
            "checkin_context": checkin_ctx,
        })
        state["session"]["session_type"] = "checkin"
        state["session"]["checkin_context"] = checkin_ctx

        # Clear current chat
        conversation.clear()
        chat_list.controls.clear()

        # Add check-in banner
        chat_list.controls.append(_build_checkin_banner(title, due_date))

        # Add MAI's check-in message first (MAI initiates, not the user)
        conversation.append({
            "role": "assistant",
            "content": mai_message,
            "provider": "MAI",
        })
        chat_list.controls.append(ChatMessage("MAI", mai_message))

        _save_to_db()
        sidebar_refresh()
        page.update()

    return view
