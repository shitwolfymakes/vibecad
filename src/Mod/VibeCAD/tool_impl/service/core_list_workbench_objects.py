# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``core.list_workbench_objects``."""

from __future__ import annotations

from VibeCADWorkbenchTools import get_tool_pack


TOOL_SPEC = {'contextual': True,
 'description': 'Return active-document objects matching a VibeCAD workbench tool '
                'pack.',
 'name': 'core.list_workbench_objects',
 'parameters': {'properties': {'workbench': {'description': 'Optional workbench name. '
                                                            'Defaults to the active '
                                                            'workbench.',
                                             'type': 'string'}},
                'type': 'object'},
 'safety': 'READ'}


def run(service, **kwargs):
    active = kwargs.get("workbench") or _active_workbench_name()
    pack = get_tool_pack(active)
    doc = service._active_document()
    objects = []
    if doc is not None and pack is not None:
        objects = [
            service._document_object_summary(obj)
            for obj in doc.Objects
            if service._object_matches_pack(obj, pack)
        ]
    visible, bounds = _bounded_items(objects, 40)
    return {
        "active_workbench": active,
        "tool_pack": pack.workbench if pack else None,
        "object_count": len(objects),
        "object_limit": bounds["limit"],
        "objects_truncated": bounds["truncated"],
        "objects_omitted": bounds["omitted"],
        "objects": visible,
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


def _bounded_items(items, limit):
    safe_limit = max(0, int(limit))
    visible = list(items[:safe_limit])
    omitted = max(0, len(items) - len(visible))
    return visible, {
        "limit": safe_limit,
        "truncated": omitted > 0,
        "omitted": omitted,
    }
