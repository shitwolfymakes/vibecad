# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher datum edit tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, run_freecad_transaction, validate_constraint_index


TOOL_SPEC = {
    "name": "sketcher.set_constraint_value",
    "description": "Edit an existing Sketcher dimension constraint value by index, equivalent to changing a datum in the Sketcher constraints panel.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "constraint_index": {"type": "integer"},
            "value": {"type": "number"},
        },
        "required": ["constraint_index", "value"],
    },
}


DIMENSION_CONSTRAINTS = {"Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"}


def run(
    service: Any,
    sketch_name: str | None = None,
    constraint_index: int = 0,
    value: float = 10.0,
) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    invalid = validate_constraint_index(sketch, int(constraint_index))
    if invalid:
        return invalid
    index = int(constraint_index)
    constraint = list(getattr(sketch, "Constraints", []))[index]
    constraint_type = str(getattr(constraint, "Type", ""))
    if constraint_type not in DIMENSION_CONSTRAINTS:
        return {
            "ok": False,
            "error": f"Constraint is not a dimension datum: {constraint_type}",
            "constraint_index": index,
            "constraint_type": constraint_type,
        }
    if float(value) <= 0 and constraint_type != "Angle":
        return {"ok": False, "error": "Sketch dimension values must be positive."}

    def _set() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_constraint = list(getattr(target, "Constraints", []))[index]
        before = float(getattr(before_constraint, "Value", 0.0))
        quantity = App.Units.Quantity(float(value), App.Units.Length)
        if constraint_type == "Angle":
            quantity = App.Units.Quantity(float(value), App.Units.Angle)
        target.setDatum(index, quantity)
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        after_constraint = list(getattr(target, "Constraints", []))[index]
        after = float(getattr(after_constraint, "Value", 0.0))
        return {
            "sketch": target.Name,
            "sketch_label": getattr(target, "Label", target.Name),
            "constraint_index": index,
            "constraint_type": constraint_type,
            "before": before,
            "after": after,
        }

    return active_response(
        service,
        sketch,
        run_freecad_transaction(f"Edit Sketcher constraint {index}: {getattr(sketch, 'Label', sketch.Name)}", _set),
    )
