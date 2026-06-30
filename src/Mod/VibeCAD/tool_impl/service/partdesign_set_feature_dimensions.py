# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.set_feature_dimensions``."""

from __future__ import annotations

from . import domain_runtime


TOOL_SPEC = {'contextual': True,
 'description': 'Edit existing PartDesign feature dimension properties such as Pad '
                'Length or AdditiveBox Length/Width/Height in place.',
 'name': 'partdesign.set_feature_dimensions',
 'parameters': {'properties': {'feature_name': {'type': 'string'},
                               'height': {'type': 'number'},
                               'length': {'type': 'number'},
                               'radius': {'type': 'number'},
                               'width': {'type': 'number'}},
                'required': ['feature_name'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartDesignWorkbench'}
from VibeCADTransactions import run_freecad_transaction


def run(
    service,
    feature_name: str,
    length: float | None = None,
    width: float | None = None,
    height: float | None = None,
    radius: float | None = None,
) -> dict[str, Any]:
    feature = service._get_document_object(feature_name)
    if feature is None:
        return {"ok": False, "error": f"PartDesign feature not found: {feature_name}"}
    type_id = getattr(feature, "TypeId", "")
    editable = {
        "Length": length,
        "Width": width,
        "Height": height,
        "Radius": radius,
    }
    requested = {
        key: float(value)
        for key, value in editable.items()
        if value is not None and hasattr(feature, key)
    }
    ignored = sorted(key for key, value in editable.items() if value is not None and not hasattr(feature, key))
    if not type_id.startswith("PartDesign::"):
        return {
            "ok": False,
            "error": f"Object is not a PartDesign feature: {feature_name}",
            "type": type_id,
        }
    if not requested:
        return {
            "ok": False,
            "error": "No editable PartDesign dimension properties were provided.",
            "type": type_id,
            "ignored_dimensions": ignored,
        }
    if any(value <= 0 for value in requested.values()):
        return {"ok": False, "error": "PartDesign feature dimensions must be positive."}

    def _set() -> dict[str, Any]:
        import FreeCAD as App

        target = service._get_document_object(feature_name)
        if target is None:
            raise RuntimeError(f"PartDesign feature not found: {feature_name}")
        before = {
            key: float(getattr(target, key))
            for key in requested
            if hasattr(target, key)
        }
        for key, value in requested.items():
            setattr(target, key, value)
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        after = {
            key: float(getattr(target, key))
            for key in requested
            if hasattr(target, key)
        }
        return {
            "feature": target.Name,
            "label": getattr(target, "Label", target.Name),
            "type": getattr(target, "TypeId", ""),
            "before": before,
            "after": after,
            "ignored_dimensions": ignored,
        }

    transaction = run_freecad_transaction(
        f"Edit PartDesign feature dimensions: {feature_name}",
        _set,
    )
    return {
        "ok": bool(transaction.get("ok")),
        "transaction": transaction,
        "partdesign": domain_runtime.partdesign_summary(service),
    }
