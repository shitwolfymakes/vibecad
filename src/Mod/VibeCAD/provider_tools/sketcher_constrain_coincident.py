# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``sketcher.constrain_coincident``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "sketcher.constrain_coincident"
FUNCTION_NAME = "sketcher_constrain_coincident"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
