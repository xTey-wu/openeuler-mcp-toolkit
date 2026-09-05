"""Make FastMCP-generated function argument models reject unknown fields."""

from typing import Any

from mcp.server.fastmcp import FastMCP


def enforce_strict_tool_arguments(mcp: FastMCP) -> None:
    """Reject cross-tool or hallucinated fields instead of silently dropping them.

    FastMCP 1.x builds a Pydantic model for each function signature with Pydantic's
    default ``extra='ignore'`` behavior. The toolkit promises typed, validated tools,
    so accepting unknown fields is surprising and made malformed model calls appear
    successful. Rebuild each generated argument model with ``extra='forbid'`` and
    refresh the published JSON schema to include ``additionalProperties: false``.
    """

    manager: Any = getattr(mcp, "_tool_manager", None)
    if manager is None or not hasattr(manager, "list_tools"):
        raise RuntimeError("FastMCP tool manager API is incompatible with strict arguments")

    for tool in manager.list_tools():
        argument_model = tool.fn_metadata.arg_model
        argument_model.model_config["extra"] = "forbid"
        argument_model.model_rebuild(force=True)
        tool.parameters = argument_model.model_json_schema(by_alias=True)


__all__ = ["enforce_strict_tool_arguments"]
