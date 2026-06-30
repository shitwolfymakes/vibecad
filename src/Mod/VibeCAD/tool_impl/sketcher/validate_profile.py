# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher profile validation tool."""

from __future__ import annotations

from typing import Any

from .common import get_sketch, no_sketch, profile_validation


TOOL_SPEC = {
    "name": "sketcher.validate_profile",
    "description": "Validate whether a Sketcher sketch has a closed pad/pocket-ready profile, reporting open endpoints, edge/face counts, construction counts, and profile status.",
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
    result = profile_validation(service, sketch)
    result["ok"] = True
    return result
