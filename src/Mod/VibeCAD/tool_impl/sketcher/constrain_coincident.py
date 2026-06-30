# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed native Sketcher coincident constraint tool."""

from __future__ import annotations

from typing import Any

from . import add_constraint
from .constrain_common import point_position


TOOL_SPEC = {
    "name": "sketcher.constrain_coincident",
    "description": "Add a native Sketcher Coincident constraint using semantic point roles instead of raw point-position integers.",
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
        },
        "required": ["first_point", "second_point"],
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    first_geometry: int | None = None,
    first_geometry_handle: str | None = None,
    first_point: str = "end",
    second_geometry: int | None = None,
    second_geometry_handle: str | None = None,
    second_point: str = "start",
) -> dict[str, Any]:
    return add_constraint.run(
        service,
        sketch_name=sketch_name,
        constraint_type="Coincident",
        first_geometry=first_geometry,
        first_geometry_handle=first_geometry_handle,
        first_pos=point_position(first_point),
        second_geometry=second_geometry,
        second_geometry_handle=second_geometry_handle,
        second_pos=point_position(second_point),
    )
