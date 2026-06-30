# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher fillet/chamfer corner tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, resolve_geometry_index, run_freecad_transaction, validate_geometry_index
from .constrain_common import point_position


TOOL_SPEC = {
    "name": "sketcher.fillet_corner",
    "description": "Create a native Sketcher fillet or chamfer between two curves or at a coincident endpoint, equivalent to the Sketcher fillet/chamfer tool.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "first_geometry": {"type": "integer"},
            "first_geometry_handle": {"type": "string"},
            "first_point": {"type": "string", "enum": ["start", "end"]},
            "second_geometry": {"type": "integer"},
            "second_geometry_handle": {"type": "string"},
            "first_reference_x": {"type": "number"},
            "first_reference_y": {"type": "number"},
            "second_reference_x": {"type": "number"},
            "second_reference_y": {"type": "number"},
            "radius": {"type": "number"},
            "trim": {"type": "boolean"},
            "preserve_corner": {"type": "boolean"},
            "chamfer": {"type": "boolean"},
        },
        "required": ["radius"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    first_geometry: int | None = None,
    first_geometry_handle: str | None = None,
    first_point: str = "end",
    second_geometry: int | None = None,
    second_geometry_handle: str | None = None,
    first_reference_x: float | None = None,
    first_reference_y: float | None = None,
    second_reference_x: float | None = None,
    second_reference_y: float | None = None,
    radius: float = 1.0,
    trim: bool = True,
    preserve_corner: bool = True,
    chamfer: bool = False,
) -> dict[str, Any]:
    if float(radius) <= 0:
        return {"ok": False, "error": "radius must be positive."}
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    try:
        first_index = resolve_geometry_index(service, sketch, first_geometry, first_geometry_handle)
        second_index = (
            resolve_geometry_index(service, sketch, second_geometry, second_geometry_handle)
            if second_geometry is not None or second_geometry_handle
            else None
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    invalid = validate_geometry_index(sketch, first_index)
    if invalid:
        return invalid
    if second_index is not None:
        invalid = validate_geometry_index(sketch, second_index)
        if invalid:
            return invalid

    def _fillet() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_geometry = len(getattr(target, "Geometry", []))
        before_constraints = len(getattr(target, "Constraints", []))
        if second_index is None:
            target.fillet(
                first_index,
                point_position(first_point),
                float(radius),
                int(bool(trim)),
                bool(preserve_corner),
                bool(chamfer),
            )
            reference_mode = "coincident_point"
        else:
            if None in (first_reference_x, first_reference_y, second_reference_x, second_reference_y):
                raise ValueError(
                    "first_reference_x/y and second_reference_x/y are required when second_geometry is provided."
                )
            target.fillet(
                first_index,
                second_index,
                App.Vector(float(first_reference_x), float(first_reference_y), 0.0),
                App.Vector(float(second_reference_x), float(second_reference_y), 0.0),
                float(radius),
                int(bool(trim)),
                bool(preserve_corner),
                bool(chamfer),
            )
            reference_mode = "two_curve_references"
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        after_geometry = len(getattr(target, "Geometry", []))
        after_constraints = len(getattr(target, "Constraints", []))
        return {
            "sketch": target.Name,
            "geometry_index": before_geometry,
            "geometry_added": max(0, after_geometry - before_geometry),
            "constraint_index": before_constraints,
            "constraints_added": max(0, after_constraints - before_constraints),
            "first_geometry": first_index,
            "first_geometry_handle": first_geometry_handle or f"geometry:{first_index}",
            "second_geometry": second_index,
            "second_geometry_handle": second_geometry_handle or (f"geometry:{second_index}" if second_index is not None else None),
            "reference_mode": reference_mode,
            "radius": float(radius),
            "trim": bool(trim),
            "preserve_corner": bool(preserve_corner),
            "chamfer": bool(chamfer),
            "geometry_count_before": before_geometry,
            "geometry_count": after_geometry,
            "constraint_count_before": before_constraints,
            "constraint_count": after_constraints,
        }

    return active_response(service, sketch, run_freecad_transaction("Create Sketcher fillet/chamfer", _fillet))
