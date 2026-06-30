# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``mesh.get_objects``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return Mesh workbench objects with mesh point, edge, facet, and '
                'bounding-box counts.',
 'name': 'mesh.get_objects',
 'safety': 'READ',
 'workbench': 'MeshWorkbench'}


def run(service, **kwargs):
    objects = [service._mesh_object_summary(obj) for obj in service._mesh_objects()]
    return {"object_count": len(objects), "objects": objects}
