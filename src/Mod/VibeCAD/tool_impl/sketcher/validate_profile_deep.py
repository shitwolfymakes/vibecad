# SPDX-License-Identifier: LGPL-2.1-or-later

"""Deep profile diagnostics for native Sketcher geometry."""

from __future__ import annotations

from .common import get_sketch, profile_validation_deep


TOOL_SPEC = {
    "name": "sketcher.validate_profile_deep",
    "description": (
        "Inspect a Sketcher profile with exact FreeCAD shape state plus explicit endpoint graph, "
        "open node, duplicate edge, self-intersection, component, wire, face, and feature-readiness diagnostics."
    ),
    "safety": "READ",
    "workbench": "SketcherWorkbench",
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {
                "type": "string",
                "description": "Sketch object name or label. Uses the active edit sketch when omitted.",
            },
            "tolerance": {
                "type": "number",
                "default": 0.000001,
                "description": "Coordinate tolerance in millimeters for endpoint graph checks.",
            },
        },
    },
}


def run(service, sketch_name: str | None = None, tolerance: float = 0.000001):
    sketch = get_sketch(service, sketch_name)
    return profile_validation_deep(service, sketch, float(tolerance))
