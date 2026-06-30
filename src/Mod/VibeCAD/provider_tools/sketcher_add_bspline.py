# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``sketcher.add_bspline``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "sketcher.add_bspline"
FUNCTION_NAME = "sketcher_add_bspline"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
