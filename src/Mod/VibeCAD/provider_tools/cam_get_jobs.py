# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider function tool for ``cam.get_jobs``."""

from __future__ import annotations

from .base import create_provider_tool


TOOL_NAME = "cam.get_jobs"
FUNCTION_NAME = "cam_get_jobs"


def create(schema, conn, FunctionTool):
    return create_provider_tool(TOOL_NAME, FUNCTION_NAME, schema, conn, FunctionTool)
