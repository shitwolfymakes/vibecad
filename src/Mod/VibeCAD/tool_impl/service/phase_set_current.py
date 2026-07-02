# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``phase.set_current``."""

from __future__ import annotations


TOOL_SPEC = {
    "description": (
        "Request a VibeCAD workflow phase change. This changes the project "
        "phase contract and therefore the AI-visible tool surface; it does not "
        "create or modify CAD geometry."
    ),
    "name": "phase.set_current",
    "parameters": {
        "type": "object",
        "properties": {
            "phase": {
                "type": "string",
                "description": "Target phase: intent, design, assembly, analysis, or manufacturing.",
            },
            "reason": {
                "type": "string",
                "description": "Why this phase is the right next workflow phase.",
            },
        },
        "required": ["phase"],
    },
    "safety": "SAFE_WRITE",
}


def run(service, phase: str, reason: str = "") -> dict[str, object]:
    return service.set_phase(phase, reason=reason, requested_by="ai")
