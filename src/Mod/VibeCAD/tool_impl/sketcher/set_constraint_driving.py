# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher driving/reference constraint toggle tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, resolve_constraint_index, run_freecad_transaction, validate_constraint_index


TOOL_SPEC = {
    "name": "sketcher.set_constraint_driving",
    "description": (
        "Set a Sketcher constraint to driving or reference using FreeCAD's native "
        "setDriving API, equivalent to the Sketcher dimensional constraint driving toggle."
    ),
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "constraint_index": {"type": "integer"},
            "constraint_name": {"type": "string"},
            "constraint_handle": {"type": "string"},
            "driving": {"type": "boolean"},
        },
        "required": ["driving"],
    },
}


def run(
    service: Any,
    driving: bool,
    constraint_index: int | None = None,
    constraint_name: str | None = None,
    constraint_handle: str | None = None,
    sketch_name: str | None = None,
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

    def _set_driving() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_constraint = list(getattr(target, "Constraints", []))[index]
        before = bool(getattr(before_constraint, "Driving", getattr(before_constraint, "isDriving", True)))
        target.setDriving(index, bool(driving))
        if App.ActiveDocument is not None:
            App.ActiveDocument.recompute()
        after_constraint = list(getattr(target, "Constraints", []))[index]
        after = bool(getattr(after_constraint, "Driving", getattr(after_constraint, "isDriving", True)))
        return {
            "sketch": target.Name,
            "constraint_index": index,
            "constraint_handle": constraint_handle or f"constraint:{index}",
            "constraint_name": constraint_name,
            "before_driving": before,
            "driving": after,
        }

    return active_response(
        service,
        sketch,
        run_freecad_transaction(f"Set Sketcher constraint {index} driving state", _set_driving),
    )
