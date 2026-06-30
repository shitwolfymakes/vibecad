# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed native Sketcher equal constraint tool."""

from __future__ import annotations

from typing import Any

from . import add_constraint


TOOL_SPEC = {
    "name": "sketcher.constrain_equal",
    "description": "Add a native Sketcher Equal constraint between two geometry elements.",
    "contextual": True,
    "parameters": {
        "type": "object",
        "properties": {
            "sketch_name": {"type": "string"},
            "first_geometry": {"type": "integer"},
            "first_geometry_handle": {"type": "string"},
            "second_geometry": {"type": "integer"},
            "second_geometry_handle": {"type": "string"},
        },
    },
}


def run(
    service: Any,
    sketch_name: str | None = None,
    first_geometry: int | None = None,
    first_geometry_handle: str | None = None,
    second_geometry: int | None = None,
    second_geometry_handle: str | None = None,
) -> dict[str, Any]:
    return add_constraint.run(
        service,
        sketch_name=sketch_name,
        constraint_type="Equal",
        first_geometry=first_geometry,
        first_geometry_handle=first_geometry_handle,
        second_geometry=second_geometry,
        second_geometry_handle=second_geometry_handle,
    )
