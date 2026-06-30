# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.create_sketch``."""

from __future__ import annotations

from . import core_get_active_document, core_get_task_panel

TOOL_SPEC = {'contextual': True,
 'description': 'Create or reuse a PartDesign Body and create a Sketch attached to a '
                'default origin plane without opening the plane picker. Use XY_Plane '
                'unless the user explicitly asks for another plane.',
 'name': 'partdesign.create_sketch',
 'parameters': {'properties': {'body_name': {'description': 'Optional target PartDesign Body internal name or visible label returned by partdesign.create_body or partdesign.get_bodies.',
                                              'type': 'string'},
                               'label': {'type': 'string'},
                               'plane': {'enum': ['XY_Plane', 'XZ_Plane', 'YZ_Plane'],
                                         'type': 'string'}},
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartDesignWorkbench'}
from VibeCADTransactions import run_freecad_transaction


def run(
    service,
    label: str = "Sketch",
    plane: str = "XY_Plane",
    body_name: str | None = None,
) -> dict[str, Any]:
    requested_plane = str(plane or "XY_Plane")
    if requested_plane not in {"XY_Plane", "XZ_Plane", "YZ_Plane"}:
        return {
            "ok": False,
            "error": "Only default origin planes are supported: XY_Plane, XZ_Plane, YZ_Plane.",
        }

    def _create() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument or App.newDocument("VibeCAD")
        body = service._get_partdesign_body(body_name) if body_name else None
        if body_name and body is None:
            raise RuntimeError(f"PartDesign Body not found by name or label: {body_name}")
        if body is None:
            active = getattr(doc, "ActiveObject", None)
            if getattr(active, "TypeId", "") == "PartDesign::Body":
                body = active
        if body is None:
            bodies = [
                obj
                for obj in doc.Objects
                if getattr(obj, "TypeId", "") == "PartDesign::Body"
            ]
            body = bodies[0] if bodies else None
        if body is None:
            body = doc.addObject("PartDesign::Body", "Body")
            body.Label = "Body"

        origin = getattr(body, "Origin", None)
        features = list(getattr(origin, "OriginFeatures", []) or [])
        def _normalized_origin_name(item) -> str:
            name = str(getattr(item, "Name", ""))
            label = str(getattr(item, "Label", "")).replace("-", "_")
            for value in (name, label):
                for plane_name in ("XY_Plane", "XZ_Plane", "YZ_Plane"):
                    if value == plane_name or value.startswith(plane_name):
                        return plane_name
            return name or label

        support = next(
            (
                item
                for item in features
                if _normalized_origin_name(item) == requested_plane
            ),
            None,
        )
        if support is None:
            raise RuntimeError(f"Body origin plane not found: {requested_plane}")

        sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
        sketch.Label = label or "Sketch"
        body.addObject(sketch)
        sketch.AttachmentSupport = [(support, "")]
        sketch.MapMode = "FlatFace"
        doc.recompute()
        try:
            import FreeCADGui as Gui

            Gui.ActiveDocument.setEdit(sketch.Name)
            Gui.updateGui()
        except Exception:
            pass
        return {
            "document": doc.Name,
            "body": body.Name,
            "body_label": getattr(body, "Label", body.Name),
            "sketch": sketch.Name,
            "sketch_label": getattr(sketch, "Label", sketch.Name),
            "plane": requested_plane,
            "attachment_support": getattr(support, "Name", requested_plane),
            "active_workbench": _active_workbench_name(),
            "document_summary": core_get_active_document.run(service),
            "sketcher": service.sketcher_summary(sketch.Name),
            "active_sketch": sketch.Name,
            "profile_status": service._sketch_profile_status(sketch),
            "next_actions": service._sketch_next_actions(sketch),
            "task_panel": core_get_task_panel.run(service),
        }

    transaction = run_freecad_transaction(
        f"Create PartDesign sketch on {requested_plane}",
        _create,
    )
    return {
        "ok": bool(transaction.get("ok")),
        "transaction": transaction,
        "active_sketch": (
            transaction.get("result", {}).get("sketch")
            if isinstance(transaction.get("result"), dict)
            else None
        ),
        "next_action": "Add closed sketch geometry, then call partdesign.pad_sketch or partdesign.pocket_sketch.",
    }


def _active_workbench_name():
    try:
        import FreeCADGui as Gui

        workbench = Gui.activeWorkbench()
        if workbench:
            return workbench.name()
    except Exception:
        pass
    return None
