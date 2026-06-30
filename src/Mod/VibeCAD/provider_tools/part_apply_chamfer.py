# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``part.apply_chamfer``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "part.apply_chamfer"
FUNCTION_NAME = "part_apply_chamfer"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
