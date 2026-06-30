# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher geometry inventory tool."""

from __future__ import annotations

from typing import Any

from .common import geometry_inventory, get_sketch, profile_validation, resolve_geometry_names, solver_status


TOOL_SPEC = {
    "name": "sketcher.list_geometry",
    "description": (
        "List Sketcher geometry with indices, stable geometry handles, optional semantic names, "
        "fingerprints, point roles, construction state, solver status, and profile validation."
    ),
    "contextual": True,
    "safety": "READ",
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
        },
    },
}


def run(service: Any, sketch_name: str | None = None) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    geometry = geometry_inventory(service, sketch)
    return {
        "ok": True,
        "sketch": getattr(sketch, "Name", None),
        "sketch_label": getattr(sketch, "Label", getattr(sketch, "Name", None)),
        "geometry_count": len(geometry),
        "geometry": geometry,
        "named_geometry": resolve_geometry_names(service, sketch, include_missing=True),
        "solver_status": solver_status(service, sketch),
        "profile_validation": profile_validation(service, sketch),
    }
