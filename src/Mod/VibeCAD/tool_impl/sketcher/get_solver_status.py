# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher solver-status inspection tool."""

from __future__ import annotations

from typing import Any

from .common import get_sketch, no_sketch, solver_status


TOOL_SPEC = {
    "name": "sketcher.get_solver_status",
    "description": "Return Sketcher solver state, degrees of freedom, constraint counts, and conflict/redundancy lists when available.",
    "safety": "READ",
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {
                "type": "string",
                "description": "Sketch object name or label. Defaults to the first sketch.",
            },
        },
    },
}


def run(service: Any, sketch_name: str | None = None) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return no_sketch(sketch_name)
    result = solver_status(service, sketch)
    result["ok"] = True
    return result
