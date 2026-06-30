# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher circle tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, no_sketch, run_freecad_transaction


TOOL_SPEC = {
    "name": "sketcher.add_circle",
    "description": "Add one native Sketcher circle to an existing sketch, equivalent to using the circle tool once.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "center_x": {"type": "number"},
            "center_y": {"type": "number"},
            "radius": {"type": "number"},
            "construction": {"type": "boolean"},
        },
        "required": ["center_x", "center_y", "radius"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    center_x: float = 0.0,
    center_y: float = 0.0,
    radius: float = 5.0,
    construction: bool = False,
) -> dict[str, Any]:
    if float(radius) <= 0:
        return {"ok": False, "error": "Circle radius must be positive."}
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
        geometry_index = target.addGeometry(
            Part.Circle(
                App.Vector(float(center_x), float(center_y), 0.0),
                App.Vector(0.0, 0.0, 1.0),
                float(radius),
            ),
            bool(construction),
        )
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        return {
            "sketch": target.Name,
            "geometry_index": int(geometry_index),
            "created_geometry_indices": [int(geometry_index)],
            "geometry_added": 1,
            "geometry_count_before": before_count,
            "geometry_count": len(getattr(target, "Geometry", [])),
            "center": [float(center_x), float(center_y)],
            "radius": float(radius),
            "construction": bool(construction),
            "suggested_next_actions": [
                {
                    "tool": "sketcher.constrain_radius",
                    "arguments": {
                        "sketch_name": target.Name,
                        "geometry_index": int(geometry_index),
                        "value": float(radius),
                    },
                    "why": "Make the circle size a native editable radius constraint.",
                },
                {
                    "tool": "sketcher.constrain_lock_point",
                    "arguments": {
                        "sketch_name": target.Name,
                        "geometry": int(geometry_index),
                        "point": "center",
                        "x": float(center_x),
                        "y": float(center_y),
                    },
                    "why": "Lock the circle center to exact sketch coordinates when the feature position is known.",
                },
            ],
        }

    return active_response(service, sketch, run_freecad_transaction("Add Sketcher circle", _add))
