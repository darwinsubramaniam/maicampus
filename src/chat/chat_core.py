"""Shared chat engine — used by both the full chat view and floating chat widget."""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from datetime import date
from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from collections.abc import Callable

from ai_providers import Provider, TextChunk, ToolCall, stream_response
from chat.input_bar import create_input_bar
from chat.message import ChatMessage
from observability import get_logger
from tools import execute as execute_tool
from tools.converters import get_tools_for_provider

_log = get_logger("chat.engine")


class ChatEngine:
    """Manages conversation state, streaming, and tool execution."""

    def __init__(
        self,
        page: ft.Page,
        get_config: Callable,
        get_memory_manager: Callable,
        get_calendar_context: Callable | None = None,
        on_tool_executed: Callable | None = None,
        on_response_complete: Callable | None = None,
        get_user_context: Callable | None = None,
        user_name: str = "You",
        user_pic: str = "",
    ):
        self.page = page
        self.get_config = get_config
        self.get_memory_manager = get_memory_manager
        self.get_calendar_context = get_calendar_context
        # Returns the authenticated services.UserContext — scopes tools + enforces daily limits.
        self.get_user_context = get_user_context
        self.on_tool_executed = on_tool_executed  # callback(tool_name, result)
        self.on_response_complete = on_response_complete  # callback() after AI response saved
        self.user_name = user_name
        self.user_pic = user_pic
        self.checkin_context: dict | None = None  # set by _start_checkin

        self.conversation: list[dict] = []
        self.chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True, padding=20)
        self.input_bar, self.message_input = create_input_bar(self._send_message)

    def clear(self):
        self.conversation.clear()
        self.chat_list.controls.clear()

    def load_messages(self, messages: list[dict]):
        self.conversation.clear()
        self.conversation.extend(messages)
        self.chat_list.controls.clear()
        for msg in messages:
            if msg["role"] == "user":
                self.chat_list.controls.append(
                    ChatMessage(self.user_name, msg["content"], is_user=True, user_pic=self.user_pic)
                )
            elif msg["role"] == "assistant":
                self.chat_list.controls.append(ChatMessage("MAI", msg["content"]))

    def _build_system_prompt(self, user_text: str) -> str:
        today_str = date.today().isoformat()
        base_prompt = (
            "You are MAI, a friendly and proactive student companion for campus life. "
            "You help students manage their classes, assignments, project deadlines, "
            "facility bookings, social club activities, and general well-being on campus. "
            "Be warm, encouraging, and practical. "
            "When relevant, proactively remind students about deadlines or suggest campus resources.\n\n"
            f"Today's date is {today_str}.\n\n"
            "You have access to tools for managing the student's calendar and campus facility bookings. "
            "Before creating a calendar event, ask the student to confirm all the details. "
            "When the student confirms, use the create_calendar_event tool. "
            "Use get_upcoming_events or get_events_for_date to check the schedule when asked.\n"
            "For facility bookings: use search_facilities to show what's bookable, "
            "check_facility_availability to find open slots, and book_facility to reserve one. "
            "Use list_my_bookings to show the student's current bookings, cancel_booking to cancel "
            "one, and reschedule_booking to move one to a new time. Always confirm the facility, "
            "date and time with the student before booking, cancelling, or rescheduling.\n"
            "Facility ids (e.g. FAC05) and booking ids come ONLY from tool results. Copy the id "
            "exactly from the latest search_facilities result for the facility you mean — never "
            "guess an id, reuse one from earlier in the chat, or assume two facilities share an id. "
            "After booking, state the facility name that book_facility returns, not the one you "
            "intended. To check, cancel, or reschedule, FIRST call list_my_bookings and use the "
            "exact booking_id and facility name it returns — treat its result as the source of "
            "truth over your own memory. If a booking looks wrong or missing, show the student what "
            "list_my_bookings actually returned and ask; never silently re-book to 'fix' it."
        )

        # Detect if this is a progress check-in session (MAI initiated)
        is_checkin = len(self.conversation) >= 1 and self.conversation[0].get("role") == "assistant"
        if is_checkin:
            ctx = self.checkin_context or {}
            task_title = ctx.get("task_title", "their task")
            event_id = ctx.get("event_id", "")
            due_date = ctx.get("due_date", "")

            base_prompt += (
                "\n\nIMPORTANT: This is a PROGRESS CHECK-IN session that YOU (MAI) initiated.\n"
                f'You are checking on: "{task_title}"\n'
            )
            if event_id:
                base_prompt += (
                    f"Event ID: {event_id} (use this when calling update_task_status or log_task_completion)\n"
                )
            if due_date:
                base_prompt += f"Due date: {due_date}\n"
            base_prompt += (
                "\nYour role in this check-in:\n"
                "1. Understand where the student is with this specific task (not started, in progress, done)\n"
                "2. Use update_task_status tool to record their progress (use the event_id above)\n"
                "3. If they've completed it, ask how many hours it took and use log_task_completion\n"
                "4. If they're struggling, offer encouragement and help plan\n"
                "5. Be conversational and supportive, not interrogative\n"
                "6. Stay focused on THIS task — don't drift to other topics unless the student brings them up\n"
                "Remember: YOU initiated this conversation, the student is responding to your check-in."
            )

        mgr = self.get_memory_manager()
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

        if self.get_calendar_context:
            try:
                cal_block = self.get_calendar_context()
                if cal_block:
                    base_prompt += f"\n\n{cal_block}"
            except Exception:
                pass

        return base_prompt

    def _append_tool_turn(
        self, provider: Provider, messages: list[dict], tool_calls: list[ToolCall], results: list[dict]
    ):
        if provider in (Provider.OPENAI, Provider.DEEPSEEK):
            # DeepSeek follows the OpenAI tool-call / tool-result message shape.
            openai_tool_calls = [
                {
                    "id": tc.call_id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in tool_calls
            ]
            messages.append({"role": "assistant", "tool_calls": openai_tool_calls, "content": None})
            for tc, result in zip(tool_calls, results, strict=True):
                messages.append({"role": "tool", "tool_call_id": tc.call_id, "content": json.dumps(result)})
        elif provider == Provider.CLAUDE:
            content_blocks = [
                {"type": "tool_use", "id": tc.call_id, "name": tc.name, "input": tc.arguments} for tc in tool_calls
            ]
            messages.append({"role": "assistant", "content": content_blocks})
            tool_results = [
                {"type": "tool_result", "tool_use_id": tc.call_id, "content": json.dumps(result)}
                for tc, result in zip(tool_calls, results, strict=True)
            ]
            messages.append({"role": "user", "content": tool_results})
        elif provider == Provider.GEMINI:
            fc_parts = [{"function_call": {"name": tc.name, "args": tc.arguments}} for tc in tool_calls]
            messages.append({"role": "assistant", "content": fc_parts})
            fr_parts = [
                {"function_response": {"name": tc.name, "response": result}}
                for tc, result in zip(tool_calls, results, strict=True)
            ]
            messages.append({"role": "user", "content": fr_parts})

    def _send_message(self, e):
        text = self.message_input.value.strip()
        if not text:
            return

        config = self.get_config()
        if config is None:
            return

        self.conversation.append({"role": "user", "content": text})
        self.chat_list.controls.append(ChatMessage(self.user_name, text, is_user=True, user_pic=self.user_pic))
        self.message_input.value = ""

        ai_msg = ChatMessage("MAI", "", is_loading=True)
        self.chat_list.controls.append(ai_msg)
        self.page.update()

        user_ctx = self.get_user_context() if self.get_user_context else None

        async def do_stream():
            collected = []
            streaming_started = False
            try:
                # Enforce the per-user daily limit before spending the server's AI budget.
                if user_ctx is not None:
                    from usage import check_and_increment

                    status = check_and_increment(user_ctx.user_id)
                    if not status.allowed:
                        ai_msg.set_error(
                            f"You've reached today's limit of {status.limit} messages. "
                            "It resets tomorrow — see you then!"
                        )
                        self.page.update()
                        return

                system_prompt = self._build_system_prompt(text)
                messages_to_send = [{"role": "system", "content": system_prompt}, *self.conversation]
                provider_tools = get_tools_for_provider(config.provider)

                max_tool_rounds = 5
                tool_round = 0

                while tool_round < max_tool_rounds:
                    _log.info(
                        "stream round %d/%d via %s (%d tools available)",
                        tool_round + 1, max_tool_rounds, config.provider.value, len(provider_tools),
                    )
                    tool_calls_this_turn: list[ToolCall] = []
                    loop = asyncio.get_event_loop()
                    queue: asyncio.Queue = asyncio.Queue()

                    def _produce(msgs=messages_to_send, tls=provider_tools, _loop=loop, _queue=queue):
                        try:
                            for item in stream_response(config, msgs, tools=tls):
                                _loop.call_soon_threadsafe(_queue.put_nowait, item)
                            _loop.call_soon_threadsafe(_queue.put_nowait, None)
                        except Exception as ex:
                            _loop.call_soon_threadsafe(_queue.put_nowait, ex)

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
                            self.page.update()
                        elif isinstance(item, ToolCall):
                            tool_calls_this_turn.append(item)

                    if not tool_calls_this_turn:
                        _log.info("stream round %d: model returned text, no tool calls", tool_round + 1)
                        break

                    _log.info(
                        "stream round %d: model requested tools: %s",
                        tool_round + 1, [tc.name for tc in tool_calls_this_turn],
                    )
                    results = []
                    for tc in tool_calls_this_turn:
                        # Bind the authenticated user so user-scoped tools (calendar, booking,
                        # planner, memory) resolve the right person's stores via the ContextVar.
                        result = execute_tool(tc.name, tc.arguments, user_ctx)
                        results.append(result)
                        if self.on_tool_executed:
                            self.on_tool_executed(tc.name, result)

                    self._append_tool_turn(config.provider, messages_to_send, tool_calls_this_turn, results)
                    tool_round += 1

                    if not streaming_started:
                        ai_msg.start_streaming()
                        streaming_started = True

                assistant_response = "".join(collected)
                self.conversation.append(
                    {
                        "role": "assistant",
                        "content": assistant_response,
                        "provider": config.provider.value,
                    }
                )
                self.page.update()

                if self.on_response_complete:
                    self.on_response_complete()

                mgr = self.get_memory_manager()
                if mgr:

                    def _store():
                        with contextlib.suppress(Exception):
                            mgr.add_turn(text, assistant_response)

                    threading.Thread(target=_store, daemon=True).start()

            except Exception as ex:
                # Surface the real cause in the trace (provider auth/rate errors, tool failures,
                # etc.) — this is what shows up as the red "Error: …" bubble in chat.
                _log.exception("chat stream failed: %s", ex)
                ai_msg.set_error(str(ex))
                self.page.update()

        self.page.run_task(do_stream)

        return text  # Return for callers that need to know the text
