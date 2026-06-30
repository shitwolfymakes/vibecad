# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed native Sketcher horizontal distance constraint tool."""

from __future__ import annotations

from typing import Any

from . import add_constraint
from .constrain_common import point_position


TOOL_SPEC = {
    "name": "sketcher.constrain_distance_x",
    "description": "Add a native Sketcher DistanceX dimension between two point roles or from one point role to the sketch Y axis.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "first_geometry": {"type": "integer"},
            "first_geometry_handle": {"type": "string"},
            "first_point": {"type": "string", "enum": ["start", "end", "center", "midpoint"]},
            "second_geometry": {"type": "integer"},
            "second_geometry_handle": {"type": "string"},
            "second_point": {"type": "string", "enum": ["start", "end", "center", "midpoint"]},
            "value": {"type": "number"},
        },
        "required": ["first_point", "value"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    first_geometry: int | None = None,
    first_geometry_handle: str | None = None,
    first_point: str = "start",
    second_geometry: int | None = None,
    second_geometry_handle: str | None = None,
    second_point: str | None = None,
    value: float = 0.0,
) -> dict[str, Any]:
    kwargs = {
        "sketch_name": sketch_name,
        "constraint_type": "DistanceX",
        "first_geometry": first_geometry,
        "first_geometry_handle": first_geometry_handle,
        "first_pos": point_position(first_point),
        "value": float(value),
    }
    if second_geometry is not None or second_geometry_handle:
        kwargs["second_geometry"] = second_geometry
        kwargs["second_geometry_handle"] = second_geometry_handle
        kwargs["second_pos"] = point_position(second_point or "start")
    return add_constraint.run(service, **kwargs)
