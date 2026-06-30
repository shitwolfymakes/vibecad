# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``robot.get_objects``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "robot.get_objects"
FUNCTION_NAME = "robot_get_objects"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
