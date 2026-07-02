# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``phase.validate_document``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "phase.validate_document"
FUNCTION_NAME = "phase_validate_document"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
