# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``sketcher.get_constraint_by_name``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "sketcher.get_constraint_by_name"
FUNCTION_NAME = "sketcher_get_constraint_by_name"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
