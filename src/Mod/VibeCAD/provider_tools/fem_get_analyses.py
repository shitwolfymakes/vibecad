# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``fem.get_analyses``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "fem.get_analyses"
FUNCTION_NAME = "fem_get_analyses"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
