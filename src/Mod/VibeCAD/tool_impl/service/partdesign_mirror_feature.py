# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.mirror_feature``."""

from __future__ import annotations

from . import domain_runtime


TOOL_SPEC = {'contextual': True,
 'description': 'Create a native PartDesign Mirrored feature from an existing '
                'PartDesign feature across a Body origin plane.',
 'name': 'partdesign.mirror_feature',
 'parameters': {'properties': {'feature_name': {'type': 'string'},
                               'label': {'type': 'string'},
                               'mirror_plane': {'enum': ['XY_Plane',
                                                         'XZ_Plane',
                                                         'YZ_Plane'],
                                                'type': 'string'},
                               'refine': {'type': 'boolean'}},
                'required': ['feature_name'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartDesignWorkbench'}
from VibeCADTransactions import run_freecad_transaction


def run(
    service,
    feature_name: str,
    label: str = "VibeCAD Mirrored Feature",
    mirror_plane: str = "YZ_Plane",
    refine: bool = True,
) -> dict[str, Any]:
    feature = service._get_document_object(feature_name)
    if feature is None:
        return {"ok": False, "error": f"PartDesign feature not found: {feature_name}"}
    if not str(getattr(feature, "TypeId", "")).startswith("PartDesign::"):
        return {"ok": False, "error": f"Object is not a PartDesign feature: {feature_name}"}
    requested_plane = str(mirror_plane or "YZ_Plane")
    if requested_plane not in {"XY_Plane", "XZ_Plane", "YZ_Plane"}:
        return {"ok": False, "error": "mirror_plane must be XY_Plane, XZ_Plane, or YZ_Plane."}

    def _mirror() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active document.")
        target = service._get_document_object(feature.Name)
        if target is None:
            raise RuntimeError(f"PartDesign feature not found: {feature.Name}")
        body = service._partdesign_body_for_feature(target)
        if body is None:
            raise RuntimeError("No PartDesign Body found for mirrored feature.")
        plane_feature = service._partdesign_origin_feature(body, requested_plane)
        if plane_feature is None:
            raise RuntimeError(f"Body origin mirror plane not found: {requested_plane}")
        body_shape_before = domain_runtime.shape_summary(body)
        mirrored = body.newObject("PartDesign::Mirrored", "VibeCAD_Mirrored")
        mirrored.Label = label or "VibeCAD Mirrored Feature"
        mirrored.Originals = [target]
        mirrored.MirrorPlane = (plane_feature, [""])
        mirrored.Refine = bool(refine)
        body.Tip = mirrored
        doc.recompute()
        feature_name = mirrored.Name
        feature_label = getattr(mirrored, "Label", mirrored.Name)
        feature_type = getattr(mirrored, "TypeId", "")
        feature_refine = bool(getattr(mirrored, "Refine", False))
        solid_count = len(getattr(getattr(mirrored, "Shape", None), "Solids", []) or [])
        volume = float(getattr(getattr(mirrored, "Shape", None), "Volume", 0.0) or 0.0)
        effect = domain_runtime.finalize_partdesign_feature_effect(
            doc,
            body,
            mirrored,
            "mirror",
            body_shape_before,
        )
        return {
            "document": doc.Name,
            "body": body.Name,
            "base_feature": target.Name,
            "feature": feature_name,
            "label": feature_label,
            "type": feature_type,
            "mirror_plane": requested_plane,
            "refine": feature_refine,
            "solid_count": solid_count,
            "volume": volume,
            **effect,
        }

    transaction = run_freecad_transaction(
        f"Create PartDesign mirrored feature from feature: {getattr(feature, 'Label', feature.Name)}",
        _mirror,
    )
    transaction_result = transaction.get("result", {}) if isinstance(transaction.get("result"), dict) else {}
    feature_effect = transaction_result.get("feature_effect")
    effective = not isinstance(feature_effect, dict) or bool(feature_effect.get("ok"))
    response = {
        "ok": bool(transaction.get("ok")) and effective,
        **(
            {
                "error": (
                    "PartDesign Mirrored feature was created but did not produce an "
                    "effective body shape change."
                    + (
                        " It was removed automatically to keep the Body tip coherent."
                        if transaction_result.get("rolled_back_feature")
                        else ""
                    )
                ),
                "recoverable": True,
            }
            if transaction.get("ok") and not effective
            else {}
        ),
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
    if not response["ok"]:
        body = service._partdesign_body_for_feature(feature)
        response.setdefault(
            "error",
            transaction.get("error") or "PartDesign mirror feature failed.",
        )
        response["recoverable"] = True
        response["failure_context"] = {
            "feature": service._object_summary(feature),
            "body": service._partdesign_body_summary(body) if body is not None else None,
            "mirror_plane": requested_plane,
            "document_delta": transaction.get("document_delta"),
            "report_view_errors": transaction.get("report_view_errors"),
        }
        response["next_actions"] = [
            {
                "tool": "partdesign.get_bodies",
                "why": "Inspect the active Body, feature names, Tip, and origin planes before retrying the mirror.",
            },
            {
                "tool": "core.get_object_properties",
                "arguments": {"object_name": feature.Name},
                "why": "Verify the selected original feature exists, is inside the expected Body, and has a valid shape.",
            },
            {
                "tool": "core.delete_object",
                "why": "If the failed mirror left invalid feature objects in the document delta, delete those invalid objects before continuing.",
            },
            {
                "tool": "partdesign.create_sketch",
                "why": "If the same native mirror fails with the same invalid-shape error, create the opposite-side detail as a normal sketch-driven PartDesign feature instead of retrying the unchanged mirror.",
            },
        ]
    return response
