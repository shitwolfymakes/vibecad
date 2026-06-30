# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher constraint inspection tool."""

from __future__ import annotations

from typing import Any

from .common import get_sketch, profile_validation, solver_status


TOOL_SPEC = {
    "name": "sketcher.list_constraints",
    "description": (
        "List Sketcher constraints with stable handles, names, driving/reference state, "
        "geometry references, datum values, and expressions so later edits can target "
        "semantic names instead of guessed indices."
    ),
    "contextual": True,
    "safety": "READ",
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "include_geometry": {"type": "boolean", "default": False},
        },
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    include_geometry: bool = False,
) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    summary = service.sketcher_summary(getattr(sketch, "Name", None))
    result = {
        "ok": True,
        "sketch": getattr(sketch, "Name", None),
        "sketch_label": getattr(sketch, "Label", getattr(sketch, "Name", None)),
        "constraint_count": summary.get("constraint_count", 0),
        "constraints": summary.get("constraints", []),
        "solver_status": solver_status(service, sketch),
        "profile_validation": profile_validation(service, sketch),
    }
    if include_geometry:
        result["geometry"] = summary.get("geometry", [])
        result["geometry_count"] = summary.get("geometry_count", 0)
    return result
