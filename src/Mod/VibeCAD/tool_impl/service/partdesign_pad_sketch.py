# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.pad_sketch``."""

from __future__ import annotations

from . import domain_runtime


TOOL_SPEC = {'contextual': True,
 'description': 'Create a native PartDesign Pad from an existing sketch, equivalent to '
                'using the Pad feature after selecting a sketch.',
 'name': 'partdesign.pad_sketch',
 'parameters': {'properties': {'label': {'type': 'string'},
                               'length': {'type': 'number'},
                               'midplane': {'type': 'boolean'},
                               'reversed': {'type': 'boolean'},
                               'sketch_name': {'type': 'string'}},
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartDesignWorkbench'}
from VibeCADTransactions import run_freecad_transaction


def _set_side_mode(feature, midplane: bool) -> str:
    requested = bool(midplane)
    if hasattr(feature, "SideType"):
        try:
            choices = list(feature.getEnumerationsOfProperty("SideType") or [])
        except Exception:
            choices = []
        if requested:
            for choice in ("Symmetric", "Two sides", "To first"):
                if not choices or choice in choices:
                    feature.SideType = choice
                    return choice
        if not choices or "One side" in choices:
            feature.SideType = "One side"
            return "One side"
    if hasattr(feature, "Midplane"):
        setattr(feature, "Midplane", requested)
        return "Midplane"
    return ""


def _is_midplane(feature) -> bool:
    side_type = getattr(feature, "SideType", "")
    if side_type:
        return side_type in {"Symmetric", "Two sides"}
    return bool(getattr(feature, "Midplane", False))


def run(
    service,
    sketch_name: str | None = None,
    label: str = "VibeCAD Pad",
    length: float = 10.0,
    reversed: bool = False,
    midplane: bool = False,
) -> dict[str, Any]:
    sketch = service._get_sketch(sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    if float(length) <= 0:
        return {"ok": False, "error": "Pad length must be positive."}
    profile_status = service._sketch_profile_status(sketch)
    if not profile_status.get("ready_for_pad"):
        if profile_status.get("closed_profile") and profile_status.get("under_constrained"):
            error = (
                "Sketch is not ready for PartDesign Pad; it has a closed profile "
                f"but remains under-constrained ({profile_status.get('degrees_of_freedom')} degrees of freedom)."
            )
        else:
            error = "Sketch is not ready for PartDesign Pad; it does not contain a closed profile that is fully constrained."
        return {
            "ok": False,
            "error": error,
            "requested": sketch_name,
            "active_sketch": getattr(sketch, "Name", None),
            "profile_status": profile_status,
            "next_actions": service._sketch_next_actions(sketch),
            "recoverable": True,
        }

    def _pad() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active document.")
        target_sketch = service._get_sketch(sketch.Name)
        if target_sketch is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        body = None
        for candidate in service._partdesign_bodies():
            if target_sketch in list(getattr(candidate, "Group", []) or []):
                body = candidate
                break
        if body is None:
            body = service._get_partdesign_body()
        if body is None:
            raise RuntimeError("No PartDesign Body found for pad.")
        body_shape_before = domain_runtime.shape_summary(body)
        pad = body.newObject("PartDesign::Pad", "VibeCAD_Pad")
        pad.Label = label or "VibeCAD Pad"
        pad.Profile = target_sketch
        pad.Length = float(length)
        pad.Reversed = bool(reversed)
        side_type = _set_side_mode(pad, bool(midplane))
        body.Tip = pad
        doc.recompute()
        feature_name = pad.Name
        feature_label = getattr(pad, "Label", pad.Name)
        feature_type = getattr(pad, "TypeId", "")
        feature_length = float(pad.Length)
        feature_reversed = bool(getattr(pad, "Reversed", False))
        feature_midplane = _is_midplane(pad)
        feature_side_type = side_type or getattr(pad, "SideType", "")
        body_shape_after = domain_runtime.shape_summary(body)
        feature_shape = domain_runtime.shape_summary(pad)
        feature_effect = domain_runtime.partdesign_feature_effect(
            "pad",
            body_shape_before,
            body_shape_after,
            feature_shape,
        )
        rolled_back_feature = False
        body_shape_after_rollback = None
        if not feature_effect.get("ok"):
            failed_feature_name = pad.Name
            doc.removeObject(failed_feature_name)
            doc.recompute()
            rolled_back_feature = True
            body_shape_after_rollback = domain_runtime.shape_summary(body)
        return {
            "document": doc.Name,
            "body": body.Name,
            "sketch": target_sketch.Name,
            "feature": feature_name,
            "label": feature_label,
            "type": feature_type,
            "length": feature_length,
            "reversed": feature_reversed,
            "midplane": feature_midplane,
            "side_type": feature_side_type,
            "body_shape_before": body_shape_before,
            "body_shape_after": body_shape_after,
            "body_shape_delta": feature_effect["body_shape_delta"],
            "feature_shape": feature_shape,
            "feature_effect": feature_effect,
            "rolled_back_feature": rolled_back_feature,
            "body_shape_after_rollback": body_shape_after_rollback,
        }

    transaction = run_freecad_transaction(
        f"Create PartDesign pad from sketch: {getattr(sketch, 'Label', sketch.Name)}",
        _pad,
    )
    transaction_result = (
        transaction.get("result", {}) if isinstance(transaction.get("result"), dict) else {}
    )
    feature_effect = transaction_result.get("feature_effect")
    effective = not isinstance(feature_effect, dict) or bool(feature_effect.get("ok"))
    ok = bool(transaction.get("ok")) and effective
    error = None
    if transaction.get("ok") and not effective:
        rollback_note = (
            " It was removed automatically to keep the Body tip coherent."
            if transaction_result.get("rolled_back_feature")
            else ""
        )
        error = (
            "PartDesign Pad was created but did not produce an effective body "
            f"shape change.{rollback_note}"
        )
    return {
        "ok": ok,
        **({"error": error, "recoverable": True} if error else {}),
        "transaction": transaction,
        "partdesign": domain_runtime.partdesign_summary(service),
        "active_feature": (
            transaction_result.get("feature")
        ),
        "active_sketch": getattr(sketch, "Name", None),
        "feature_shape": transaction_result.get("feature_shape"),
        "body_shape_before": transaction_result.get("body_shape_before"),
        "body_shape_after": transaction_result.get("body_shape_after"),
        "body_shape_delta": transaction_result.get("body_shape_delta"),
        "feature_effect": feature_effect,
        "rolled_back_feature": transaction_result.get("rolled_back_feature"),
        "body_shape_after_rollback": transaction_result.get("body_shape_after_rollback"),
        "profile_status": service._sketch_profile_status(sketch),
        "next_action": "Inspect the created feature, then create the next component/detail or capture a screenshot.",
    }
