import threading

import flet as ft

from ai_providers import ProviderConfig, stream_response
from chat.input_bar import create_input_bar
from chat.message import ChatMessage
from chat.session_store import SessionStore
from chat.sidebar import create_sidebar
from memory import MemoryManager
from settings.profile_settings import load_profile


def create_chat_view(page: ft.Page, get_config: callable, get_memory_manager: callable) -> ft.Row:
    store = SessionStore()
    chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True, padding=20)

    # User profile state (loaded async)
    profile: dict = {"name": "You", "pic_path": ""}

    conversation: list[dict] = []
    state: dict = {"session": None}

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
                mgr: MemoryManager | None = get_memory_manager()
                messages_to_send = list(conversation)

                base_prompt = (
                    "You are MAI, a friendly and proactive student companion for campus life. "
                    "You help students manage their classes, assignments, project deadlines, "
                    "facility bookings, social club activities, and general well-being on campus. "
                    "Be warm, encouraging, and practical. "
                    "When relevant, proactively remind students about deadlines or suggest campus resources."
                )

                if mgr:
                    try:
                        memories = mgr.search_relevant(text)
                        if memories:
                            memory_block = "\n".join(f"- {m}" for m in memories)
                            base_prompt += (
                                "\n\nHere are relevant things you remember about this student:\n"
                                f"{memory_block}\n\n"
                                "Use this context to personalize your response."
                            )
                    except Exception:
                        pass

                messages_to_send = [{"role": "system", "content": base_prompt}] + messages_to_send

                # Run blocking stream in a thread, yield chunks back
                import asyncio
                loop = asyncio.get_event_loop()
                queue = asyncio.Queue()

                def _produce():
                    try:
                        for chunk in stream_response(config, messages_to_send):
                            loop.call_soon_threadsafe(queue.put_nowait, chunk)
                        loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel
                    except Exception as ex:
                        loop.call_soon_threadsafe(queue.put_nowait, ex)

                threading.Thread(target=_produce, daemon=True).start()

                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    if isinstance(item, Exception):
                        raise item
                    if not streaming_started:
                        ai_msg.start_streaming()
                        streaming_started = True
                    collected.append(item)
                    ai_msg.body_text.value = "".join(collected)
                    page.update()

                assistant_response = "".join(collected)
                conversation.append({
                    "role": "assistant",
                    "content": assistant_response,
                    "provider": config.provider.value,
                })

                _save_to_db()
                page.update()

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

    # Sidebar hidden by default
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

    chat_header = ft.Container(
        content=ft.Row(
            controls=[
                toggle_btn,
                ft.Icon(ft.Icons.SCHOOL, color=ft.Colors.TEAL, size=20),
                ft.Text("MAI Campus", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.TEAL_700),
                ft.Container(expand=True),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        padding=ft.Padding(left=4, right=12, top=6, bottom=6),
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
    )

    # Floating scroll-to-bottom button
    scroll_down_btn = ft.IconButton(
        icon=ft.Icons.KEYBOARD_ARROW_DOWN,
        icon_size=22,
        bgcolor=ft.Colors.TEAL,
        icon_color=ft.Colors.WHITE,
        visible=False,
        on_click=lambda e: page.run_task(_scroll_to_bottom),
        style=ft.ButtonStyle(
            shape=ft.CircleBorder(),
            shadow_color=ft.Colors.BLACK,
            elevation=4,
        ),
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
            ft.Container(
                content=scroll_down_btn,
                alignment=ft.Alignment.BOTTOM_CENTER,
                bottom=10,
                right=0,
                left=0,
            ),
        ],
        expand=True,
    )

    chat_panel = ft.Column(expand=True, controls=[chat_header, chat_area, input_bar])

    # Load user profile, then restore most recent session
    async def _init_chat():
        p = await load_profile(page)
        profile["name"] = p.get("name") or "You"
        profile["pic_path"] = p.get("pic_path") or ""

        sessions = store.get_all_sessions()
        if sessions:
            load_session(sessions[0])

    page.run_task(_init_chat)

    return ft.Row(
        expand=True,
        controls=[sidebar_container, sidebar_divider, chat_panel],
        spacing=0,
    )
