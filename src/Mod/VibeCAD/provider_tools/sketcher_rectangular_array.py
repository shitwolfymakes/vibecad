# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``sketcher.rectangular_array``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "sketcher.rectangular_array"
FUNCTION_NAME = "sketcher_rectangular_array"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
