# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``partdesign.linear_pattern``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "partdesign.linear_pattern"
FUNCTION_NAME = "partdesign_linear_pattern"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
