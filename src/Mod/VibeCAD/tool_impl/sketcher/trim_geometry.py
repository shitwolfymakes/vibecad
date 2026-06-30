# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher trim tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, resolve_geometry_index, run_freecad_transaction, validate_geometry_index


TOOL_SPEC = {
    "name": "sketcher.trim_geometry",
    "description": "Trim one native Sketcher curve at the picked sketch-space point, equivalent to using the Sketcher trim tool on a selected edge.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "geometry_index": {"type": "integer"},
            "geometry_handle": {"type": "string"},
            "x": {"type": "number"},
            "y": {"type": "number"},
        },
        "required": ["x", "y"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    geometry_index: int | None = None,
    geometry_handle: str | None = None,
    x: float = 0.0,
    y: float = 0.0,
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

    def _trim() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_geometry = len(getattr(target, "Geometry", []))
        before_constraints = len(getattr(target, "Constraints", []))
        target.trim(index, App.Vector(float(x), float(y), 0.0))
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        after_geometry = len(getattr(target, "Geometry", []))
        after_constraints = len(getattr(target, "Constraints", []))
        return {
            "sketch": target.Name,
            "geometry_index": index,
            "geometry_handle": geometry_handle or f"geometry:{index}",
            "picked_point": [float(x), float(y)],
            "geometry_count_before": before_geometry,
            "geometry_count": after_geometry,
            "constraint_count_before": before_constraints,
            "constraint_count": after_constraints,
            "geometry_added": max(0, after_geometry - before_geometry),
            "constraints_added": max(0, after_constraints - before_constraints),
        }

    return active_response(service, sketch, run_freecad_transaction("Trim Sketcher geometry", _trim))
