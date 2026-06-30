# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.chamfer_feature``."""

from __future__ import annotations

from . import domain_runtime


TOOL_SPEC = {'contextual': True,
 'description': 'Create a native PartDesign Chamfer feature from an existing '
                'PartDesign feature, using all edges by default or explicit edge '
                'names.',
 'name': 'partdesign.chamfer_feature',
 'parameters': {'properties': {'all_edges': {'type': 'boolean'},
                               'edge_names': {'items': {'type': 'string'},
                                              'type': 'array'},
                               'feature_name': {'type': 'string'},
                               'label': {'type': 'string'},
                               'size': {'type': 'number'}},
                'required': ['feature_name'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartDesignWorkbench'}
from VibeCADTransactions import run_freecad_transaction


def run(
    service,
    feature_name: str,
    label: str = "VibeCAD PartDesign Chamfer",
    size: float = 0.5,
    all_edges: bool = True,
    edge_names: list[str] | None = None,
) -> dict[str, Any]:
    feature = service._get_document_object(feature_name)
    if feature is None:
        return {"ok": False, "error": f"PartDesign feature not found: {feature_name}"}
    if not str(getattr(feature, "TypeId", "")).startswith("PartDesign::"):
        return {"ok": False, "error": f"Object is not a PartDesign feature: {feature_name}"}
    if float(size) <= 0:
        return {"ok": False, "error": "Chamfer size must be positive."}

    def _chamfer() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active document.")
        target = service._get_document_object(feature.Name)
        if target is None:
            raise RuntimeError(f"PartDesign feature not found: {feature.Name}")
        body = service._get_partdesign_body()
        for candidate in service._partdesign_bodies():
            if target in list(getattr(candidate, "Group", []) or []):
                body = candidate
                break
        if body is None:
            raise RuntimeError("No PartDesign Body found for chamfer.")
        body_shape_before = domain_runtime.shape_summary(body)
        chamfer = body.newObject("PartDesign::Chamfer", "VibeCAD_PD_Chamfer")
        chamfer.Label = label or "VibeCAD PartDesign Chamfer"
        selected_edges = [str(item) for item in edge_names or []]
        chamfer.Base = (target, selected_edges)
        chamfer.Size = float(size)
        chamfer.UseAllEdges = bool(all_edges or not selected_edges)
        body.Tip = chamfer
        doc.recompute()
        feature_name = chamfer.Name
        feature_label = getattr(chamfer, "Label", chamfer.Name)
        feature_type = getattr(chamfer, "TypeId", "")
        feature_size = float(chamfer.Size)
        feature_use_all_edges = bool(getattr(chamfer, "UseAllEdges", False))
        face_count = len(getattr(getattr(chamfer, "Shape", None), "Faces", []) or [])
        volume = float(getattr(getattr(chamfer, "Shape", None), "Volume", 0.0) or 0.0)
        effect = domain_runtime.finalize_partdesign_feature_effect(
            doc,
            body,
            chamfer,
            "chamfer",
            body_shape_before,
        )
        return {
            "document": doc.Name,
            "body": body.Name,
            "base_feature": target.Name,
            "feature": feature_name,
            "label": feature_label,
            "type": feature_type,
            "size": feature_size,
            "use_all_edges": feature_use_all_edges,
            "edge_names": selected_edges,
            "face_count": face_count,
            "volume": volume,
            **effect,
        }

    transaction = run_freecad_transaction(
        f"Create PartDesign chamfer from feature: {getattr(feature, 'Label', feature.Name)}",
        _chamfer,
    )
    transaction_result = transaction.get("result", {}) if isinstance(transaction.get("result"), dict) else {}
    feature_effect = transaction_result.get("feature_effect")
    effective = not isinstance(feature_effect, dict) or bool(feature_effect.get("ok"))
    ok = bool(transaction.get("ok")) and effective
    error = None
    if not transaction.get("ok"):
        error = transaction.get("error") or "PartDesign Chamfer failed."
    elif not effective:
        rollback_note = (
            " It was removed automatically to keep the Body tip coherent."
            if transaction_result.get("rolled_back_feature")
            else ""
        )
        error = f"PartDesign Chamfer was created but did not produce an effective body shape change.{rollback_note}"
    return {
        "ok": ok,
        **({"error": error, "recoverable": True} if error else {}),
        "transaction": transaction,
        "partdesign": domain_runtime.partdesign_summary(service),
        "active_feature": transaction_result.get("feature"),
        "feature_shape": transaction_result.get("feature_shape"),
        "body_shape_before": transaction_result.get("body_shape_before"),
        "body_shape_after": transaction_result.get("body_shape_after"),
        "body_shape_delta": transaction_result.get("body_shape_delta"),
        "feature_effect": feature_effect,
        "rolled_back_feature": transaction_result.get("rolled_back_feature"),
        "body_shape_after_rollback": transaction_result.get("body_shape_after_rollback"),
    }
