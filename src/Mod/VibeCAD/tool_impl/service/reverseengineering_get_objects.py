# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``reverseengineering.get_objects``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return ReverseEngineering point/mesh candidates and reconstruction '
                'outputs from the active document.',
 'name': 'reverseengineering.get_objects',
 'safety': 'READ',
 'workbench': 'ReverseEngineeringWorkbench'}


def run(service, **kwargs):
    doc = service._active_document()
    if doc is None:
        return {"candidate_count": 0, "output_count": 0, "candidates": [], "outputs": []}
    candidates = [
        service._reverseengineering_object_summary(obj)
        for obj in doc.Objects
        if service._is_reverseengineering_candidate(obj)
    ]
    outputs = [
        service._reverseengineering_object_summary(obj)
        for obj in doc.Objects
        if service._is_reverseengineering_output(obj)
    ]
    return {"candidate_count": len(candidates), "output_count": len(outputs), "candidates": candidates, "outputs": outputs}
