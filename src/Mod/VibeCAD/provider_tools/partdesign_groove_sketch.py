# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``partdesign.groove_sketch``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "partdesign.groove_sketch"
FUNCTION_NAME = "partdesign_groove_sketch"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
