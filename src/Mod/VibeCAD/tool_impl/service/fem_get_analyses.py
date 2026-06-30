# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``fem.get_analyses``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return FEM analysis containers and their member categories from the '
                'active document.',
 'name': 'fem.get_analyses',
 'parameters': {'properties': {'analysis_name': {'description': 'FEM analysis object '
                                                                'name or label. '
                                                                'Defaults to the first '
                                                                'analysis.',
                                                 'type': 'string'}},
                'type': 'object'},
 'safety': 'READ',
 'workbench': 'FemWorkbench'}


def run(service, **kwargs):
    analysis_name = kwargs.get("analysis_name")
    analyses = service._fem_analyses()
    analysis = service._get_fem_analysis(analysis_name)
    return {
        "analysis_count": len(analyses),
        "analyses": [service._fem_analysis_summary(item) for item in analyses],
        "selected_analysis": service._fem_analysis_summary(analysis) if analysis else None,
    }
