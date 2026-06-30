# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.thickness_feature``."""

from __future__ import annotations

from typing import Any

from . import domain_runtime
from VibeCADTransactions import run_freecad_transaction


TOOL_SPEC = {'contextual': True,
 'description': 'Create a native PartDesign Thickness feature from an existing '
                'PartDesign feature by removing selected faces and applying wall '
                'thickness inside the Body feature history.',
 'name': 'partdesign.thickness_feature',
 'parameters': {'properties': {'face_names': {'description': 'Face names to remove, '
                                                             'such as Face1 or Face6.',
                                              'items': {'type': 'string'},
                                              'type': 'array'},
                               'feature_name': {'description': 'Base PartDesign feature '
                                                              'internal name or label.',
                                                'type': 'string'},
                               'inward': {'description': 'When true, make thickness '
                                                        'inwards like the PartDesign '
                                                        'task panel option.',
                                          'type': 'boolean'},
                               'join': {'description': 'Native PartDesign thickness '
                                                      'join mode integer.',
                                        'type': 'integer'},
                               'label': {'type': 'string'},
                               'mode': {'description': 'Native PartDesign thickness '
                                                      'mode integer.',
                                        'type': 'integer'},
                               'wall_thickness': {'type': 'number'}},
                'required': ['feature_name'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartDesignWorkbench'}


def run(
    service,
    feature_name: str,
    label: str = "VibeCAD PartDesign Thickness",
    wall_thickness: float = 1.5,
    face_names: list[str] | None = None,
    inward: bool = True,
    mode: int = 0,
    join: int = 0,
) -> dict[str, Any]:
    feature = service._get_document_object(feature_name)
    if feature is None:
        feature = _partdesign_feature_by_label(service, feature_name)
    if feature is None:
        return {"ok": False, "error": f"PartDesign feature not found: {feature_name}"}
    if not str(getattr(feature, "TypeId", "")).startswith("PartDesign::"):
        return {"ok": False, "error": f"Object is not a PartDesign feature: {feature_name}"}
    if float(wall_thickness) <= 0:
        return {"ok": False, "error": "wall_thickness must be positive."}
    selected_faces = [str(item) for item in (face_names or ["Face1"])]
    if not selected_faces:
        return {"ok": False, "error": "At least one face name is required."}

    def _thickness() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active document.")
        target = service._get_document_object(feature.Name)
        if target is None:
            raise RuntimeError(f"PartDesign feature not found: {feature.Name}")
        body = service._partdesign_body_for_feature(target)
        if body is None:
            raise RuntimeError("No PartDesign Body found for thickness.")
        shape = getattr(target, "Shape", None)
        faces = list(getattr(shape, "Faces", []) or [])
        if not faces:
            raise RuntimeError(f"Feature has no faces for thickness: {target.Name}")
        for face_name in selected_faces:
            if not face_name.startswith("Face"):
                raise RuntimeError(f"Invalid face name: {face_name}")
            try:
                face_index = int(face_name[4:])
            except ValueError as exc:
                raise RuntimeError(f"Invalid face name: {face_name}") from exc
            if face_index < 1 or face_index > len(faces):
                raise RuntimeError(f"Face name out of range for {target.Name}: {face_name}")

        body_shape_before = domain_runtime.shape_summary(body)
        thickness = doc.addObject("PartDesign::Thickness", "VibeCAD_PD_Thickness")
        thickness.Label = label or "VibeCAD PartDesign Thickness"
        thickness.Base = (target, selected_faces)
        body.addObject(thickness)
        thickness.Value = float(wall_thickness)
        thickness.Reversed = 1 if inward else 0
        thickness.Mode = int(mode)
        thickness.Join = int(join)
        thickness.Base = (target, selected_faces)
        body.Tip = thickness
        doc.recompute()
        effect = domain_runtime.finalize_partdesign_feature_effect(
            doc,
            body,
            thickness,
            "thickness",
            body_shape_before,
        )
        return {
            "document": doc.Name,
            "body": body.Name,
            "base_feature": target.Name,
            "feature": thickness.Name,
            "label": getattr(thickness, "Label", thickness.Name),
            "type": getattr(thickness, "TypeId", ""),
            "face_names": selected_faces,
            "wall_thickness": float(wall_thickness),
            "inward": bool(inward),
            "mode": int(mode),
            "join": int(join),
            **effect,
        }

    transaction = run_freecad_transaction(
        f"Create PartDesign thickness from feature: {getattr(feature, 'Label', feature.Name)}",
        _thickness,
    )
    transaction_result = transaction.get("result", {}) if isinstance(transaction.get("result"), dict) else {}
    feature_effect = transaction_result.get("feature_effect")
    effective = not isinstance(feature_effect, dict) or bool(feature_effect.get("ok"))
    ok = bool(transaction.get("ok")) and effective
    error = None
    if not transaction.get("ok"):
        error = transaction.get("error") or "PartDesign Thickness failed."
    elif not effective:
        rollback_note = (
            " It was removed automatically to keep the Body tip coherent."
            if transaction_result.get("rolled_back_feature")
            else ""
        )
        error = (
            "PartDesign Thickness was created but did not produce an effective "
            f"body shape change.{rollback_note}"
        )
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


def _partdesign_feature_by_label(service, label: str):
    for body in service._partdesign_bodies():
        for item in list(getattr(body, "Group", []) or []):
            if getattr(item, "Label", None) == label:
                return item
    return None
