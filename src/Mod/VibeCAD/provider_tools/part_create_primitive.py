# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``part.create_primitive``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "part.create_primitive"
FUNCTION_NAME = "part_create_primitive"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
