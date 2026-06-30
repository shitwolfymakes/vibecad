# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``openscad.get_objects``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return OpenSCAD-relevant Part, Mesh, and OpenSCAD proxy objects plus '
                'OpenSCAD executable state.',
 'name': 'openscad.get_objects',
 'safety': 'READ',
 'workbench': 'OpenSCADWorkbench'}


def run(service, **kwargs):
    doc = service._active_document()
    objects = [service._openscad_object_summary(obj) for obj in doc.Objects] if doc else []
    return {"object_count": len(objects), "objects": objects}
