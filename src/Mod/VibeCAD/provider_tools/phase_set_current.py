# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``phase.set_current``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "phase.set_current"
FUNCTION_NAME = "phase_set_current"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
