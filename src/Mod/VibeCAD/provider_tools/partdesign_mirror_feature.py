# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``partdesign.mirror_feature``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "partdesign.mirror_feature"
FUNCTION_NAME = "partdesign_mirror_feature"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
