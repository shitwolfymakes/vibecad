# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``draft.create_array``."""

from __future__ import annotations

from VibeCADTransactions import run_freecad_transaction
from . import domain_runtime


TOOL_SPEC = {'description': 'Create a native Draft orthogonal or polar array from an existing '
                'object for repeated holes, vents, motors, wheels, ribs, or other '
                'patterned CAD features.',
 'name': 'draft.create_array',
 'parameters': {'properties': {'array_type': {'enum': ['ortho', 'polar'],
                                              'type': 'string'},
                               'center_x': {'type': 'number'},
                               'center_y': {'type': 'number'},
                               'center_z': {'type': 'number'},
                               'interval_x': {'type': 'number'},
                               'interval_y': {'type': 'number'},
                               'interval_z': {'type': 'number'},
                               'label': {'type': 'string'},
                               'number_x': {'type': 'integer'},
                               'number_y': {'type': 'integer'},
                               'number_z': {'type': 'integer'},
                               'object_name': {'type': 'string'},
                               'polar_angle': {'type': 'number'},
                               'polar_count': {'type': 'integer'},
                               'use_link': {'type': 'boolean'}},
                'required': ['object_name', 'array_type'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'DraftWorkbench'}


def run(
    service,
    object_name: str,
    label: str = "VibeCAD Array",
    array_type: str = "ortho",
    number_x: int = 2,
    number_y: int = 1,
    number_z: int = 1,
    interval_x: float = 10.0,
    interval_y: float = 0.0,
    interval_z: float = 0.0,
    polar_count: int = 4,
    polar_angle: float = 360.0,
    center_x: float = 0.0,
    center_y: float = 0.0,
    center_z: float = 0.0,
    use_link: bool = False,
) -> dict[str, Any]:
    source = service._get_document_object(object_name)
    if source is None:
        return {"ok": False, "error": f"Object not found: {object_name}"}
    kind = str(array_type or "ortho").lower().strip()
    if kind in {"orthogonal", "rect", "rectangular"}:
        kind = "ortho"
    if kind not in {"ortho", "polar"}:
        return {"ok": False, "error": "array_type must be ortho or polar"}
    if kind == "ortho":
        counts = (int(number_x), int(number_y), int(number_z))
        if any(count < 1 for count in counts) or counts == (1, 1, 1):
            return {"ok": False, "error": "Ortho arrays need positive counts and at least one repeated axis."}
    else:
        if int(polar_count) < 2:
            return {"ok": False, "error": "Polar arrays need at least two copies."}

    def _create() -> dict[str, Any]:
        import FreeCAD as App
        import Draft

        base = service._get_document_object(object_name)
        if base is None:
            raise RuntimeError(f"Object not found: {object_name}")
        if kind == "ortho":
            array_obj = Draft.make_ortho_array(
                base,
                App.Vector(float(interval_x), 0, 0),
                App.Vector(0, float(interval_y), 0),
                App.Vector(0, 0, float(interval_z)),
                int(number_x),
                int(number_y),
                int(number_z),
                use_link=bool(use_link),
            )
            metadata = {
                "array_type": "ortho",
                "counts": [int(number_x), int(number_y), int(number_z)],
                "intervals": [float(interval_x), float(interval_y), float(interval_z)],
            }
        else:
            center = App.Vector(float(center_x), float(center_y), float(center_z))
            array_obj = Draft.make_polar_array(
                base,
                int(polar_count),
                float(polar_angle),
                center,
                use_link=bool(use_link),
            )
            metadata = {
                "array_type": "polar",
                "count": int(polar_count),
                "angle": float(polar_angle),
                "center": [float(center_x), float(center_y), float(center_z)],
            }
        array_obj.Label = label
        doc = App.ActiveDocument
        if doc is not None:
            doc.recompute()
        metadata.update(
            {
                "object": array_obj.Name,
                "label": array_obj.Label,
                "type": getattr(array_obj, "TypeId", ""),
                "base": base.Name,
                "use_link": bool(use_link),
            }
        )
        return metadata

    transaction = run_freecad_transaction(
        f"Create Draft {kind} array: {object_name}",
        _create,
    )
    return {"ok": bool(transaction.get("ok")), "transaction": transaction, "draft": domain_runtime.draft_summary(service)}
