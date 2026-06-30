# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``inspection.get_objects``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return Inspection groups/features and inspection-capable Part, Mesh, '
                'and Points geometry.',
 'name': 'inspection.get_objects',
 'safety': 'READ',
 'workbench': 'InspectionWorkbench'}


def run(service, **kwargs):
    features = [service._inspection_feature_summary(obj) for obj in service._inspection_features()]
    candidates = [service._document_object_summary(obj) for obj in service._inspection_candidates()]
    return {
        "feature_count": len(features),
        "features": features,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
