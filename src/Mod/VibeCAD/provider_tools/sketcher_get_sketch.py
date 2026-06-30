# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``sketcher.get_sketch``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "sketcher.get_sketch"
FUNCTION_NAME = "sketcher_get_sketch"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
