# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher offset-geometry tool."""

from __future__ import annotations

import math
from typing import Any

from .common import (
    active_response,
    get_sketch,
    resolve_geometry_index,
    run_freecad_transaction,
    validate_geometry_index,
)


TOOL_SPEC = {
    "name": "sketcher.offset_geometry",
    "description": (
        "Create offset copies of selected native Sketcher line, circle, or circular "
        "arc geometry. The AI chooses the source geometry and offset distance; the "
        "tool executes the native geometric offset and returns exact created "
        "geometry summaries."
    ),
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "geometry_indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Line, circle, or arc geometry indices to offset.",
            },
            "geometry_handles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Semantic geometry handles to offset.",
            },
            "distance": {"type": "number", "description": "Signed offset distance in sketch units."},
            "side": {
                "type": "string",
                "enum": ["left", "right", "outward", "inward"],
                "description": (
                    "Direction semantics. Lines use left/right relative to start-to-end. "
                    "Circles and arcs use outward/inward radius change."
                ),
            },
            "construction": {
                "type": "boolean",
                "description": "Optional construction flag for created offset geometry.",
            },
        },
        "required": ["distance"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    geometry_indices: list[int] | None = None,
    geometry_handles: list[str] | None = None,
    distance: float = 1.0,
    side: str = "left",
    construction: bool | None = None,
) -> dict[str, Any]:
    if abs(float(distance)) < 1e-12:
        return {"ok": False, "error": "Offset distance must be non-zero."}
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    try:
        indices = _resolve_indices(service, sketch, geometry_indices, geometry_handles)
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "geometry_indices": geometry_indices,
            "geometry_handles": geometry_handles,
        }
    if not indices:
        return {"ok": False, "error": "At least one geometry index or handle is required."}
    for index in indices:
        invalid = validate_geometry_index(sketch, index)
        if invalid:
            return invalid

    def _offset() -> dict[str, Any]:
        import FreeCAD as App
        import Part

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_count = len(getattr(target, "Geometry", []))
        created: list[int] = []
        source_geometry = list(getattr(target, "Geometry", []))
        normalized_side = str(side or "left").strip().lower()
        for index in indices:
            source = source_geometry[index]
            offset = _offset_one(App, Part, source, float(distance), normalized_side)
            if offset is None:
                raise RuntimeError(
                    "Offset currently supports LineSegment, Circle, and ArcOfCircle geometry; "
                    f"geometry {index} is {type(source).__name__}."
                )
            created.append(int(target.addGeometry(offset, bool(target.getConstruction(index)) if construction is None else bool(construction))))
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        all_geometry = list(getattr(target, "Geometry", []))
        geometry = [service._geometry_summary(all_geometry[index], index) for index in created]
        return {
            "sketch": target.Name,
            "source_geometry_indices": indices,
            "source_geometry_handles": geometry_handles or [f"geometry:{index}" for index in indices],
            "created_geometry_indices": created,
            "geometry_index": created[0] if created else None,
            "geometry_added": len(created),
            "geometry_count_before": before_count,
            "geometry_count": len(all_geometry),
            "distance": float(distance),
            "side": normalized_side,
            "construction": construction,
            "geometry": geometry,
            "old_to_new_geometry_index": {
                str(index): index
                for index in range(len(all_geometry))
            },
        }

    return active_response(service, sketch, run_freecad_transaction("Offset Sketcher geometry", _offset))


def _offset_one(App: Any, Part: Any, source: Any, distance: float, side: str) -> Any:
    name = type(source).__name__
    if name == "LineSegment":
        start = source.StartPoint
        end = source.EndPoint
        dx = float(end.x) - float(start.x)
        dy = float(end.y) - float(start.y)
        length = math.hypot(dx, dy)
        if length <= 1e-12:
            raise RuntimeError("Cannot offset a zero-length line segment.")
        sign = -1.0 if side == "right" else 1.0
        vector = App.Vector(-dy / length * distance * sign, dx / length * distance * sign, 0.0)
        return Part.LineSegment(start + vector, end + vector)
    if name == "Circle":
        radius = _offset_radius(float(source.Radius), distance, side)
        return Part.Circle(source.Center, source.Axis, radius)
    if name == "ArcOfCircle":
        radius = _offset_radius(float(source.Radius), distance, side)
        circle = Part.Circle(source.Center, source.Axis, radius)
        return Part.ArcOfCircle(circle, float(source.FirstParameter), float(source.LastParameter))
    return None


def _offset_radius(radius: float, distance: float, side: str) -> float:
    if side == "inward":
        result = radius - abs(distance)
    elif side == "outward":
        result = radius + abs(distance)
    else:
        result = radius + distance
    if result <= 1e-12:
        raise RuntimeError("Offset radius must remain positive.")
    return result


def _resolve_indices(
    service: Any,
    sketch: Any,
    geometry_indices: list[int] | None,
    geometry_handles: list[str] | None,
) -> list[int]:
    resolved: list[int] = []
    for raw_index in geometry_indices or []:
        index = int(raw_index)
        if index not in resolved:
            resolved.append(index)
    for handle in geometry_handles or []:
        index = resolve_geometry_index(service, sketch, None, handle)
        if index not in resolved:
            resolved.append(index)
    return resolved
