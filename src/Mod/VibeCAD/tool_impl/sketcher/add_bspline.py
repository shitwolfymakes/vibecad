# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher B-spline tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, no_sketch, run_freecad_transaction, vector2


TOOL_SPEC = {
    "name": "sketcher.add_bspline",
    "description": "Add one native Sketcher B-spline from explicit control/interpolation points.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "points": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "minItems": 2,
            },
            "interpolate": {"type": "boolean"},
            "periodic": {"type": "boolean"},
            "construction": {"type": "boolean"},
        },
        "required": ["points"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    points: list[list[float]] | None = None,
    interpolate: bool = True,
    periodic: bool = False,
    construction: bool = False,
) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return no_sketch(sketch_name)
    point_values = points or []
    if len(point_values) < 2:
        return {"ok": False, "error": "B-spline requires at least two points."}

    def _add() -> dict[str, Any]:
        import FreeCAD as App
        import Part

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_count = len(getattr(target, "Geometry", []))
        vectors = [vector2(raw, index, "B-spline") for index, raw in enumerate(point_values)]
        curve = Part.BSplineCurve()
        if bool(interpolate):
            curve.interpolate(vectors, PeriodicFlag=bool(periodic))
        else:
            curve.buildFromPoles(vectors, bool(periodic))
        geometry_index = target.addGeometry(curve, bool(construction))
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        return {
            "sketch": target.Name,
            "geometry_index": int(geometry_index),
            "geometry_added": 1,
            "geometry_count_before": before_count,
            "geometry_count": len(getattr(target, "Geometry", [])),
            "point_count": len(vectors),
            "interpolate": bool(interpolate),
            "periodic": bool(periodic),
            "construction": bool(construction),
        }

    return active_response(service, sketch, run_freecad_transaction("Add Sketcher B-spline", _add))
