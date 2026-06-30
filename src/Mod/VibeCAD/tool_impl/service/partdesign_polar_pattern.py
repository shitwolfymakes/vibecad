# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.polar_pattern``."""

from __future__ import annotations

from . import domain_runtime


TOOL_SPEC = {'contextual': True,
 'description': 'Create a native PartDesign PolarPattern from an existing PartDesign '
                'feature around a Body origin axis.',
 'name': 'partdesign.polar_pattern',
 'parameters': {'properties': {'angle': {'type': 'number'},
                               'axis': {'enum': ['X_Axis', 'Y_Axis', 'Z_Axis'],
                                        'type': 'string'},
                               'feature_name': {'type': 'string'},
                               'label': {'type': 'string'},
                               'occurrences': {'type': 'integer'},
                               'refine': {'type': 'boolean'}},
                'required': ['feature_name'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartDesignWorkbench'}
from VibeCADTransactions import run_freecad_transaction


def run(
    service,
    feature_name: str,
    label: str = "VibeCAD Polar Pattern",
    axis: str = "Z_Axis",
    angle: float = 360.0,
    occurrences: int = 4,
    refine: bool = True,
) -> dict[str, Any]:
    feature = service._get_document_object(feature_name)
    if feature is None:
        return {"ok": False, "error": f"PartDesign feature not found: {feature_name}"}
    if not str(getattr(feature, "TypeId", "")).startswith("PartDesign::"):
        return {"ok": False, "error": f"Object is not a PartDesign feature: {feature_name}"}
    requested_axis = str(axis or "Z_Axis")
    if requested_axis not in {"X_Axis", "Y_Axis", "Z_Axis"}:
        return {"ok": False, "error": "axis must be X_Axis, Y_Axis, or Z_Axis."}
    if float(angle) <= 0 or float(angle) > 360:
        return {"ok": False, "error": "Polar pattern angle must be greater than 0 and no more than 360 degrees."}
    if int(occurrences) < 2:
        return {"ok": False, "error": "Polar pattern occurrences must be at least 2."}

    def _polar_pattern() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active document.")
        target = service._get_document_object(feature.Name)
        if target is None:
            raise RuntimeError(f"PartDesign feature not found: {feature.Name}")
        body = service._partdesign_body_for_feature(target)
        if body is None:
            raise RuntimeError("No PartDesign Body found for polar pattern.")
        axis_feature = service._partdesign_origin_feature(body, requested_axis)
        if axis_feature is None:
            raise RuntimeError(f"Body origin axis not found: {requested_axis}")
        body_shape_before = domain_runtime.shape_summary(body)
        pattern = body.newObject("PartDesign::PolarPattern", "VibeCAD_PolarPattern")
        pattern.Label = label or "VibeCAD Polar Pattern"
        pattern.Originals = [target]
        pattern.Axis = (axis_feature, [""])
        pattern.Angle = float(angle)
        pattern.Occurrences = int(occurrences)
        pattern.Refine = bool(refine)
        body.Tip = pattern
        doc.recompute()
        feature_name = pattern.Name
        feature_label = getattr(pattern, "Label", pattern.Name)
        feature_type = getattr(pattern, "TypeId", "")
        feature_angle = float(pattern.Angle)
        feature_occurrences = int(pattern.Occurrences)
        feature_refine = bool(getattr(pattern, "Refine", False))
        solid_count = len(getattr(getattr(pattern, "Shape", None), "Solids", []) or [])
        volume = float(getattr(getattr(pattern, "Shape", None), "Volume", 0.0) or 0.0)
        effect = domain_runtime.finalize_partdesign_feature_effect(
            doc,
            body,
            pattern,
            "polar_pattern",
            body_shape_before,
        )
        return {
            "document": doc.Name,
            "body": body.Name,
            "base_feature": target.Name,
            "feature": feature_name,
            "label": feature_label,
            "type": feature_type,
            "axis": requested_axis,
            "angle": feature_angle,
            "occurrences": feature_occurrences,
            "refine": feature_refine,
            "solid_count": solid_count,
            "volume": volume,
            **effect,
        }

    transaction = run_freecad_transaction(
        f"Create PartDesign polar pattern from feature: {getattr(feature, 'Label', feature.Name)}",
        _polar_pattern,
    )
    transaction_result = transaction.get("result", {}) if isinstance(transaction.get("result"), dict) else {}
    feature_effect = transaction_result.get("feature_effect")
    effective = not isinstance(feature_effect, dict) or bool(feature_effect.get("ok"))
    ok = bool(transaction.get("ok")) and effective
    error = None
    if not transaction.get("ok"):
        error = transaction.get("error") or "PartDesign PolarPattern failed."
    elif not effective:
        rollback_note = (
            " It was removed automatically to keep the Body tip coherent."
            if transaction_result.get("rolled_back_feature")
            else ""
        )
        error = f"PartDesign PolarPattern was created but did not produce an effective body shape change.{rollback_note}"
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
