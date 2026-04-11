from dataclasses import dataclass
from enum import Enum
from typing import Generator


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


def stream_response(config: ProviderConfig, messages: list[dict]) -> Generator[str, None, None]:
    """Stream AI response chunks. Messages format: [{"role": "system"|"user"|"assistant", "content": "..."}]"""
    # Extract optional leading system message
    system_msg = None
    chat_messages = messages
    if messages and messages[0]["role"] == "system":
        system_msg = messages[0]["content"]
        chat_messages = messages[1:]

    match config.provider:
        case Provider.OPENAI:
            yield from _stream_openai(config, messages)  # OpenAI handles system in-line
        case Provider.CLAUDE:
            yield from _stream_claude(config, chat_messages, system=system_msg)
        case Provider.GEMINI:
            yield from _stream_gemini(config, chat_messages, system=system_msg)


def _stream_openai(config: ProviderConfig, messages: list[dict]) -> Generator[str, None, None]:
    from openai import OpenAI

    client = OpenAI(api_key=config.api_key)
    stream = client.chat.completions.create(
        model=config.effective_model,
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        text = chunk.choices[0].delta.content
        if text:
            yield text


def _stream_claude(
    config: ProviderConfig, messages: list[dict], system: str | None = None,
) -> Generator[str, None, None]:
    from anthropic import Anthropic

    client = Anthropic(api_key=config.api_key)
    kwargs = {
        "model": config.effective_model,
        "max_tokens": 4096,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            yield text


def _stream_gemini(
    config: ProviderConfig, messages: list[dict], system: str | None = None,
) -> Generator[str, None, None]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.api_key)

    # Convert messages to Gemini format
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    config_kwargs = {}
    if system:
        config_kwargs["system_instruction"] = system

    response = client.models.generate_content_stream(
        model=config.effective_model,
        contents=contents,
        config=types.GenerateContentConfig(**config_kwargs) if config_kwargs else None,
    )
    for chunk in response:
        if chunk.text:
            yield chunk.text
