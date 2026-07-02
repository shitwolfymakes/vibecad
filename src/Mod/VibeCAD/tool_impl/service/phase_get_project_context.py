# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``phase.get_project_context``."""

from __future__ import annotations


TOOL_SPEC = {
    "description": (
        "Return the current VibeCAD project, active phase, intent brief, "
        "artifact paths, and phase success gates. Use this before deciding "
        "whether the current phase is ready for CAD authoring."
    ),
    "name": "phase.get_project_context",
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "safety": "READ",
}


def run(service) -> dict[str, object]:
    return service.phase_context()
