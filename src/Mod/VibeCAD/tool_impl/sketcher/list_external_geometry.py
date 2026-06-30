# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native Sketcher external-geometry inspection tool."""

from __future__ import annotations

from typing import Any

from .common import external_geometry_summary, get_sketch, no_sketch


TOOL_SPEC = {
    "name": "sketcher.list_external_geometry",
    "description": "List external geometry references currently imported into a native Sketcher sketch.",
    "safety": "READ",
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
        },
    },
}


def run(service: Any, sketch_name: str | None = None) -> dict[str, Any]:
    sketch = get_sketch(service, sketch_name)
    if sketch is None:
        return no_sketch(sketch_name)
    external = external_geometry_summary(sketch)
    return {
        "ok": True,
        "sketch": getattr(sketch, "Name", None),
        "external_geometry_count": len(external),
        "external_geometry": external,
    }
