# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed native Sketcher angle constraint tool."""

from __future__ import annotations

from typing import Any

from . import add_constraint
from .constrain_common import optional_point_position


TOOL_SPEC = {
    "name": "sketcher.constrain_angle_between",
    "description": "Add a native Sketcher Angle constraint to one curve or between two semantic curve/point targets.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "first_geometry": {"type": "integer"},
            "first_geometry_handle": {"type": "string"},
            "first_point": {"type": "string", "enum": ["whole", "start", "end", "center", "midpoint"]},
            "second_geometry": {"type": "integer"},
            "second_geometry_handle": {"type": "string"},
            "second_point": {"type": "string", "enum": ["whole", "start", "end", "center", "midpoint"]},
            "angle_degrees": {"type": "number"},
        },
        "required": ["angle_degrees"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    first_geometry: int | None = None,
    first_geometry_handle: str | None = None,
    first_point: str | None = None,
    second_geometry: int | None = None,
    second_geometry_handle: str | None = None,
    second_point: str | None = None,
    angle_degrees: float = 90.0,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "sketch_name": sketch_name,
        "constraint_type": "Angle",
        "first_geometry": first_geometry,
        "first_geometry_handle": first_geometry_handle,
        "value": float(angle_degrees),
    }
    if first_point is not None or second_geometry is not None or second_geometry_handle:
        kwargs["first_pos"] = optional_point_position(first_point, first_geometry_handle, "whole")
    if second_geometry is not None or second_geometry_handle:
        kwargs["second_geometry"] = second_geometry
        kwargs["second_geometry_handle"] = second_geometry_handle
        kwargs["second_pos"] = optional_point_position(second_point, second_geometry_handle, "whole")
    return add_constraint.run(service, **kwargs)
