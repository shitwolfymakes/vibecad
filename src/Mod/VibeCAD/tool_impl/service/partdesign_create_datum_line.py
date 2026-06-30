# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.create_datum_line``."""

from __future__ import annotations

from typing import Any

from . import domain_runtime
from VibeCADTransactions import run_freecad_transaction


TOOL_SPEC = {'contextual': True,
 'description': 'Create a native PartDesign Datum Line in a Body from a Body origin '
                'axis reference.',
 'name': 'partdesign.create_datum_line',
 'parameters': {'properties': {'body_name': {'description': 'Optional target Body internal name or visible label.',
                                              'type': 'string'},
                               'label': {'type': 'string'},
                               'map_mode': {'description': 'Native attachment map mode.',
                                            'type': 'string'},
                               'support_axis': {'enum': ['X_Axis', 'Y_Axis', 'Z_Axis'],
                                                'type': 'string'}},
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartDesignWorkbench'}


def run(
    service,
    label: str = "VibeCAD Datum Line",
    support_axis: str = "Z_Axis",
    map_mode: str = "TwoPointLine",
    body_name: str | None = None,
) -> dict[str, Any]:
    requested_support = str(support_axis or "Z_Axis")
    if requested_support not in {"X_Axis", "Y_Axis", "Z_Axis"}:
        return {"ok": False, "error": "support_axis must be X_Axis, Y_Axis, or Z_Axis."}

    def _create() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active document.")
        body = service._get_partdesign_body(body_name) if body_name else service._get_partdesign_body()
        if body is None:
            raise RuntimeError("No PartDesign Body found for datum line.")
        support = service._partdesign_origin_feature(body, requested_support)
        if support is None:
            raise RuntimeError(f"Body origin axis not found: {requested_support}")
        datum = doc.addObject("PartDesign::Line", "VibeCAD_DatumLine")
        datum.Label = label or "VibeCAD Datum Line"
        datum.AttachmentSupport = [(support, "")]
        datum.MapMode = str(map_mode or "TwoPointLine")
        body.addObject(datum)
        doc.recompute()
        return {
            "document": doc.Name,
            "body": body.Name,
            "datum": datum.Name,
            "label": getattr(datum, "Label", datum.Name),
            "type": getattr(datum, "TypeId", ""),
            "support_axis": requested_support,
            "map_mode": getattr(datum, "MapMode", None),
            "shape": domain_runtime.shape_summary(datum),
        }

    transaction = run_freecad_transaction(
        f"Create PartDesign datum line on {requested_support}",
        _create,
    )
    result = transaction.get("result", {}) if isinstance(transaction.get("result"), dict) else {}
    return {
        "ok": bool(transaction.get("ok")),
        **({"error": transaction.get("error"), "recoverable": True} if not transaction.get("ok") else {}),
        "transaction": transaction,
        "datum": result.get("datum"),
        "partdesign": domain_runtime.partdesign_summary(service),
    }
