# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher mirror-geometry tool."""

from __future__ import annotations

from typing import Any

from .common import (
    active_response,
    get_sketch,
    resolve_geometry_index,
    run_freecad_transaction,
    validate_geometry_index,
)


TOOL_SPEC = {
    "name": "sketcher.mirror_geometry",
    "description": (
        "Create mirrored copies of selected native Sketcher geometry across an "
        "explicit 2D mirror axis. This is the model-facing equivalent of using "
        "Sketcher's symmetry/mirror workflow on selected geometry."
    ),
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "geometry_indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Geometry indices to mirror.",
            },
            "geometry_handles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Semantic geometry handles to mirror.",
            },
            "axis_point_x": {"type": "number", "description": "X coordinate of a point on the mirror axis."},
            "axis_point_y": {"type": "number", "description": "Y coordinate of a point on the mirror axis."},
            "axis_direction_x": {"type": "number", "description": "X component of the mirror-axis direction vector."},
            "axis_direction_y": {"type": "number", "description": "Y component of the mirror-axis direction vector."},
            "keep_original": {
                "type": "boolean",
                "description": "When true, preserve selected geometry and add mirrored copies. Defaults to true.",
            },
        },
        "required": ["axis_point_x", "axis_point_y", "axis_direction_x", "axis_direction_y"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    geometry_indices: list[int] | None = None,
    geometry_handles: list[str] | None = None,
    axis_point_x: float = 0.0,
    axis_point_y: float = 0.0,
    axis_direction_x: float = 1.0,
    axis_direction_y: float = 0.0,
    keep_original: bool = True,
) -> dict[str, Any]:
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
    if abs(float(axis_direction_x)) < 1e-12 and abs(float(axis_direction_y)) < 1e-12:
        return {"ok": False, "error": "Mirror axis direction vector must be non-zero."}
    for index in indices:
        invalid = validate_geometry_index(sketch, index)
        if invalid:
            return invalid

    def _mirror() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_count = len(getattr(target, "Geometry", []))
        created: list[int] = []
        modified: list[int] = []
        source_geometry = list(getattr(target, "Geometry", []))
        axis_point = App.Vector(float(axis_point_x), float(axis_point_y), 0.0)
        axis_direction = App.Vector(float(axis_direction_x), float(axis_direction_y), 0.0)
        for index in indices:
            mirrored = source_geometry[index].copy()
            mirrored.mirror(axis_point, axis_direction)
            if keep_original:
                construction = bool(target.getConstruction(index))
                created.append(int(target.addGeometry(mirrored, construction)))
            else:
                target.setGeometry(index, mirrored)
                modified.append(index)
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        all_geometry = list(getattr(target, "Geometry", []))
        affected = created if keep_original else modified
        geometry = [service._geometry_summary(all_geometry[index], index) for index in affected]
        return {
            "sketch": target.Name,
            "source_geometry_indices": indices,
            "source_geometry_handles": geometry_handles or [f"geometry:{index}" for index in indices],
            "created_geometry_indices": created,
            "modified_geometry_indices": modified,
            "geometry_index": created[0] if created else None,
            "geometry_added": len(created),
            "geometry_count_before": before_count,
            "geometry_count": len(all_geometry),
            "mirror_axis": {
                "point": [float(axis_point_x), float(axis_point_y)],
                "direction": [float(axis_direction_x), float(axis_direction_y)],
            },
            "keep_original": bool(keep_original),
            "geometry": geometry,
            "old_to_new_geometry_index": {
                str(index): index
                for index in range(len(all_geometry))
            },
        }

    return active_response(service, sketch, run_freecad_transaction("Mirror Sketcher geometry", _mirror))


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
