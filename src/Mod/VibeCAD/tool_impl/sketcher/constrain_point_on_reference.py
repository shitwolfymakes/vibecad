# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed native Sketcher point-on-reference constraint tool."""

from __future__ import annotations

from typing import Any

from . import add_constraint
from .constrain_common import optional_point_position


TOOL_SPEC = {
    "name": "sketcher.constrain_point_on_reference",
    "description": (
        "Add a native Sketcher PointOnObject constraint from a semantic point target to a curve/reference "
        "handle such as name:edge, geometry:0, axis:H, axis:V, or external:0."
    ),
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "point_geometry": {"type": "integer"},
            "point_geometry_handle": {"type": "string"},
            "point": {"type": "string", "enum": ["start", "end", "center", "midpoint", "origin"]},
            "reference_geometry": {"type": "integer"},
            "reference_geometry_handle": {"type": "string"},
        },
        "required": ["point"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    point_geometry: int | None = None,
    point_geometry_handle: str | None = None,
    point: str | None = "start",
    reference_geometry: int | None = None,
    reference_geometry_handle: str | None = None,
) -> dict[str, Any]:
    return add_constraint.run(
        service,
        sketch_name=sketch_name,
        constraint_type="PointOnObject",
        first_geometry=point_geometry,
        first_geometry_handle=point_geometry_handle,
        first_pos=optional_point_position(point, point_geometry_handle, "start"),
        second_geometry=reference_geometry,
        second_geometry_handle=reference_geometry_handle,
    )
