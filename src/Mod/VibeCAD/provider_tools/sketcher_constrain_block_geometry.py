# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``sketcher.constrain_block_geometry``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "sketcher.constrain_block_geometry"
FUNCTION_NAME = "sketcher_constrain_block_geometry"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
