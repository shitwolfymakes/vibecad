# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``part.get_objects``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return Part workbench objects, primitive dimensions, and shape counts '
                'from the active document.',
 'name': 'part.get_objects',
 'safety': 'READ',
 'workbench': 'PartWorkbench'}


def run(service, **kwargs):
    objects = [service._part_object_summary(obj) for obj in service._part_objects()]
    return {"object_count": len(objects), "objects": objects}
