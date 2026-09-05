"""Shared MCP hints describing the toolkit's read-only safety boundary."""

from mcp.types import ToolAnnotations

OBSERVATION_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)

SIMULATION_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

__all__ = ["OBSERVATION_ANNOTATIONS", "SIMULATION_ANNOTATIONS"]
