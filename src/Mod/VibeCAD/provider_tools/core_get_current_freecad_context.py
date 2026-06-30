# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``core.get_current_freecad_context``."""

from __future__ import annotations

from typing import Any

from .base import tool_json_schema


TOOL_NAME = "core.get_current_freecad_context"
FUNCTION_NAME = "core_get_current_freecad_context"


def _model_visible_context(context: dict[str, Any]) -> dict[str, Any]:
    visible = dict(context)
    visible.pop("available_tools", None)
    visible.pop("available_tools_workbench", None)
    visible.pop("provider_tool_schemas", None)
    visible.pop("provider_tool_schemas_workbench", None)
    visible.pop("provider_function_tools", None)
    visible.pop("provider_tool_surface", None)
    visible.pop("tool_shape_report", None)
    return visible


def create(schema: dict[str, Any], context: dict[str, Any], FunctionTool: Any) -> Any:
    async def _invoke(_tool_context, _arguments_json: str):
        return _model_visible_context(context)

    description = (
        "Return the current VibeCAD-visible FreeCAD context for this provider "
        "turn, including document state, active workbench, task panel, screenshot "
        "state, loop state, conversation memory, and recent tool results. This is "
        "a read-only context inspection tool, not a generic CAD operation router.\n\n"
        f"Native VibeCAD tool: {TOOL_NAME}. Workbench: global. Safety: read. "
        "Use this exact function directly."
    )
    return FunctionTool(
        name=FUNCTION_NAME,
        description=description,
        params_json_schema=tool_json_schema(schema),
        on_invoke_tool=_invoke,
        strict_json_schema=False,
    )
