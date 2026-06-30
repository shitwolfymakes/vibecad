# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher point tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, no_sketch, run_freecad_transaction


TOOL_SPEC = {
    "name": "sketcher.add_point",
    "description": "Add one native Sketcher point to an existing sketch, equivalent to using the point tool once.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "x": {"type": "number"},
            "y": {"type": "number"},
            "construction": {"type": "boolean"},
        },
        "required": ["x", "y"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    x: float = 0.0,
    y: float = 0.0,
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
            Part.Point(App.Vector(float(x), float(y), 0.0)),
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
            "point": [float(x), float(y)],
            "construction": bool(construction),
        }

    return active_response(service, sketch, run_freecad_transaction("Add Sketcher point", _add))
