# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``intent.update_brief``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "intent.update_brief"
FUNCTION_NAME = "intent_update_brief"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
