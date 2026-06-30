# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``meshpart.get_objects``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return MeshPart tessellation candidates and mesh outputs from the '
                'active document.',
 'name': 'meshpart.get_objects',
 'safety': 'READ',
 'workbench': 'MeshPartWorkbench'}


def run(service, **kwargs):
    doc = service._active_document()
    if doc is None:
        return {
            "document": None,
            "part_candidate_count": 0,
            "mesh_count": 0,
            "part_candidates": [],
            "meshes": [],
        }
    part_candidates = [
        service._part_object_summary(obj)
        for obj in doc.Objects
        if service._is_meshpart_part_candidate(obj)
    ]
    meshes = [
        service._mesh_object_summary(obj)
        for obj in doc.Objects
        if service._is_meshpart_mesh_output(obj)
    ]
    return {
        "document": doc.Name,
        "part_candidate_count": len(part_candidates),
        "mesh_count": len(meshes),
        "part_candidates": part_candidates[:80],
        "meshes": meshes[:80],
    }
