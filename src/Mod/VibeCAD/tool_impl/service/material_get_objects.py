# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``material.get_objects``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return active-document objects that expose material or shape '
                'appearance state.',
 'name': 'material.get_objects',
 'safety': 'READ',
 'workbench': 'MaterialWorkbench'}


def run(service, **kwargs):
    objects = [service._material_object_summary(obj) for obj in service._material_capable_objects()]
    return {"object_count": len(objects), "objects": objects}
