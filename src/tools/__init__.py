from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from services import UserContext


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict  # JSON Schema format {"type": "object", "properties": {...}, "required": [...]}
    handler: Callable[[dict], dict]


_REGISTRY: dict[str, ToolDefinition] = {}


def register(tool: ToolDefinition):
    _REGISTRY[tool.name] = tool


def get_all() -> list[ToolDefinition]:
    return list(_REGISTRY.values())


def get_tool(name: str) -> ToolDefinition | None:
    return _REGISTRY.get(name)


def execute(name: str, arguments: dict, context: UserContext | None = None) -> dict:
    """Run a tool. ``context`` binds the authenticated user so the handler's store/API calls
    are scoped to the right person; it is set for the duration of the handler in this thread."""
    from observability import get_logger

    log = get_logger("tools")
    tool = _REGISTRY.get(name)
    if not tool:
        log.warning("tool call for unknown tool %r", name)
        return {"error": f"Unknown tool: {name}"}

    import services

    log.info("tool ▶ %s args=%s", name, arguments)
    token = services.set_request_context(context) if context is not None else None
    try:
        result = tool.handler(arguments)
    except Exception as e:
        log.exception("tool ✖ %s raised", name)
        return {"error": str(e)}
    finally:
        if token is not None:
            services.reset_request_context(token)
    status = "error" if isinstance(result, dict) and "error" in result else "ok"
    log.info("tool ◀ %s [%s]", name, status)
    return result
