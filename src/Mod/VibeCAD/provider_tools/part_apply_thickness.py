# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``part.apply_thickness``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "part.apply_thickness"
FUNCTION_NAME = "part_apply_thickness"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
