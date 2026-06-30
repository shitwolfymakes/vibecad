# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``mesh.get_objects``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "mesh.get_objects"
FUNCTION_NAME = "mesh_get_objects"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
