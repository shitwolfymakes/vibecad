# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher line tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, no_sketch, run_freecad_transaction


TOOL_SPEC = {
    "name": "sketcher.add_line",
    "description": "Add one native Sketcher line segment to an existing sketch, equivalent to using the line tool for one deliberate stroke.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "start_x": {"type": "number"},
            "start_y": {"type": "number"},
            "end_x": {"type": "number"},
            "end_y": {"type": "number"},
            "construction": {"type": "boolean"},
        },
        "required": ["start_x", "start_y", "end_x", "end_y"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    start_x: float = 0.0,
    start_y: float = 0.0,
    end_x: float = 10.0,
    end_y: float = 0.0,
    construction: bool = False,
) -> dict[str, Any]:
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
            Part.LineSegment(
                App.Vector(float(start_x), float(start_y), 0.0),
                App.Vector(float(end_x), float(end_y), 0.0),
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
            "start": [float(start_x), float(start_y)],
            "end": [float(end_x), float(end_y)],
            "construction": bool(construction),
        }

    return active_response(service, sketch, run_freecad_transaction("Add Sketcher line", _add))
