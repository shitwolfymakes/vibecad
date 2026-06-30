# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed native Sketcher block constraint tool."""

from __future__ import annotations

from typing import Any

from . import add_constraint


TOOL_SPEC = {
    "name": "sketcher.constrain_block_geometry",
    "description": "Add a native Sketcher Block constraint to one geometry handle, equivalent to blocking selected geometry.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "geometry": {"type": "integer"},
            "geometry_handle": {"type": "string"},
        },
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    geometry: int | None = None,
    geometry_handle: str | None = None,
) -> dict[str, Any]:
    return add_constraint.run(
        service,
        sketch_name=sketch_name,
        constraint_type="Block",
        first_geometry=geometry,
        first_geometry_handle=geometry_handle,
    )
