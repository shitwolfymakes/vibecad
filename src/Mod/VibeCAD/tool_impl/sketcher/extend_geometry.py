# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher extend tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, resolve_geometry_index, run_freecad_transaction, validate_geometry_index
from .constrain_common import point_position


TOOL_SPEC = {
    "name": "sketcher.extend_geometry",
    "description": "Extend one native Sketcher line or arc endpoint by a signed increment, equivalent to using the Sketcher extend tool.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "geometry_index": {"type": "integer"},
            "geometry_handle": {"type": "string"},
            "endpoint": {"type": "string", "enum": ["start", "end"]},
            "increment": {"type": "number"},
        },
        "required": ["endpoint", "increment"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    geometry_index: int | None = None,
    geometry_handle: str | None = None,
    endpoint: str = "end",
    increment: float = 1.0,
) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    try:
        index = resolve_geometry_index(service, sketch, geometry_index, geometry_handle)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "geometry_index": geometry_index, "geometry_handle": geometry_handle}
    invalid = validate_geometry_index(sketch, index)
    if invalid:
        return invalid
    clean_endpoint = str(endpoint or "").strip().lower()
    if clean_endpoint not in {"start", "end"}:
        return {"ok": False, "error": "endpoint must be start or end."}

    def _extend() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_geometry = len(getattr(target, "Geometry", []))
        before_constraints = len(getattr(target, "Constraints", []))
        target.extend(index, float(increment), point_position(clean_endpoint))
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        after_geometry = len(getattr(target, "Geometry", []))
        after_constraints = len(getattr(target, "Constraints", []))
        return {
            "sketch": target.Name,
            "geometry_index": index,
            "geometry_handle": geometry_handle or f"geometry:{index}",
            "endpoint": clean_endpoint,
            "increment": float(increment),
            "geometry_count_before": before_geometry,
            "geometry_count": after_geometry,
            "constraint_count_before": before_constraints,
            "constraint_count": after_constraints,
        }

    return active_response(service, sketch, run_freecad_transaction("Extend Sketcher geometry", _extend))
