# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher arc-of-circle tool."""

from __future__ import annotations

import math
from typing import Any

from .common import active_response, get_sketch, no_sketch, run_freecad_transaction


TOOL_SPEC = {
    "name": "sketcher.add_arc",
    "description": "Add one native Sketcher arc of circle to an existing sketch using center, radius, and start/end angles in degrees.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "center_x": {"type": "number"},
            "center_y": {"type": "number"},
            "radius": {"type": "number"},
            "start_angle_degrees": {"type": "number"},
            "end_angle_degrees": {"type": "number"},
            "construction": {"type": "boolean"},
        },
        "required": ["center_x", "center_y", "radius", "start_angle_degrees", "end_angle_degrees"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    center_x: float = 0.0,
    center_y: float = 0.0,
    radius: float = 5.0,
    start_angle_degrees: float = 0.0,
    end_angle_degrees: float = 90.0,
    construction: bool = False,
) -> dict[str, Any]:
    if float(radius) <= 0:
        return {"ok": False, "error": "Arc radius must be positive."}
    if abs(float(end_angle_degrees) - float(start_angle_degrees)) < 1e-9:
        return {"ok": False, "error": "Arc start and end angles must differ."}
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return no_sketch(sketch_name)

    def _add() -> dict[str, Any]:
        import FreeCAD as App
        import Part

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_count = len(getattr(target, "Geometry", []))
        circle = Part.Circle(
            App.Vector(float(center_x), float(center_y), 0.0),
            App.Vector(0.0, 0.0, 1.0),
            float(radius),
        )
        geometry_index = target.addGeometry(
            Part.ArcOfCircle(
                circle,
                math.radians(float(start_angle_degrees)),
                math.radians(float(end_angle_degrees)),
            ),
            bool(construction),
        )
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        return {
            "sketch": target.Name,
            "geometry_index": int(geometry_index),
            "geometry_added": 1,
            "geometry_count_before": before_count,
            "geometry_count": len(getattr(target, "Geometry", [])),
            "center": [float(center_x), float(center_y)],
            "radius": float(radius),
            "start_angle_degrees": float(start_angle_degrees),
            "end_angle_degrees": float(end_angle_degrees),
            "construction": bool(construction),
        }

    return active_response(service, sketch, run_freecad_transaction("Add Sketcher arc", _add))
