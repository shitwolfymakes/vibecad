# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher construction-geometry toggle tool."""

from __future__ import annotations

from typing import Any

from .common import active_response, get_sketch, resolve_geometry_index, run_freecad_transaction, validate_geometry_index


TOOL_SPEC = {
    "name": "sketcher.set_construction",
    "description": "Set one Sketcher geometry element as construction or normal geometry, equivalent to toggling construction mode for selected geometry.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "geometry_index": {"type": "integer"},
            "geometry_handle": {"type": "string"},
            "construction": {"type": "boolean"},
        },
        "required": ["construction"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    geometry_index: int | None = None,
    geometry_handle: str | None = None,
    construction: bool = True,
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

    def _set() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before = bool(target.getConstruction(index))
        target.setConstruction(index, bool(construction))
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        return {
            "sketch": target.Name,
            "geometry_index": index,
            "geometry_handle": geometry_handle or f"geometry:{index}",
            "before": before,
            "after": bool(target.getConstruction(index)),
        }

    return active_response(service, sketch, run_freecad_transaction("Set Sketcher construction geometry", _set))
