# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher delete-geometry tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, resolve_geometry_index, run_freecad_transaction, validate_geometry_index


TOOL_SPEC = {
    "name": "sketcher.delete_geometry",
    "description": "Delete one Sketcher geometry element by index so the AI can correct a sketch and continue.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "geometry_index": {"type": "integer"},
            "geometry_handle": {"type": "string"},
        },
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    geometry_index: int | None = None,
    geometry_handle: str | None = None,
) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    try:
        index = resolve_geometry_index(service, sketch, geometry_index, geometry_handle)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "geometry_index": geometry_index, "geometry_handle": geometry_handle}
    invalid = validate_geometry_index(sketch, index)
    if invalid:
        return invalid

    def _delete() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_geometry = len(getattr(target, "Geometry", []))
        before_constraints = len(getattr(target, "Constraints", []))
        target.delGeometry(index)
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        return {
            "sketch": target.Name,
            "deleted_geometry_index": index,
            "deleted_geometry_handle": geometry_handle or f"geometry:{index}",
            "geometry_count_before": before_geometry,
            "constraint_count_before": before_constraints,
            "geometry_count": len(getattr(target, "Geometry", [])),
            "constraint_count": len(getattr(target, "Constraints", [])),
            "old_to_new_geometry_index": {
                str(old_index): old_index if old_index < index else old_index - 1
                for old_index in range(before_geometry)
                if old_index != index
            },
        }

    return active_response(service, sketch, run_freecad_transaction("Delete Sketcher geometry", _delete))
