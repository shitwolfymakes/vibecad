# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed native Sketcher vertical constraint tool."""

from __future__ import annotations

from typing import Any

from . import add_constraint


TOOL_SPEC = {
    "name": "sketcher.constrain_vertical",
    "description": "Add a native Sketcher Vertical constraint to one geometry element.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "geometry_index": {"type": "integer"},
            "geometry_handle": {"type": "string"},
        },
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    geometry_index: int | None = None,
    geometry_handle: str | None = None,
) -> dict[str, Any]:
    return add_constraint.run(
        service,
        sketch_name=sketch_name,
        constraint_type="Vertical",
        first_geometry=geometry_index,
        first_geometry_handle=geometry_handle,
    )
