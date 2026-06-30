# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher bulk delete-constraints tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, run_freecad_transaction


TOOL_SPEC = {
    "name": "sketcher.delete_all_constraints",
    "description": (
        "Delete all constraints in a Sketcher sketch, equivalent to using the "
        "Sketcher delete-all-constraints cleanup command before re-constraining."
    ),
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
        },
    },
}


def run(service: Any, sketch_name: str | None = None) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}

    def _delete_all() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_count = len(getattr(target, "Constraints", []))
        for index in reversed(range(before_count)):
            target.delConstraint(index)
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        return {
            "sketch": target.Name,
            "deleted_constraint_indices": list(range(before_count)),
            "constraint_count_before": before_count,
            "constraint_count": len(getattr(target, "Constraints", [])),
            "old_to_new_constraint_index": {},
        }

    return active_response(service, sketch, run_freecad_transaction("Delete all Sketcher constraints", _delete_all))
