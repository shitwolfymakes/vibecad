# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher constraint expression tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, resolve_constraint_index, run_freecad_transaction, validate_constraint_index


TOOL_SPEC = {
    "name": "sketcher.set_constraint_expression",
    "description": (
        "Set or clear a Sketcher dimensional constraint expression using FreeCAD's "
        "native setExpression API. Empty expression clears the binding."
    ),
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "constraint_index": {"type": "integer"},
            "constraint_name": {"type": "string"},
            "constraint_handle": {"type": "string"},
            "expression": {"type": "string"},
        },
        "required": ["expression"],
    },
}


def run(
    service: Any,
    expression: str,
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

    def _set_expression() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        path = f"Constraints[{index}]"
        value = str(expression).strip()
        target.setExpression(path, value or None)
        if App.ActiveDocument is not None:
            App.ActiveDocument.recompute()
        expressions = {}
        try:
            expressions = {str(expr_path): str(expr) for expr_path, expr in target.ExpressionEngine}
        except Exception:
            expressions = {}
        return {
            "sketch": target.Name,
            "constraint_index": index,
            "constraint_handle": constraint_handle or f"constraint:{index}",
            "constraint_name": constraint_name,
            "expression_path": path,
            "expression": expressions.get(path),
        }

    return active_response(
        service,
        sketch,
        run_freecad_transaction(f"Set Sketcher constraint {index} expression", _set_expression),
    )
