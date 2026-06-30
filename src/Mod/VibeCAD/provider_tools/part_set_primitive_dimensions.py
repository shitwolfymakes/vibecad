# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``part.set_primitive_dimensions``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "part.set_primitive_dimensions"
FUNCTION_NAME = "part_set_primitive_dimensions"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
