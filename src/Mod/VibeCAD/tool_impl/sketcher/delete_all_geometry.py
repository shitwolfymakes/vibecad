# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher bulk delete-geometry tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, run_freecad_transaction


TOOL_SPEC = {
    "name": "sketcher.delete_all_geometry",
    "description": (
        "Delete all editable geometry in a Sketcher sketch, equivalent to using "
        "the Sketcher delete-all-geometry cleanup command before rebuilding."
    ),
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "delete_constraints_first": {
                "type": "boolean",
                "description": (
                    "Also delete all constraints before geometry. Defaults to true "
                    "because FreeCAD geometry deletion can invalidate constraints."
                ),
            },
        },
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    delete_constraints_first: bool | None = True,
) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}

    def _delete_all() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_geometry = len(getattr(target, "Geometry", []))
        before_constraints = len(getattr(target, "Constraints", []))
        deleted_constraints: list[int] = []
        if delete_constraints_first:
            for index in reversed(range(before_constraints)):
                target.delConstraint(index)
                deleted_constraints.append(index)
        for index in reversed(range(before_geometry)):
            target.delGeometry(index)
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        return {
            "sketch": target.Name,
            "deleted_geometry_indices": list(range(before_geometry)),
            "deleted_constraint_indices": sorted(deleted_constraints),
            "geometry_count_before": before_geometry,
            "constraint_count_before": before_constraints,
            "geometry_count": len(getattr(target, "Geometry", [])),
            "constraint_count": len(getattr(target, "Constraints", [])),
            "old_to_new_geometry_index": {},
            "old_to_new_constraint_index": (
                {} if delete_constraints_first else {str(index): index for index in range(before_constraints)}
            ),
        }

    return active_response(service, sketch, run_freecad_transaction("Delete all Sketcher geometry", _delete_all))
