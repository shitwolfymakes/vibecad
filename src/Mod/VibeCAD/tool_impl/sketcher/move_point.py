# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher point/geometry move tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, resolve_geometry_index, run_freecad_transaction, validate_geometry_index
from .constrain_common import point_position


TOOL_SPEC = {
    "name": "sketcher.move_point",
    "description": "Move one existing Sketcher geometry point role or whole geometry to an absolute or relative 2D location, equivalent to dragging geometry in Sketcher.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "geometry_index": {"type": "integer"},
            "geometry_handle": {"type": "string"},
            "point": {"type": "string", "enum": ["whole", "start", "end", "center", "midpoint"]},
            "x": {"type": "number"},
            "y": {"type": "number"},
            "relative": {"type": "boolean"},
        },
        "required": ["point", "x", "y"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    geometry_index: int | None = None,
    geometry_handle: str | None = None,
    point: str = "whole",
    x: float = 0.0,
    y: float = 0.0,
    relative: bool = False,
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

    def _move() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        pos = point_position(point)
        target.moveGeometry(index, pos, App.Vector(float(x), float(y), 0.0), int(bool(relative)))
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        geometry = service._geometry_summary(list(getattr(target, "Geometry", []))[index], index)
        return {
            "sketch": target.Name,
            "geometry_index": index,
            "geometry_handle": geometry_handle or f"geometry:{index}",
            "point": str(point),
            "point_position": pos,
            "x": float(x),
            "y": float(y),
            "relative": bool(relative),
            "geometry": geometry,
        }

    return active_response(service, sketch, run_freecad_transaction("Move Sketcher geometry point", _move))
