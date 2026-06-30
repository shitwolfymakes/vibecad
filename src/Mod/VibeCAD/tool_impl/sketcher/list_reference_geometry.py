# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher reference-geometry discovery tool."""

from __future__ import annotations

from typing import Any

from .common import find_document_object, subelement_references


TOOL_SPEC = {
    "name": "sketcher.list_reference_geometry",
    "description": "List document objects and valid shape subelements that can be used as Sketcher external geometry references.",
    "safety": "READ",
    "parameters": {
        "type": "object",
        "properties": {
            "object_name": {"type": "string"},
            "max_references": {"type": "integer"},
        },
    },
}


def _object_entry(obj: Any, max_references: int) -> dict[str, Any]:
    refs = subelement_references(obj)
    return {
        "object": getattr(obj, "Name", None),
        "label": getattr(obj, "Label", getattr(obj, "Name", None)),
        "type": getattr(obj, "TypeId", None),
        "reference_count": len(refs),
        "references": refs[:max(0, int(max_references))],
        "references_truncated": len(refs) > max(0, int(max_references)),
    }


def run(
    service: Any,
    object_name: str | None = None,
    max_references: int = 80,
) -> dict[str, Any]:
    doc = service._active_document()
    if doc is None:
        return {"ok": False, "error": "No active document."}
    limit = max(1, int(max_references))
    if object_name:
        obj = find_document_object(service, object_name)
        if obj is None:
            return {"ok": False, "error": f"Object not found: {object_name}"}
        return {"ok": True, "document": doc.Name, "objects": [_object_entry(obj, limit)]}
    objects = []
    for obj in getattr(doc, "Objects", []) or []:
        if getattr(obj, "TypeId", "") == "Sketcher::SketchObject":
            continue
        refs = subelement_references(obj)
        if refs:
            objects.append(_object_entry(obj, limit))
    return {
        "ok": True,
        "document": doc.Name,
        "object_count": len(objects),
        "objects": objects[:40],
        "objects_truncated": len(objects) > 40,
    }
