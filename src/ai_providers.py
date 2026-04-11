from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
from enum import Enum


class Provider(Enum):
    OPENAI = "OpenAI"
    CLAUDE = "Claude"
    GEMINI = "Gemini"


DEFAULT_MODELS = {
    Provider.OPENAI: "gpt-4o",
    Provider.CLAUDE: "claude-sonnet-4-20250514",
    Provider.GEMINI: "gemini-2.5-flash",
}


@dataclass
class ProviderConfig:
    provider: Provider
    api_key: str
    model: str | None = None

    @property
    def effective_model(self) -> str:
        return self.model or DEFAULT_MODELS[self.provider]


@dataclass
class TextChunk:
    text: str


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: dict


StreamItem = TextChunk | ToolCall


def stream_response(
    config: ProviderConfig,
    messages: list[dict],
    tools: list | None = None,
) -> Generator[StreamItem]:
    """Stream AI response. Yields TextChunk for text and ToolCall for tool invocations."""
    system_msg = None
    chat_messages = messages
    if messages and messages[0]["role"] == "system":
        system_msg = messages[0]["content"]
        chat_messages = messages[1:]

    match config.provider:
        case Provider.OPENAI:
            yield from _stream_openai(config, messages, tools=tools)
        case Provider.CLAUDE:
            yield from _stream_claude(config, chat_messages, system=system_msg, tools=tools)
        case Provider.GEMINI:
            yield from _stream_gemini(config, chat_messages, system=system_msg, tools=tools)


def _stream_openai(
    config: ProviderConfig,
    messages: list[dict],
    tools: list | None = None,
) -> Generator[StreamItem]:
    from openai import OpenAI

    client = OpenAI(api_key=config.api_key)
    kwargs = {
        "model": config.effective_model,
        "messages": messages,
        "stream": True,
    }
    if tools:
        kwargs["tools"] = tools

    stream = client.chat.completions.create(**kwargs)

    # Accumulate tool call arguments across chunks
    tool_calls_acc: dict[int, dict] = {}  # index -> {"id", "name", "arguments"}

    for chunk in stream:
        choice = chunk.choices[0]
        delta = choice.delta

        if delta.content:
            yield TextChunk(delta.content)

        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {"id": tc.id or "", "name": tc.function.name or "", "arguments": ""}
                if tc.id:
                    tool_calls_acc[idx]["id"] = tc.id
                if tc.function.name:
                    tool_calls_acc[idx]["name"] = tc.function.name
                if tc.function.arguments:
                    tool_calls_acc[idx]["arguments"] += tc.function.arguments

        if choice.finish_reason == "tool_calls":
            for tc_data in tool_calls_acc.values():
                try:
                    args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}
                yield ToolCall(call_id=tc_data["id"], name=tc_data["name"], arguments=args)


def _stream_claude(
    config: ProviderConfig,
    messages: list[dict],
    system: str | None = None,
    tools: list | None = None,
) -> Generator[StreamItem]:
    from anthropic import Anthropic

    client = Anthropic(api_key=config.api_key)
    kwargs = {
        "model": config.effective_model,
        "max_tokens": 4096,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools

    with client.messages.stream(**kwargs) as stream:
        current_tool: dict | None = None
        tool_json_parts: list[str] = []

        for event in stream:
            if hasattr(event, "type"):
                if event.type == "content_block_start":
                    block = event.content_block
                    if hasattr(block, "type") and block.type == "tool_use":
                        current_tool = {"id": block.id, "name": block.name}
                        tool_json_parts = []
                    elif hasattr(block, "type") and block.type == "text":
                        pass  # text block starting

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "type"):
                        if delta.type == "text_delta":
                            yield TextChunk(delta.text)
                        elif delta.type == "input_json_delta" and current_tool:
                            tool_json_parts.append(delta.partial_json)

                elif event.type == "content_block_stop":
                    if current_tool:
                        json_str = "".join(tool_json_parts)
                        try:
                            args = json.loads(json_str) if json_str else {}
                        except json.JSONDecodeError:
                            args = {}
                        yield ToolCall(call_id=current_tool["id"], name=current_tool["name"], arguments=args)
                        current_tool = None
                        tool_json_parts = []


def _stream_gemini(
    config: ProviderConfig,
    messages: list[dict],
    system: str | None = None,
    tools: list | None = None,
) -> Generator[StreamItem]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.api_key)

    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        # Handle complex content (tool results)
        parts = msg["content"] if isinstance(msg.get("content"), list) else [{"text": msg["content"]}]
        contents.append({"role": role, "parts": parts})

    config_kwargs = {}
    if system:
        config_kwargs["system_instruction"] = system
    if tools:
        config_kwargs["tools"] = tools

    response = client.models.generate_content_stream(
        model=config.effective_model,
        contents=contents,
        config=types.GenerateContentConfig(**config_kwargs) if config_kwargs else None,
    )
    for chunk in response:
        if chunk.candidates:
            candidate = chunk.candidates[0]
            if not candidate.content:
                continue
            for part in candidate.content.parts or []:
                if hasattr(part, "text") and part.text:
                    yield TextChunk(part.text)
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    yield ToolCall(
                        call_id=fc.name or "",
                        name=fc.name or "",
                        arguments=dict(fc.args) if fc.args else {},
                    )
