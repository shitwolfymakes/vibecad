# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher sketch inspection tool."""

from __future__ import annotations

from typing import Any


TOOL_SPEC = {
    "name": "sketcher.get_sketch",
    "description": "Return geometry and constraint details for a Sketcher sketch.",
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
    return service.sketcher_summary(sketch_name)
