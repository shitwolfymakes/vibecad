# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher constraint rename tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, run_freecad_transaction, validate_constraint_index


TOOL_SPEC = {
    "name": "sketcher.set_constraint_name",
    "description": (
        "Name or rename an existing Sketcher constraint using FreeCAD's native "
        "renameConstraint API, matching the Sketcher constraints panel behavior."
    ),
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "constraint_index": {"type": "integer"},
            "constraint_name": {"type": "string"},
        },
        "required": ["constraint_index", "constraint_name"],
    },
}


def run(
    service: Any,
    constraint_index: int,
    constraint_name: str,
    sketch_name: str | None = None,
) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    index = int(constraint_index)
    invalid = validate_constraint_index(sketch, index)
    if invalid:
        return invalid

    def _rename() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before = getattr(list(getattr(target, "Constraints", []))[index], "Name", "")
        target.renameConstraint(index, str(constraint_name))
        if App.ActiveDocument is not None:
            App.ActiveDocument.recompute()
        after = getattr(list(getattr(target, "Constraints", []))[index], "Name", "")
        return {
            "sketch": target.Name,
            "constraint_index": index,
            "old_constraint_name": before,
            "constraint_name": after,
        }

    return active_response(
        service,
        sketch,
        run_freecad_transaction(f"Rename Sketcher constraint {index}: {getattr(sketch, 'Label', sketch.Name)}", _rename),
    )
