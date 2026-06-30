# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``openscad.get_objects``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "openscad.get_objects"
FUNCTION_NAME = "openscad_get_objects"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
