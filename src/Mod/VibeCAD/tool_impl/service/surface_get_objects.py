# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``surface.get_objects``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return Surface workbench Filling, GeomFillSurface, Sections, and '
                'related feature objects from the active document.',
 'name': 'surface.get_objects',
 'safety': 'READ',
 'workbench': 'SurfaceWorkbench'}


def run(service, **kwargs):
    objects = [service._surface_object_summary(obj) for obj in service._surface_objects()]
    return {"object_count": len(objects), "objects": objects}
