# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.draft_feature``."""

from __future__ import annotations

from typing import Any

from . import domain_runtime
from VibeCADTransactions import run_freecad_transaction


TOOL_SPEC = {'contextual': True,
 'description': 'Create a native PartDesign Draft feature on selected faces of an '
                'existing PartDesign feature using explicit neutral plane and pull '
                'direction references.',
 'name': 'partdesign.draft_feature',
 'parameters': {'properties': {'angle': {'type': 'number'},
                               'face_names': {'description': 'Face names to draft, such as Face1 or Face6.',
                                              'items': {'type': 'string'},
                                              'type': 'array'},
                               'feature_name': {'description': 'Base PartDesign feature internal name or label.',
                                                'type': 'string'},
                               'label': {'type': 'string'},
                               'neutral_plane_name': {'description': 'PartDesign Datum Plane or other neutral-plane object name/label.',
                                                      'type': 'string'},
                               'pull_direction_name': {'description': 'PartDesign Datum Line or other pull-direction object name/label.',
                                                       'type': 'string'},
                               'reversed': {'type': 'boolean'}},
                'required': ['feature_name', 'face_names', 'neutral_plane_name', 'pull_direction_name'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartDesignWorkbench'}


def run(
    service,
    feature_name: str,
    face_names: list[str],
    neutral_plane_name: str,
    pull_direction_name: str,
    label: str = "VibeCAD PartDesign Draft",
    angle: float = 3.0,
    reversed: bool = False,
) -> dict[str, Any]:
    feature = _get_body_item(service, feature_name)
    if feature is None:
        return {"ok": False, "error": f"PartDesign feature not found: {feature_name}"}
    if not str(getattr(feature, "TypeId", "")).startswith("PartDesign::"):
        return {"ok": False, "error": f"Object is not a PartDesign feature: {feature_name}"}
    neutral_plane = _get_body_item(service, neutral_plane_name)
    if neutral_plane is None:
        return {"ok": False, "error": f"Neutral plane object not found: {neutral_plane_name}"}
    pull_direction = _get_body_item(service, pull_direction_name)
    if pull_direction is None:
        return {"ok": False, "error": f"Pull direction object not found: {pull_direction_name}"}
    selected_faces = [str(item) for item in (face_names or [])]
    if not selected_faces:
        return {"ok": False, "error": "At least one face name is required."}
    if float(angle) <= 0 or float(angle) >= 89:
        return {"ok": False, "error": "Draft angle must be greater than 0 and less than 89 degrees."}

    def _draft() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active document.")
        target = _get_body_item(service, feature.Name)
        if target is None:
            raise RuntimeError(f"PartDesign feature not found: {feature.Name}")
        body = service._partdesign_body_for_feature(target)
        if body is None:
            raise RuntimeError("No PartDesign Body found for draft.")
        neutral = _get_body_item(service, neutral_plane.Name)
        pull = _get_body_item(service, pull_direction.Name)
        if neutral is None or pull is None:
            raise RuntimeError("Draft neutral plane or pull direction is missing.")
        faces = list(getattr(getattr(target, "Shape", None), "Faces", []) or [])
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
        draft = doc.addObject("PartDesign::Draft", "VibeCAD_PD_Draft")
        draft.Label = label or "VibeCAD PartDesign Draft"
        draft.Base = (target, selected_faces)
        draft.NeutralPlane = (neutral, [""])
        draft.PullDirection = (pull, [""])
        draft.Angle = float(angle)
        draft.Reversed = bool(reversed)
        body.addObject(draft)
        body.Tip = draft
        doc.recompute()
        if "Invalid" in list(getattr(draft, "State", []) or []):
            draft.Reversed = not bool(getattr(draft, "Reversed", False))
            doc.recompute()
        draft_name = draft.Name
        draft_label = getattr(draft, "Label", draft.Name)
        draft_type = getattr(draft, "TypeId", "")
        draft_angle = float(draft.Angle)
        draft_reversed = bool(getattr(draft, "Reversed", False))
        effect = domain_runtime.finalize_partdesign_feature_effect(
            doc,
            body,
            draft,
            "draft",
            body_shape_before,
        )
        return {
            "document": doc.Name,
            "body": body.Name,
            "base_feature": target.Name,
            "feature": draft_name,
            "label": draft_label,
            "type": draft_type,
            "face_names": selected_faces,
            "neutral_plane": neutral.Name,
            "pull_direction": pull.Name,
            "angle": draft_angle,
            "reversed": draft_reversed,
            **effect,
        }

    transaction = run_freecad_transaction(
        f"Create PartDesign draft from feature: {getattr(feature, 'Label', feature.Name)}",
        _draft,
    )
    transaction_result = transaction.get("result", {}) if isinstance(transaction.get("result"), dict) else {}
    feature_effect = transaction_result.get("feature_effect")
    effective = not isinstance(feature_effect, dict) or bool(feature_effect.get("ok"))
    ok = bool(transaction.get("ok")) and effective
    error = None
    if not transaction.get("ok"):
        error = transaction.get("error") or "PartDesign Draft failed."
    elif not effective:
        rollback_note = (
            " It was removed automatically to keep the Body tip coherent."
            if transaction_result.get("rolled_back_feature")
            else ""
        )
        error = f"PartDesign Draft was created but did not produce an effective body shape change.{rollback_note}"
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


def _get_body_item(service, name_or_label: str):
    item = service._get_document_object(name_or_label)
    if item is not None:
        return item
    for body in service._partdesign_bodies():
        if getattr(body, "Label", None) == name_or_label:
            return body
        for child in list(getattr(body, "Group", []) or []):
            if getattr(child, "Name", None) == name_or_label or getattr(child, "Label", None) == name_or_label:
                return child
    return None
