# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher named constraint lookup tool."""

from __future__ import annotations

from typing import Any

from .common import get_sketch, profile_validation, solver_status


TOOL_SPEC = {
    "name": "sketcher.get_constraint_by_name",
    "description": "Resolve a named Sketcher constraint to its current index and full constraint summary.",
    "contextual": True,
    "safety": "READ",
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "constraint_name": {"type": "string"},
        },
        "required": ["constraint_name"],
    },
}


def run(
    service: Any,
    constraint_name: str,
    sketch_name: str | None = None,
) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
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
    constraints = service.sketcher_summary(getattr(sketch, "Name", None)).get("constraints", [])
    constraint = next((item for item in constraints if item.get("index") == index), None)
    return {
        "ok": True,
        "sketch": getattr(sketch, "Name", None),
        "constraint_name": str(constraint_name),
        "constraint_index": index,
        "constraint": constraint,
        "solver_status": solver_status(service, sketch),
        "profile_validation": profile_validation(service, sketch),
    }
