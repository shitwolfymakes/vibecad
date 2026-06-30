# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``sketcher.add_circle``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "sketcher.add_circle"
FUNCTION_NAME = "sketcher_add_circle"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
