# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``core.enter_workspace``."""

from __future__ import annotations


TOOL_SPEC = {
    "description": (
        "Explicitly enter a FreeCAD workspace/workbench for the next CAD operation. "
        "Use this from the small planning surface before asking VibeCAD to expose "
        "that workspace's full useful tool pack."
    ),
    "name": "core.enter_workspace",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Workbench name such as PartDesignWorkbench or SketcherWorkbench.",
            },
            "goal": {
                "type": "string",
                "description": "Short model-written goal for this workspace session.",
            },
            "reason": {
                "type": "string",
                "description": "Why this workspace is the right place for the next operation.",
            },
        },
        "required": ["name"],
    },
    "safety": "VIEW",
}


def run(service, name: str, goal: str = "", reason: str = "") -> dict[str, object]:
    from tool_impl.service.core_activate_workbench import run as activate_workbench
    from VibeCADWorkbenchTools import get_tool_pack

    phase_context = service.phase_context()
    phase = str(phase_context.get("active_phase") or "intent")
    allowed = set(service.phase_allowed_workbenches(phase))
    if phase == "intent" or (allowed and name not in allowed):
        return {
            "ok": False,
            "requested": name,
            "active_phase": phase,
            "allowed_workbenches": sorted(allowed),
            "error": (
                f"{name} is outside the current VibeCAD phase '{phase}'. "
                "Request or select the appropriate phase before entering this workspace."
            ),
            "recoverable": True,
            "required_next_action": {
                "tool": "phase.set_current",
                "arguments": {"phase": _phase_for_workbench(name), "reason": reason or goal},
                "why": "Workspace access is phase-scoped so each workflow has tuned tools and validators.",
            },
        }

    result = activate_workbench(service, name=name)
    active = result.get("active")
    if active is None:
        active = result.get("active_workbench")
    known_workspace = get_tool_pack(name) is not None
    ok = bool(result.get("activated")) or active == name or known_workspace
    response: dict[str, object] = {
        "ok": ok,
        "requested": name,
        "active_workbench": active or name,
        "workspace": active or name,
        "goal": str(goal or "").strip(),
        "reason": str(reason or "").strip(),
        "workspace_session": {
            "workbench": active or name,
            "goal": str(goal or "").strip(),
            "reason": str(reason or "").strip(),
        },
    }
    if result.get("error"):
        if ok:
            response["activation_warning"] = result["error"]
        else:
            response["error"] = result["error"]
            response["recoverable"] = True
    return response


def _phase_for_workbench(name: str) -> str:
    if name == "AssemblyWorkbench":
        return "assembly"
    if name == "FemWorkbench":
        return "analysis"
    if name == "CAMWorkbench":
        return "manufacturing"
    return "design"
