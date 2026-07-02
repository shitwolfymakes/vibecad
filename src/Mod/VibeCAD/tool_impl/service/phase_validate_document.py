# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``phase.validate_document``."""

from __future__ import annotations


TOOL_SPEC = {
    "description": (
        "Inspect the current FreeCAD document against the active VibeCAD phase "
        "gates. This is a verifier, not a completion claim."
    ),
    "name": "phase.validate_document",
    "parameters": {
        "type": "object",
        "properties": {
            "phase": {
                "type": "string",
                "description": "Optional phase to validate. Defaults to the active project phase.",
            }
        },
        "additionalProperties": False,
    },
    "safety": "READ",
}


def run(service, phase: str = "") -> dict[str, object]:
    return service.validate_phase_document(phase or None)
