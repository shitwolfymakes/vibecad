# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher bulk transform tool."""

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
    "name": "sketcher.transform_geometry",
    "description": (
        "Translate multiple Sketcher geometry elements by a 2D delta, equivalent "
        "to using Sketcher's move/translate workflow on selected geometry."
    ),
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "geometry_indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Geometry indices to translate.",
            },
            "geometry_handles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Semantic geometry handles to translate.",
            },
            "dx": {"type": "number"},
            "dy": {"type": "number"},
        },
        "required": ["dx", "dy"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    geometry_indices: list[int] | None = None,
    geometry_handles: list[str] | None = None,
    dx: float = 0.0,
    dy: float = 0.0,
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
    for index in indices:
        invalid = validate_geometry_index(sketch, index)
        if invalid:
            return invalid

    def _transform() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        for index in indices:
            target.moveGeometry(index, 0, App.Vector(float(dx), float(dy), 0.0), 1)
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        geometry = [
            service._geometry_summary(list(getattr(target, "Geometry", []))[index], index)
            for index in indices
        ]
        return {
            "sketch": target.Name,
            "modified_geometry_indices": indices,
            "geometry_indices": indices,
            "geometry_handles": geometry_handles or [f"geometry:{index}" for index in indices],
            "dx": float(dx),
            "dy": float(dy),
            "geometry": geometry,
            "old_to_new_geometry_index": {str(index): index for index in range(len(getattr(target, "Geometry", [])))},
        }

    return active_response(service, sketch, run_freecad_transaction("Transform Sketcher geometry", _transform))


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
