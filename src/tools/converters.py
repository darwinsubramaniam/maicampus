from ai_providers import Provider
from tools import ToolDefinition, get_all


def _to_openai(tool: ToolDefinition) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _to_claude(tool: ToolDefinition) -> dict:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.parameters,
    }


def _to_gemini(tool: ToolDefinition) -> list:
    """Returns a list with one Tool containing all function declarations."""
    from google.genai import types

    def _schema_from_json(schema: dict) -> types.Schema:
        type_map = {
            "string": "STRING",
            "integer": "INTEGER",
            "number": "NUMBER",
            "boolean": "BOOLEAN",
            "array": "ARRAY",
            "object": "OBJECT",
        }
        props = {}
        for name, prop in schema.get("properties", {}).items():
            props[name] = types.Schema(
                type=type_map.get(prop.get("type", "string"), "STRING"),  # type: ignore[arg-type]
                description=prop.get("description", ""),
                enum=prop.get("enum"),
            )
        return types.Schema(
            type="OBJECT",  # type: ignore[arg-type]
            properties=props,
            required=schema.get("required", []),
        )

    return types.FunctionDeclaration(  # type: ignore[return-value]
        name=tool.name,
        description=tool.description,
        parameters=_schema_from_json(tool.parameters),
    )


def get_tools_for_provider(provider: Provider) -> list | None:
    """Convert all registered tools to the format for the given provider."""
    tools = get_all()
    if not tools:
        return None

    if provider == Provider.OPENAI:
        return [_to_openai(t) for t in tools]
    elif provider == Provider.CLAUDE:
        return [_to_claude(t) for t in tools]
    elif provider == Provider.GEMINI:
        from google.genai import types

        declarations = [_to_gemini(t) for t in tools]
        return [types.Tool(function_declarations=declarations)]  # type: ignore[arg-type]
    return None
