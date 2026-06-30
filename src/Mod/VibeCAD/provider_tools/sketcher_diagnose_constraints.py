# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``sketcher.diagnose_constraints``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "sketcher.diagnose_constraints"
FUNCTION_NAME = "sketcher_diagnose_constraints"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
