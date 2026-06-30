# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher ellipse tool."""

from __future__ import annotations

import math
from typing import Any

from .common import active_response, get_sketch, no_sketch, run_freecad_transaction


TOOL_SPEC = {
    "name": "sketcher.add_ellipse",
    "description": "Add one native Sketcher ellipse to an existing sketch using center, major/minor radii, and rotation angle.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "center_x": {"type": "number"},
            "center_y": {"type": "number"},
            "major_radius": {"type": "number"},
            "minor_radius": {"type": "number"},
            "angle_degrees": {"type": "number"},
            "construction": {"type": "boolean"},
        },
        "required": ["center_x", "center_y", "major_radius", "minor_radius"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    center_x: float = 0.0,
    center_y: float = 0.0,
    major_radius: float = 10.0,
    minor_radius: float = 5.0,
    angle_degrees: float = 0.0,
    construction: bool = False,
) -> dict[str, Any]:
    if float(major_radius) <= 0 or float(minor_radius) <= 0:
        return {"ok": False, "error": "Ellipse radii must be positive."}
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
        ellipse = Part.Ellipse(
            App.Vector(float(center_x), float(center_y), 0.0),
            float(major_radius),
            float(minor_radius),
        )
        angle = math.radians(float(angle_degrees))
        ellipse.XAxis = App.Vector(math.cos(angle), math.sin(angle), 0.0)
        geometry_index = target.addGeometry(ellipse, bool(construction))
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
            "major_radius": float(major_radius),
            "minor_radius": float(minor_radius),
            "angle_degrees": float(angle_degrees),
            "construction": bool(construction),
        }

    return active_response(service, sketch, run_freecad_transaction("Add Sketcher ellipse", _add))
