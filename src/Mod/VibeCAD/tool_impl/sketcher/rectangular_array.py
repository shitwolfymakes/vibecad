# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher rectangular-array tool."""

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
    "name": "sketcher.rectangular_array",
    "description": (
        "Create a rectangular array of selected native Sketcher geometry using "
        "explicit row and column spacing, equivalent to using Sketcher's array "
        "workflow on selected geometry."
    ),
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "geometry_indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Geometry indices to array.",
            },
            "geometry_handles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Semantic geometry handles to array.",
            },
            "columns": {"type": "integer", "description": "Number of columns including the original column."},
            "rows": {"type": "integer", "description": "Number of rows including the original row."},
            "column_dx": {"type": "number", "description": "X offset between adjacent columns."},
            "column_dy": {"type": "number", "description": "Y offset between adjacent columns."},
            "row_dx": {"type": "number", "description": "X offset between adjacent rows."},
            "row_dy": {"type": "number", "description": "Y offset between adjacent rows."},
            "include_original": {
                "type": "boolean",
                "description": "When true, also creates a duplicate at row 0 column 0.",
            },
        },
        "required": ["columns", "rows", "column_dx", "column_dy", "row_dx", "row_dy"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    geometry_indices: list[int] | None = None,
    geometry_handles: list[str] | None = None,
    columns: int = 1,
    rows: int = 1,
    column_dx: float = 0.0,
    column_dy: float = 0.0,
    row_dx: float = 0.0,
    row_dy: float = 0.0,
    include_original: bool = False,
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
    if int(columns) < 1 or int(rows) < 1:
        return {"ok": False, "error": "columns and rows must be at least 1."}
    if int(columns) == 1 and int(rows) == 1 and not include_original:
        return {
            "ok": False,
            "error": "Array would create no new geometry; increase rows/columns or set include_original.",
        }
    for index in indices:
        invalid = validate_geometry_index(sketch, index)
        if invalid:
            return invalid

    def _array() -> dict[str, Any]:
        import FreeCAD as App

        target = get_sketch(service, sketch.Name)
        if target is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        before_count = len(getattr(target, "Geometry", []))
        created: list[int] = []
        source_geometry = list(getattr(target, "Geometry", []))
        source_handles = geometry_handles or [f"geometry:{index}" for index in indices]
        placements: list[dict[str, Any]] = []
        for row in range(int(rows)):
            for column in range(int(columns)):
                if row == 0 and column == 0 and not include_original:
                    continue
                dx = float(column_dx) * column + float(row_dx) * row
                dy = float(column_dy) * column + float(row_dy) * row
                vector = App.Vector(dx, dy, 0.0)
                for index in indices:
                    source = source_geometry[index]
                    copied = source.copy()
                    copied.translate(vector)
                    construction = bool(target.getConstruction(index))
                    new_index = int(target.addGeometry(copied, construction))
                    created.append(new_index)
                    placements.append(
                        {
                            "row": row,
                            "column": column,
                            "source_geometry_index": index,
                            "created_geometry_index": new_index,
                            "dx": dx,
                            "dy": dy,
                        }
                    )
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        geometry = [
            service._geometry_summary(list(getattr(target, "Geometry", []))[index], index)
            for index in created
        ]
        return {
            "sketch": target.Name,
            "source_geometry_indices": indices,
            "source_geometry_handles": source_handles,
            "created_geometry_indices": created,
            "geometry_index": created[0] if created else None,
            "geometry_added": len(created),
            "geometry_count_before": before_count,
            "geometry_count": len(getattr(target, "Geometry", [])),
            "columns": int(columns),
            "rows": int(rows),
            "column_vector": [float(column_dx), float(column_dy)],
            "row_vector": [float(row_dx), float(row_dy)],
            "include_original": bool(include_original),
            "placements": placements,
            "geometry": geometry,
            "old_to_new_geometry_index": {
                str(index): index
                for index in range(len(getattr(target, "Geometry", [])))
            },
        }

    return active_response(service, sketch, run_freecad_transaction("Create Sketcher rectangular array", _array))


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
