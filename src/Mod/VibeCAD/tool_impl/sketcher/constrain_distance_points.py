# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed native Sketcher point-to-point distance constraint tool."""

from __future__ import annotations

from typing import Any

from . import add_constraint
from .constrain_common import optional_point_position


TOOL_SPEC = {
    "name": "sketcher.constrain_distance_points",
    "description": (
        "Add a native Sketcher Distance dimension between two semantic point targets. "
        "Targets accept geometry handles such as geometry:0, name:edge, origin, axis:H, axis:V, or external:0."
    ),
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "first_geometry": {"type": "integer"},
            "first_geometry_handle": {"type": "string"},
            "first_point": {"type": "string", "enum": ["start", "end", "center", "midpoint", "origin"]},
            "second_geometry": {"type": "integer"},
            "second_geometry_handle": {"type": "string"},
            "second_point": {"type": "string", "enum": ["start", "end", "center", "midpoint", "origin"]},
            "value": {"type": "number"},
        },
        "required": ["value"],
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
    value: float = 1.0,
) -> dict[str, Any]:
    return add_constraint.run(
        service,
        sketch_name=sketch_name,
        constraint_type="Distance",
        first_geometry=first_geometry,
        first_geometry_handle=first_geometry_handle,
        first_pos=optional_point_position(first_point, first_geometry_handle, "start"),
        second_geometry=second_geometry,
        second_geometry_handle=second_geometry_handle,
        second_pos=optional_point_position(second_point, second_geometry_handle, "start"),
        value=float(value),
    )
