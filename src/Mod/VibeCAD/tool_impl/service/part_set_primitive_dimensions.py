# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``part.set_primitive_dimensions``."""

from __future__ import annotations

from VibeCADTransactions import run_freecad_transaction
from . import domain_runtime


TOOL_SPEC = {'description': 'Edit an existing native Part box, cylinder, or sphere by changing its '
                'dimension properties, equivalent to correcting values in the property '
                'editor.',
 'name': 'part.set_primitive_dimensions',
 'parameters': {'properties': {'height': {'type': 'number'},
                               'length': {'type': 'number'},
                               'object_name': {'type': 'string'},
                               'radius': {'type': 'number'},
                               'width': {'type': 'number'}},
                'required': ['object_name'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartWorkbench'}


def run(
    service,
    object_name: str,
    length: float | None = None,
    width: float | None = None,
    height: float | None = None,
    radius: float | None = None,
) -> dict[str, Any]:
    obj = service._get_document_object(object_name)
    if obj is None:
        return {"ok": False, "error": f"Object not found: {object_name}"}
    type_id = getattr(obj, "TypeId", "")
    editable = {
        "Part::Box": ("Length", "Width", "Height"),
        "Part::Cylinder": ("Radius", "Height"),
        "Part::Sphere": ("Radius",),
    }
    if type_id not in editable:
        return {
            "ok": False,
            "error": f"Object is not an editable Part primitive: {object_name}",
            "type": type_id,
        }

    updates = {
        "Length": length,
        "Width": width,
        "Height": height,
        "Radius": radius,
    }
    allowed = set(editable[type_id])
    requested = {
        key: float(value)
        for key, value in updates.items()
        if value is not None and key in allowed
    }
    ignored = sorted(key for key, value in updates.items() if value is not None and key not in allowed)
    if not requested:
        return {
            "ok": False,
            "error": f"No editable dimensions were provided for {type_id}.",
            "editable_dimensions": sorted(allowed),
            "ignored_dimensions": ignored,
        }
    if any(value <= 0 for value in requested.values()):
        return {"ok": False, "error": "Primitive dimensions must be positive."}

    def _set() -> dict[str, Any]:
        target = service._get_document_object(object_name)
        if target is None:
            raise RuntimeError(f"Object not found: {object_name}")
        before = {
            key: float(getattr(target, key))
            for key in allowed
            if hasattr(target, key)
        }
        for key, value in requested.items():
            setattr(target, key, value)
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        after = {
            key: float(getattr(target, key))
            for key in allowed
            if hasattr(target, key)
        }
        return {
            "object": target.Name,
            "label": getattr(target, "Label", target.Name),
            "type": getattr(target, "TypeId", ""),
            "before": before,
            "after": after,
            "ignored_dimensions": ignored,
        }

    transaction = run_freecad_transaction(
        f"Edit Part primitive dimensions: {object_name}",
        _set,
    )
    return {"ok": bool(transaction.get("ok")), "transaction": transaction, "part": domain_runtime.part_summary(service)}
