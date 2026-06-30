# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed native Sketcher point-on-object constraint tool."""

from __future__ import annotations

from typing import Any

from . import add_constraint
from .constrain_common import point_position


TOOL_SPEC = {
    "name": "sketcher.constrain_point_on_object",
    "description": "Add a native Sketcher PointOnObject constraint between one point role and one geometry element.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "point_geometry": {"type": "integer"},
            "point_geometry_handle": {"type": "string"},
            "point": {"type": "string", "enum": ["start", "end", "center", "midpoint", "origin"]},
            "object_geometry": {"type": "integer"},
            "object_geometry_handle": {"type": "string"},
        },
        "required": ["point"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    point_geometry: int | None = None,
    point_geometry_handle: str | None = None,
    point: str = "start",
    object_geometry: int | None = None,
    object_geometry_handle: str | None = None,
) -> dict[str, Any]:
    return add_constraint.run(
        service,
        sketch_name=sketch_name,
        constraint_type="PointOnObject",
        first_geometry=point_geometry,
        first_geometry_handle=point_geometry_handle,
        first_pos=point_position(point),
        second_geometry=object_geometry,
        second_geometry_handle=object_geometry_handle,
    )
