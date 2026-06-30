# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``sketcher.list_constraints``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "sketcher.list_constraints"
FUNCTION_NAME = "sketcher_list_constraints"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
