# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``core.activate_workbench``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "core.activate_workbench"
FUNCTION_NAME = "core_activate_workbench"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
