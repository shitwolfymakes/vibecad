# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``draft.get_objects``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return Draft-owned 2D objects from the active document.',
 'name': 'draft.get_objects',
 'safety': 'READ',
 'workbench': 'DraftWorkbench'}


def run(service, **kwargs):
    objects = [service._draft_object_summary(obj) for obj in service._draft_objects()]
    return {"object_count": len(objects), "objects": objects}
