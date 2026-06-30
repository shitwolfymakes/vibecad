# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``bim.get_objects``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return BIM/Arch objects, IFC type metadata, and local grouping '
                'relationships from the active document.',
 'name': 'bim.get_objects',
 'safety': 'READ',
 'workbench': 'BIMWorkbench'}


def run(service, **kwargs):
    objects = [service._bim_object_summary(obj) for obj in service._bim_objects()]
    return {"object_count": len(objects), "objects": objects}
