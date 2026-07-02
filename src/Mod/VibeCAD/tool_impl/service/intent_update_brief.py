# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``intent.update_brief``."""

from __future__ import annotations


TOOL_SPEC = {
    "description": (
        "Create or update the VibeCAD intent brief. This writes the human "
        "brief markdown and machine brief JSON used by later phases. It must be "
        "used during Intent/Briefing before CAD geometry tools are exposed."
    ),
    "name": "intent.update_brief",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short project title."},
            "summary": {
                "type": "string",
                "description": "Concise natural-language design intent summary.",
            },
            "requirements": {
                "type": "object",
                "description": (
                    "Machine-readable requirement fields. Preferred keys: "
                    "purpose, critical_dimensions, interfaces, loads, "
                    "materials_process, tolerances, environment, "
                    "acceptance_criteria."
                ),
                "additionalProperties": True,
            },
            "assumptions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Explicit assumptions made because the user did not specify them.",
            },
            "open_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Targeted questions that must be answered before quality CAD work can start.",
            },
            "acceptance_criteria": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concrete checks that later phases must satisfy.",
            },
            "readiness_score": {
                "type": "number",
                "description": "0-100 estimate of readiness for the next phase.",
            },
            "ready_for_next_phase": {
                "type": "boolean",
                "description": "True if the brief is clear enough to continue into CAD work.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Search tags for the local project index.",
            },
        },
        "required": ["summary", "requirements"],
    },
    "safety": "SAFE_WRITE",
}


def run(
    service,
    title: str = "",
    summary: str = "",
    requirements: dict | None = None,
    assumptions: list[str] | None = None,
    open_questions: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    readiness_score: float | None = None,
    ready_for_next_phase: bool | None = None,
    tags: list[str] | None = None,
) -> dict[str, object]:
    return service.update_intent_brief(
        title=title,
        summary=summary,
        requirements=requirements or {},
        assumptions=assumptions,
        open_questions=open_questions,
        acceptance_criteria=acceptance_criteria,
        readiness_score=readiness_score,
        ready_for_next_phase=ready_for_next_phase,
        tags=tags,
    )
