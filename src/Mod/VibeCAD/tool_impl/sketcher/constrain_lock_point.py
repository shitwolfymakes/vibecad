# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed native Sketcher lock-point constraint tool."""

from __future__ import annotations

from typing import Any

from . import add_constraint
from .constrain_common import optional_point_position


TOOL_SPEC = {
    "name": "sketcher.constrain_lock_point",
    "description": "Lock one Sketcher point role to exact sketch coordinates using native DistanceX and DistanceY constraints.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "geometry": {"type": "integer"},
            "geometry_handle": {"type": "string"},
            "point": {"type": "string", "enum": ["start", "end", "center", "midpoint", "origin"]},
            "x": {"type": "number"},
            "y": {"type": "number"},
        },
        "required": ["point", "x", "y"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    geometry: int | None = None,
    geometry_handle: str | None = None,
    point: str | None = "start",
    x: float = 0.0,
    y: float = 0.0,
) -> dict[str, Any]:
    return add_constraint.run(
        service,
        sketch_name=sketch_name,
        constraint_type="Lock",
        first_geometry=geometry,
        first_geometry_handle=geometry_handle,
        first_pos=optional_point_position(point, geometry_handle, "start"),
        x=float(x),
        y=float(y),
    )
