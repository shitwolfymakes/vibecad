# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.create_body``."""

from __future__ import annotations

from . import domain_runtime
from VibeCADTransactions import run_freecad_transaction


TOOL_SPEC = {
    "contextual": True,
    "description": (
        "Create a native PartDesign Body for a separate component, equivalent "
        "to using the PartDesign body command before creating sketches/features."
    ),
    "name": "partdesign.create_body",
    "parameters": {
        "type": "object",
        "properties": {
            "label": {"type": "string"},
        },
    },
    "safety": "SAFE_WRITE",
    "workbench": "PartDesignWorkbench",
}


def run(service, label: str = "Body") -> dict[str, Any]:
    def _create_body() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument or App.newDocument("VibeCAD")
        body = doc.addObject("PartDesign::Body", "Body")
        body.Label = label or "Body"
        try:
            doc.setActiveObject("pdbody", body)
        except Exception:
            pass
        doc.recompute()
        return {
            "document": doc.Name,
            "body": body.Name,
            "body_label": getattr(body, "Label", body.Name),
            "partdesign": domain_runtime.partdesign_summary(service, body.Name),
        }

    transaction = run_freecad_transaction(
        f"Create PartDesign body: {label or 'Body'}",
        _create_body,
    )
    result = transaction.get("result") if isinstance(transaction.get("result"), dict) else {}
    response = {
        "ok": bool(transaction.get("ok")),
        "transaction": transaction,
        "active_body": result.get("body"),
        "active_body_label": result.get("body_label"),
        "partdesign": domain_runtime.partdesign_summary(service, result.get("body")),
        "next_action": "Create a sketch in this Body, then add constrained geometry and native PartDesign features.",
    }
    if not response["ok"]:
        response["error"] = transaction.get("error") or "PartDesign Body creation failed."
        response["recoverable"] = True
    return response
