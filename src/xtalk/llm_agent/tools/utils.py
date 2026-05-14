from __future__ import annotations

"""
Helper utilities unrelated to agent decision logic.

This module defines a constructor for a pseudo tool named "tool_call_result".
It wraps each finished tool invocation into a consistent payload so upstream
components (e.g., Pipeline/TTSManager) can consume the result and downstream
modules (e.g., RetrievalManager) can react accordingly.

Notes:
- The tool is NOT registered with the LLM (models never call it directly).
- The payload simply tags a tool result with:
  name: original tool name (e.g., "web_search")
  args: original arguments (verbatim)
  content: textual output from the tool
"""

from typing import Any, Dict, Literal, TypedDict


class ToolCallResultArgs(TypedDict):
    """Serialized result for one completed tool invocation.

    Notes
    -----
    ``name`` stores the original tool name, ``args`` stores the original tool
    arguments, and ``content`` stores the textual tool output.
    """

    name: str
    args: dict[str, Any]
    content: str


class ToolCallResultPayload(TypedDict):
    """Structured stream payload emitted after a tool finishes.
    """

    name: Literal["tool_call_result"]
    args: ToolCallResultArgs


def build_tool_call_result_payload(
    *, name: str, args: Dict[str, Any] | None, content: str
) -> ToolCallResultPayload:
    """Build a normalized payload for tool_call_result events.

    Parameters
    ----------
    name : str
        Original tool name such as ``"web_search"``.
    args : Dict[str, Any] | None
        Original tool arguments.
    content : str
        Textual tool result.

    Returns
    -------
    ToolCallResultPayload
        Structured payload formatted as
        ``{"name": "tool_call_result", "args": {...}}``.
    """
    return {
        "name": "tool_call_result",
        "args": {
            "name": name or "",
            "args": dict(args or {}),
            "content": content or "",
        },
    }
