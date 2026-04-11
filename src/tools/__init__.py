from dataclasses import dataclass, field
from typing import Callable


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


def execute(name: str, arguments: dict) -> dict:
    tool = _REGISTRY.get(name)
    if not tool:
        return {"error": f"Unknown tool: {name}"}
    try:
        return tool.handler(arguments)
    except Exception as e:
        return {"error": str(e)}
