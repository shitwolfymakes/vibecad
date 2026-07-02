# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``phase.audit_workflow``."""

from __future__ import annotations


TOOL_SPEC = {
    "description": (
        "Audit the phase-native VibeCAD provider workflow. This verifies that "
        "intent, planner, workspace, wrong-phase, document lifecycle, and "
        "modify-existing request tool boundaries match the production contract."
    ),
    "name": "phase.audit_workflow",
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "safety": "READ",
}


def run(service) -> dict[str, object]:
    return service.phase_workflow_audit()
