# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher named datum edit tool."""

from __future__ import annotations

from typing import Any

from .set_constraint_value import run as set_constraint_value


TOOL_SPEC = {
    "name": "sketcher.set_constraint_value_by_name",
    "description": "Edit a Sketcher dimension constraint value by its semantic constraint name.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "constraint_name": {"type": "string"},
            "value": {"type": "number"},
        },
        "required": ["constraint_name", "value"],
    },
}


def run(
    service: Any,
    constraint_name: str,
    value: float,
    sketch_name: str | None = None,
) -> dict[str, Any]:
    sketch = service._get_sketch(sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    try:
        index = int(sketch.getIndexByName(str(constraint_name)))
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "constraint_name": str(constraint_name),
            "available_constraints": service.sketcher_summary(getattr(sketch, "Name", None)).get("constraints", []),
        }
    result = set_constraint_value(
        service,
        sketch_name=getattr(sketch, "Name", None),
        constraint_index=index,
        value=float(value),
    )
    if isinstance(result, dict):
        result["constraint_name"] = str(constraint_name)
    return result
