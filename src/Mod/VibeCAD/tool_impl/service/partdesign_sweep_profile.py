# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.sweep_profile``."""

from __future__ import annotations

from . import domain_runtime


TOOL_SPEC = {'contextual': True,
 'description': 'Create a native PartDesign AdditivePipe or SubtractivePipe by '
                'sweeping an existing profile sketch along an existing spine sketch.',
 'name': 'partdesign.sweep_profile',
 'parameters': {'properties': {'label': {'type': 'string'},
                               'mode': {'enum': ['additive', 'subtractive'],
                                        'type': 'string'},
                               'profile_sketch_name': {'type': 'string'},
                               'spine_sketch_name': {'type': 'string'}},
                'required': ['profile_sketch_name', 'spine_sketch_name'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartDesignWorkbench'}
from VibeCADTransactions import run_freecad_transaction


def run(
    service,
    profile_sketch_name: str,
    spine_sketch_name: str,
    label: str = "VibeCAD Sweep",
    mode: str = "additive",
) -> dict[str, Any]:
    profile = service._get_sketch(profile_sketch_name)
    if profile is None:
        return {"ok": False, "error": "Profile sketch not found.", "requested": profile_sketch_name}
    spine = service._get_sketch(spine_sketch_name)
    if spine is None:
        return {"ok": False, "error": "Spine sketch not found.", "requested": spine_sketch_name}
    requested_mode = str(mode or "additive").lower()
    if requested_mode not in {"additive", "subtractive"}:
        return {"ok": False, "error": "mode must be additive or subtractive."}

    def _sweep() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active document.")
        target_profile = service._get_sketch(profile.Name)
        if target_profile is None:
            raise RuntimeError(f"Profile sketch not found: {profile.Name}")
        target_spine = service._get_sketch(spine.Name)
        if target_spine is None:
            raise RuntimeError(f"Spine sketch not found: {spine.Name}")
        body = service._partdesign_body_for_feature(target_profile)
        if body is None:
            raise RuntimeError("No PartDesign Body found for sweep.")
        if target_spine not in list(getattr(body, "Group", []) or []):
            body.addObject(target_spine)
        type_name = "PartDesign::AdditivePipe" if requested_mode == "additive" else "PartDesign::SubtractivePipe"
        object_name = "VibeCAD_AdditivePipe" if requested_mode == "additive" else "VibeCAD_SubtractivePipe"
        sweep = body.newObject(type_name, object_name)
        sweep.Label = label or "VibeCAD Sweep"
        sweep.Profile = target_profile
        sweep.Spine = target_spine
        body.Tip = sweep
        doc.recompute()
        return {
            "document": doc.Name,
            "body": body.Name,
            "profile": target_profile.Name,
            "spine": target_spine.Name,
            "feature": sweep.Name,
            "label": getattr(sweep, "Label", sweep.Name),
            "type": getattr(sweep, "TypeId", ""),
            "mode": requested_mode,
            "face_count": len(getattr(getattr(sweep, "Shape", None), "Faces", []) or []),
            "volume": float(getattr(getattr(sweep, "Shape", None), "Volume", 0.0) or 0.0),
        }

    transaction = run_freecad_transaction(
        f"Create PartDesign sweep from profile: {getattr(profile, 'Label', profile.Name)}",
        _sweep,
    )
    return {
        "ok": bool(transaction.get("ok")),
        "transaction": transaction,
        "partdesign": domain_runtime.partdesign_summary(service),
    }
