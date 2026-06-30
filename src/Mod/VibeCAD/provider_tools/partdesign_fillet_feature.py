# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``partdesign.fillet_feature``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "partdesign.fillet_feature"
FUNCTION_NAME = "partdesign_fillet_feature"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
