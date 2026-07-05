# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``core.undo_last_vibecad_action``."""

from __future__ import annotations


TOOL_SPEC = {'description': 'Undo the most recent applied VibeCAD action via the document undo '
                'stack; for removing a specific older object use core.delete_object.',
 'name': 'core.undo_last_vibecad_action',
 'safety': 'WRITE'}


def run(service, **kwargs):
    action = service.approvals.last_applied()
    if action is None:
        return {
            "id": None,
            "status": "missing",
            "ok": False,
            "error": "No applied VibeCAD action is available to undo.",
        }
    try:
        import FreeCAD as App
    except Exception as exc:
        result = {"ok": False, "error": f"FreeCAD unavailable: {exc}"}
        return service.approvals.record_undo(action["id"], action.get("title", "VibeCAD action"), result)

    doc = App.ActiveDocument
    if doc is None or not hasattr(doc, "undo"):
        result = {"ok": False, "error": "No active FreeCAD document can be undone."}
    else:
        try:
            doc.undo()
            if hasattr(doc, "recompute"):
                doc.recompute()
            result = {
                "ok": True,
                "undone_action_id": action["id"],
                "document": getattr(doc, "Name", None),
            }
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
    return service.approvals.record_undo(action["id"], action.get("title", "VibeCAD action"), result)
