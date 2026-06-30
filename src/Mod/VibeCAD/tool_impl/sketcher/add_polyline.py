# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher polyline tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, no_sketch, run_freecad_transaction, vector2


TOOL_SPEC = {
    "name": "sketcher.add_polyline",
    "description": "Add a native Sketcher polyline as deliberate connected line strokes. Explicit point coordinates are converted into native Sketcher dimensional constraints by default so profile sketches remain editable and solver-defined.",
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
            "closed": {"type": "boolean"},
            "construction": {"type": "boolean"},
            "constrain_points": {
                "type": "boolean",
                "description": "When true, add native DistanceX/DistanceY constraints for each supplied point coordinate.",
            },
        },
        "required": ["points"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    points: list[list[float]] | None = None,
    closed: bool = False,
    construction: bool = False,
    constrain_points: bool = True,
) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return no_sketch(sketch_name)
    point_values = points or []
    if len(point_values) < 2:
        return {"ok": False, "error": "Polyline requires at least two points."}

    def _add() -> dict[str, Any]:
        import FreeCAD as App
        import Part
        import Sketcher

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_geometry = len(getattr(target, "Geometry", []))
        before_constraints = len(getattr(target, "Constraints", []))
        vectors = [vector2(raw, index, "Polyline") for index, raw in enumerate(point_values)]
        segments = [
            Part.LineSegment(vectors[index], vectors[index + 1])
            for index in range(len(vectors) - 1)
        ]
        if bool(closed):
            segments.append(Part.LineSegment(vectors[-1], vectors[0]))
        target.addGeometry(segments, bool(construction))
        constraints = [
            Sketcher.Constraint("Coincident", before_geometry + index, 2, before_geometry + index + 1, 1)
            for index in range(len(segments) - 1)
        ]
        if bool(closed) and len(segments) > 1:
            constraints.append(
                Sketcher.Constraint("Coincident", before_geometry + len(segments) - 1, 2, before_geometry, 1)
            )
        dimensional_constraints = []
        point_constraint_targets = []
        if bool(constrain_points):
            for point_index, vector in enumerate(vectors):
                if point_index < len(vectors) - 1:
                    geometry_index = before_geometry + point_index
                    point_pos = 1
                else:
                    geometry_index = before_geometry + point_index - 1
                    point_pos = 2
                dimensional_constraints.extend(
                    [
                        Sketcher.Constraint("DistanceX", geometry_index, point_pos, float(vector.x)),
                        Sketcher.Constraint("DistanceY", geometry_index, point_pos, float(vector.y)),
                    ]
                )
                point_constraint_targets.append(
                    {
                        "point_index": point_index,
                        "geometry_index": geometry_index,
                        "point_position": point_pos,
                        "x": float(vector.x),
                        "y": float(vector.y),
                    }
                )
        constraints.extend(dimensional_constraints)
        if constraints:
            target.addConstraint(constraints)
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        return {
            "sketch": target.Name,
            "geometry_index": before_geometry,
            "geometry_added": len(segments),
            "constraints_added": len(constraints),
            "coincident_constraints_added": len(constraints) - len(dimensional_constraints),
            "point_dimension_constraints_added": len(dimensional_constraints),
            "geometry_count_before": before_geometry,
            "constraint_count_before": before_constraints,
            "geometry_count": len(getattr(target, "Geometry", [])),
            "constraint_count": len(getattr(target, "Constraints", [])),
            "closed": bool(closed),
            "construction": bool(construction),
            "constrain_points": bool(constrain_points),
            "point_constraint_targets": point_constraint_targets,
            "suggested_next_actions": [
                {
                    "tool": "partdesign.revolve_sketch",
                    "arguments": {"sketch_name": target.Name},
                    "why": "Use this closed constrained profile for a native PartDesign revolve when it represents a section about an axis.",
                },
                {
                    "tool": "partdesign.pad_sketch",
                    "arguments": {"sketch_name": target.Name},
                    "why": "Use this closed constrained profile for a native PartDesign pad when it represents an extruded section.",
                },
                {
                    "tool": "partdesign.pocket_sketch",
                    "arguments": {"sketch_name": target.Name},
                    "why": "Use this closed constrained profile for a native PartDesign pocket when it is mapped to an existing solid face.",
                },
            ] if bool(closed) else [],
        }

    return active_response(service, sketch, run_freecad_transaction("Add Sketcher polyline", _add))
