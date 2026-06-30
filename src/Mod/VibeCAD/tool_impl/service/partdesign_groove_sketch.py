# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.groove_sketch``."""

from __future__ import annotations

from typing import Any

from . import domain_runtime
from .partdesign_revolve_sketch import _revolution_profile_preflight, _set_revolve_midplane
from VibeCADTransactions import run_freecad_transaction


TOOL_SPEC = {'contextual': True,
 'description': 'Create a native PartDesign Groove from an existing closed sketch '
                'around a Body origin axis, equivalent to the human subtractive '
                'revolve/groove workflow.',
 'name': 'partdesign.groove_sketch',
 'parameters': {'properties': {'angle': {'type': 'number'},
                               'axis': {'enum': ['X_Axis', 'Y_Axis', 'Z_Axis'],
                                        'type': 'string'},
                               'label': {'type': 'string'},
                               'midplane': {'type': 'boolean'},
                               'reversed': {'type': 'boolean'},
                               'sketch_name': {'type': 'string'}},
                'required': ['sketch_name'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartDesignWorkbench'}


def run(
    service,
    sketch_name: str | None = None,
    label: str = "VibeCAD Groove",
    angle: float = 360.0,
    axis: str = "X_Axis",
    reversed: bool = False,
    midplane: bool = False,
) -> dict[str, Any]:
    sketch = service._get_sketch(sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    if float(angle) <= 0 or float(angle) > 360:
        return {"ok": False, "error": "Groove angle must be greater than 0 and no more than 360 degrees."}
    requested_axis = str(axis or "X_Axis")
    if requested_axis not in {"X_Axis", "Y_Axis", "Z_Axis"}:
        return {"ok": False, "error": "axis must be X_Axis, Y_Axis, or Z_Axis."}
    preflight = _revolution_profile_preflight(service, sketch, requested_axis)
    if not preflight.get("ok"):
        return {
            "ok": False,
            "error": str(preflight.get("reason") or "Sketch is not valid for PartDesign Groove."),
            "recoverable": True,
            "active_sketch": getattr(sketch, "Name", None),
            "groove_preflight": preflight,
            "profile_status": preflight.get("profile_status"),
            "next_actions": [
                {
                    "tool": "sketcher.validate_profile_deep",
                    "arguments": {"sketch_name": getattr(sketch, "Name", None)},
                    "why": "Inspect open endpoints, self-intersections, and profile topology before retrying the groove.",
                },
                {
                    "tool": "sketcher.list_geometry",
                    "arguments": {"sketch_name": getattr(sketch, "Name", None)},
                    "why": "Inspect geometry coordinates relative to the requested groove axis.",
                },
                {
                    "tool": "sketcher.move_point",
                    "why": "Move or resize the profile so it stays on one side of the requested groove axis.",
                },
            ],
        }

    def _groove() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active document.")
        target_sketch = service._get_sketch(sketch.Name)
        if target_sketch is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        body = service._partdesign_body_for_feature(target_sketch)
        if body is None:
            raise RuntimeError("No PartDesign Body found for groove.")
        axis_feature = service._partdesign_origin_feature(body, requested_axis)
        if axis_feature is None:
            raise RuntimeError(f"Body origin axis not found: {requested_axis}")
        body_shape_before = domain_runtime.shape_summary(body)
        groove = body.newObject("PartDesign::Groove", "VibeCAD_Groove")
        groove.Label = label or "VibeCAD Groove"
        groove.Profile = target_sketch
        groove.ReferenceAxis = (axis_feature, [""])
        groove.Angle = float(angle)
        groove.Reversed = bool(reversed)
        actual_midplane = _set_revolve_midplane(groove, bool(midplane))
        body.Tip = groove
        doc.recompute()
        groove_name = groove.Name
        groove_label = getattr(groove, "Label", groove.Name)
        groove_type = getattr(groove, "TypeId", "")
        groove_angle = float(groove.Angle)
        groove_reversed = bool(getattr(groove, "Reversed", False))
        effect = domain_runtime.finalize_partdesign_feature_effect(
            doc,
            body,
            groove,
            "groove",
            body_shape_before,
        )
        return {
            "document": doc.Name,
            "body": body.Name,
            "sketch": target_sketch.Name,
            "feature": groove_name,
            "label": groove_label,
            "type": groove_type,
            "angle": groove_angle,
            "axis": requested_axis,
            "reversed": groove_reversed,
            "midplane": actual_midplane,
            "groove_preflight": preflight,
            **effect,
        }

    transaction = run_freecad_transaction(
        f"Create PartDesign groove from sketch: {getattr(sketch, 'Label', sketch.Name)}",
        _groove,
    )
    transaction_result = transaction.get("result", {}) if isinstance(transaction.get("result"), dict) else {}
    feature_effect = transaction_result.get("feature_effect")
    effective = not isinstance(feature_effect, dict) or bool(feature_effect.get("ok"))
    ok = bool(transaction.get("ok")) and effective
    error = None
    if not transaction.get("ok"):
        error = transaction.get("error") or "PartDesign Groove failed."
    elif not effective:
        rollback_note = (
            " It was removed automatically to keep the Body tip coherent."
            if transaction_result.get("rolled_back_feature")
            else ""
        )
        error = f"PartDesign Groove was created but did not remove material from the body.{rollback_note}"
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
        "sketcher": service.sketcher_summary(getattr(sketch, "Name", None)),
        "next_action": "Inspect the groove feature, then continue adding native PartDesign detail.",
    }
