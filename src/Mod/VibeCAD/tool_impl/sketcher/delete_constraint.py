# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher delete-constraint tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, resolve_constraint_index, run_freecad_transaction, validate_constraint_index


TOOL_SPEC = {
    "name": "sketcher.delete_constraint",
    "description": "Delete one Sketcher constraint by index so the AI can correct overconstraints or bad dimensions and continue.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "constraint_index": {"type": "integer"},
            "constraint_name": {"type": "string"},
            "constraint_handle": {"type": "string"},
        },
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    constraint_index: int | None = None,
    constraint_name: str | None = None,
    constraint_handle: str | None = None,
) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    try:
        index = resolve_constraint_index(sketch, constraint_index, constraint_name, constraint_handle)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "constraint_index": constraint_index, "constraint_name": constraint_name, "constraint_handle": constraint_handle}
    invalid = validate_constraint_index(sketch, index)
    if invalid:
        return invalid

    def _delete() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_count = len(getattr(target, "Constraints", []))
        target.delConstraint(index)
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        return {
            "sketch": target.Name,
            "deleted_constraint_index": index,
            "deleted_constraint_handle": constraint_handle or f"constraint:{index}",
            "deleted_constraint_name": constraint_name,
            "constraint_count_before": before_count,
            "constraint_count": len(getattr(target, "Constraints", [])),
            "old_to_new_constraint_index": {
                str(old_index): old_index if old_index < index else old_index - 1
                for old_index in range(before_count)
                if old_index != index
            },
        }

    return active_response(service, sketch, run_freecad_transaction("Delete Sketcher constraint", _delete))
