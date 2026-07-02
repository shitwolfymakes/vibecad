# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``phase.get_project_context``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "phase.get_project_context"
FUNCTION_NAME = "phase_get_project_context"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
