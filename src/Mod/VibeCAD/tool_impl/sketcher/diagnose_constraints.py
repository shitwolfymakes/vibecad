# SPDX-License-Identifier: LGPL-2.1-or-later

"""Constraint diagnostics for native Sketcher geometry."""

from __future__ import annotations

from .common import constraint_diagnostics, get_sketch


TOOL_SPEC = {
    "name": "sketcher.diagnose_constraints",
    "description": (
        "Inspect Sketcher solver state, conflicting and redundant constraints, per-geometry constraint coverage, "
        "and actionable next checks for under-constrained or invalid profiles."
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
                "description": "Coordinate tolerance in millimeters for profile diagnostics.",
            },
        },
    },
}


def run(service, sketch_name: str | None = None, tolerance: float = 0.000001):
    sketch = get_sketch(service, sketch_name)
    return constraint_diagnostics(service, sketch, float(tolerance))
