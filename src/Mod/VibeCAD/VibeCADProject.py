# SPDX-License-Identifier: LGPL-2.1-or-later

"""Project, phase, and intent-contract persistence for VibeCAD."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any


PROJECT_SCHEMA = "vibecad-project-v1"
BRIEF_SCHEMA = "vibecad-intent-brief-v1"
PHASE_ORDER = ("intent", "design", "assembly", "analysis", "manufacturing")

PHASE_SPECS: dict[str, dict[str, Any]] = {
    "intent": {
        "label": "Intent",
        "goal": "Understand the design contract before any geometry is created.",
        "allowed_workbenches": (),
        "requires_approved_intent": False,
        "success_gates": [
            "human-readable brief exists",
            "machine-readable brief exists",
            "critical missing questions are answered or explicitly assumed",
            "human approves the brief before CAD authoring starts",
        ],
    },
    "design": {
        "label": "Design",
        "goal": "Create robust editable part geometry from the approved intent.",
        "allowed_workbenches": (
            "PartDesignWorkbench",
            "SketcherWorkbench",
            "PartWorkbench",
            "DraftWorkbench",
            "MaterialWorkbench",
            "SurfaceWorkbench",
            "TechDrawWorkbench",
        ),
        "requires_approved_intent": True,
        "success_gates": [
            "approved intent contract is present",
            "valid FreeCAD solids exist where requested",
            "features are named and editable",
            "dimensions and interfaces match the intent contract",
            "viewport screenshot is captured after geometry changes",
        ],
    },
    "assembly": {
        "label": "Assembly",
        "goal": "Create native assemblies from real independently selectable components.",
        "allowed_workbenches": (
            "AssemblyWorkbench",
            "PartDesignWorkbench",
            "PartWorkbench",
            "MaterialWorkbench",
        ),
        "requires_approved_intent": True,
        "success_gates": [
            "native Assembly object exists",
            "multiple real component objects are added",
            "components remain independently selectable",
            "joints or placements express the assembly relationship",
            "the result is not a single fused assembly-themed body",
        ],
    },
    "analysis": {
        "label": "Analysis",
        "goal": "Set up and validate load cases, materials, mesh, and solver evidence.",
        "allowed_workbenches": (
            "FemWorkbench",
            "PartWorkbench",
            "PartDesignWorkbench",
            "MaterialWorkbench",
            "InspectionWorkbench",
        ),
        "requires_approved_intent": True,
        "success_gates": [
            "analysis references approved geometry",
            "materials are assigned",
            "loads and constraints are explicit",
            "mesh and solver state are inspectable",
            "reported results cite document evidence",
        ],
    },
    "manufacturing": {
        "label": "Manufacturing",
        "goal": "Prepare manufacturable CAM/process outputs from approved geometry.",
        "allowed_workbenches": (
            "CAMWorkbench",
            "PartWorkbench",
            "PartDesignWorkbench",
            "MaterialWorkbench",
            "TechDrawWorkbench",
        ),
        "requires_approved_intent": True,
        "success_gates": [
            "manufacturing phase references approved geometry",
            "stock/setup assumptions are explicit",
            "tools and operations are inspectable",
            "post-processing is separated from design intent",
        ],
    },
}

INTENT_REQUIREMENT_FIELDS: tuple[dict[str, str], ...] = (
    {"key": "purpose", "label": "Purpose"},
    {"key": "critical_dimensions", "label": "Critical dimensions/envelope"},
    {"key": "interfaces", "label": "Mounting and assembly interfaces"},
    {"key": "loads", "label": "Loads and duty cycle"},
    {"key": "materials_process", "label": "Material and process"},
    {"key": "tolerances", "label": "Tolerances and fit expectations"},
    {"key": "environment", "label": "Operating environment"},
    {"key": "acceptance_criteria", "label": "Acceptance criteria"},
)


def normalize_phase(value: str | None) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "brief": "intent",
        "briefing": "intent",
        "intent": "intent",
        "requirements": "intent",
        "part": "design",
        "parts": "design",
        "part_design": "design",
        "design": "design",
        "assembly": "assembly",
        "assemble": "assembly",
        "analysis": "analysis",
        "fea": "analysis",
        "fem": "analysis",
        "manufacturing": "manufacturing",
        "manufacture": "manufacturing",
        "cam": "manufacturing",
    }
    phase = aliases.get(text, text)
    if phase not in PHASE_SPECS:
        raise ValueError(
            "Unknown VibeCAD phase. Expected one of: " + ", ".join(PHASE_ORDER)
        )
    return phase


def phase_spec(phase: str | None) -> dict[str, Any]:
    return dict(PHASE_SPECS[normalize_phase(phase)])


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def slugify(value: str, fallback: str = "vibecad-project") -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("._")
    return slug[:80] or fallback


def _json_safe_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [values.strip()] if values.strip() else []
    if isinstance(values, (list, tuple)):
        return [str(item).strip() for item in values if str(item).strip()]
    return [str(values).strip()] if str(values).strip() else []


def _json_safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def _vibecad_home() -> Path:
    configured = str(os.environ.get("VIBECAD_HOME") or "").strip()
    if configured:
        return Path(configured).expanduser()
    try:
        return Path.home() / ".vibecad"
    except Exception:
        return Path.cwd() / ".vibecad"


def _default_index_path() -> Path:
    try:
        return _vibecad_home() / "index.sqlite"
    except Exception:
        return Path.cwd() / ".vibecad" / "index.sqlite"


def _active_document_info() -> dict[str, Any]:
    try:
        import FreeCAD as App
    except Exception:
        return {"document": None, "label": None, "file_path": None, "saved": False}

    doc = getattr(App, "ActiveDocument", None)
    if doc is None:
        return {"document": None, "label": None, "file_path": None, "saved": False}
    file_path = str(getattr(doc, "FileName", "") or "")
    return {
        "document": str(getattr(doc, "Name", "") or ""),
        "label": str(getattr(doc, "Label", "") or getattr(doc, "Name", "") or ""),
        "file_path": file_path or None,
        "saved": bool(file_path),
    }


def _project_id_for_scope(scope: dict[str, Any], session_id: str) -> str:
    file_path = scope.get("file_path")
    source = str(Path(str(file_path)).expanduser().resolve()) if file_path else session_id
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]


class VibeCADProjectStore:
    """Small durable project store for phase-native VibeCAD workflows."""

    def __init__(self, session_id: str, index_path: Path | None = None) -> None:
        self.session_id = str(session_id)
        self.index_path = index_path or _default_index_path()

    def project_scope(self) -> dict[str, Any]:
        doc = _active_document_info()
        project_id = _project_id_for_scope(doc, self.session_id)
        label = doc.get("label") or doc.get("document") or "Unsaved VibeCAD Project"
        if doc.get("file_path"):
            cad_path = Path(str(doc["file_path"])).expanduser()
            root = cad_path.parent / ".vibecad" / f"{slugify(cad_path.stem)}-{project_id[:8]}"
            persistent = True
        else:
            root = (
                _vibecad_home()
                / "projects"
                / f"{slugify(str(label))}-{project_id[:8]}"
            )
            persistent = True
        return {
            "project_id": project_id,
            "title": str(label),
            "root": str(root),
            "manifest_path": str(root / "project.vibecad.json"),
            "persistent": persistent,
            "document_saved": bool(doc.get("saved")),
            "document": doc,
            "index_path": str(self.index_path),
        }

    def load_manifest(self) -> dict[str, Any]:
        scope = self.project_scope()
        path = Path(str(scope["manifest_path"]))
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("schema") == PROJECT_SCHEMA:
                    return self._merge_manifest_defaults(data, scope)
            except Exception:
                pass
        return self._default_manifest(scope)

    def save_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        scope = self.project_scope()
        merged = self._merge_manifest_defaults(manifest, scope)
        merged["updated_at"] = now_iso()
        path = Path(str(scope["manifest_path"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
        self._update_index(merged, scope)
        return merged

    def context(self) -> dict[str, Any]:
        scope = self.project_scope()
        manifest = self.save_manifest(self.load_manifest())
        brief = self.latest_intent_brief()
        phase = normalize_phase(str(manifest.get("active_phase") or "intent"))
        spec = phase_spec(phase)
        readiness = self.intent_readiness(brief)
        return {
            "schema": "vibecad-project-context-v1",
            "project_id": manifest["project_id"],
            "title": manifest.get("title") or scope.get("title"),
            "root": scope["root"],
            "manifest_path": scope["manifest_path"],
            "index_path": scope["index_path"],
            "persistent": bool(scope.get("persistent")),
            "document_saved": bool(scope.get("document_saved")),
            "active_phase": phase,
            "phase": {
                "name": phase,
                "label": spec["label"],
                "goal": spec["goal"],
                "allowed_workbenches": list(spec["allowed_workbenches"]),
                "requires_approved_intent": bool(spec["requires_approved_intent"]),
                "success_gates": list(spec["success_gates"]),
            },
            "phases": manifest.get("phases", {}),
            "intent": {
                "approved": bool(manifest.get("intent", {}).get("approved")),
                "approved_intent_version": manifest.get("approved_intent_version"),
                "brief_path": str(self._intent_json_path()),
                "brief_markdown_path": str(self._intent_markdown_path()),
                "brief": brief,
                "readiness": readiness,
            },
            "document": scope.get("document", {}),
            "documents": manifest.get("documents", {}),
            "phase_transition_request": manifest.get("phase_transition_request"),
        }

    def set_phase(self, phase: str, reason: str = "", requested_by: str = "user") -> dict[str, Any]:
        normalized = normalize_phase(phase)
        manifest = self.load_manifest()
        previous = normalize_phase(str(manifest.get("active_phase") or "intent"))
        manifest["active_phase"] = normalized
        manifest.setdefault("phase_history", []).append(
            {
                "from": previous,
                "to": normalized,
                "reason": str(reason or "").strip(),
                "requested_by": str(requested_by or "user"),
                "timestamp": now_iso(),
            }
        )
        manifest.setdefault("phases", {}).setdefault(normalized, {})["status"] = "active"
        saved = self.save_manifest(manifest)
        return {
            "ok": True,
            "previous_phase": previous,
            "active_phase": normalized,
            "phase": self.context()["phase"],
            "manifest_path": self.project_scope()["manifest_path"],
            "updated_at": saved.get("updated_at"),
        }

    def request_phase_transition(
        self,
        phase: str,
        reason: str = "",
        requested_by: str = "ai",
    ) -> dict[str, Any]:
        normalized = normalize_phase(phase)
        manifest = self.load_manifest()
        request = {
            "phase": normalized,
            "label": PHASE_SPECS[normalized]["label"],
            "reason": str(reason or "").strip(),
            "requested_by": str(requested_by or "ai"),
            "timestamp": now_iso(),
        }
        manifest["phase_transition_request"] = request
        self.save_manifest(manifest)
        return {"ok": True, "requested_transition": request}

    def latest_intent_brief(self) -> dict[str, Any] | None:
        path = self._intent_json_path()
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def update_intent_brief(
        self,
        *,
        title: str = "",
        summary: str = "",
        requirements: dict[str, Any] | None = None,
        assumptions: list[str] | None = None,
        open_questions: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        readiness_score: int | float | None = None,
        ready_for_next_phase: bool | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        existing = self.latest_intent_brief() or {}
        version = int(existing.get("version", 0) or 0) + 1
        merged_requirements = _json_safe_dict(existing.get("requirements"))
        merged_requirements.update(_json_safe_dict(requirements))
        criteria = _json_safe_list(acceptance_criteria)
        if criteria:
            merged_requirements["acceptance_criteria"] = criteria
        score = self._normalize_readiness_score(readiness_score)
        if score is None:
            score = self.intent_readiness(
                {"requirements": merged_requirements, "open_questions": open_questions or []}
            )["score"]
        brief = {
            "schema": BRIEF_SCHEMA,
            "version": version,
            "updated_at": now_iso(),
            "title": str(title or existing.get("title") or self.project_scope()["title"]).strip(),
            "summary": str(summary or existing.get("summary") or "").strip(),
            "requirements": merged_requirements,
            "assumptions": _json_safe_list(assumptions if assumptions is not None else existing.get("assumptions")),
            "open_questions": _json_safe_list(open_questions if open_questions is not None else existing.get("open_questions")),
            "acceptance_criteria": criteria
            or _json_safe_list(existing.get("acceptance_criteria"))
            or _json_safe_list(merged_requirements.get("acceptance_criteria")),
            "readiness_score": score,
            "ready_for_next_phase": bool(ready_for_next_phase) if ready_for_next_phase is not None else score >= 80,
            "tags": _json_safe_list(tags if tags is not None else existing.get("tags")),
            "approved": False,
            "approval": None,
        }
        self._write_intent_artifacts(brief)
        manifest = self.load_manifest()
        manifest["title"] = brief["title"]
        manifest["summary"] = brief["summary"]
        manifest["active_phase"] = "intent"
        manifest["intent"] = {
            "approved": False,
            "brief_version": version,
            "brief_path": str(self._intent_json_path()),
            "brief_markdown_path": str(self._intent_markdown_path()),
        }
        manifest["approved_intent_version"] = None
        phase = manifest.setdefault("phases", {}).setdefault("intent", {})
        phase["status"] = "ready_for_approval" if brief["ready_for_next_phase"] else "in_progress"
        phase["artifact_paths"] = {
            "brief_json": str(self._intent_json_path()),
            "brief_markdown": str(self._intent_markdown_path()),
        }
        self.save_manifest(manifest)
        return {
            "ok": True,
            "brief": brief,
            "readiness": self.intent_readiness(brief),
            "manifest_path": self.project_scope()["manifest_path"],
            "brief_path": str(self._intent_json_path()),
            "brief_markdown_path": str(self._intent_markdown_path()),
            "next_action": (
                "Ask the user to approve the brief or answer the remaining questions."
                if brief["ready_for_next_phase"]
                else "Ask targeted questions for the missing critical design intent."
            ),
        }

    def approve_intent_brief(
        self,
        approved_by: str = "user",
        notes: str = "",
        transition_to_design: bool = True,
    ) -> dict[str, Any]:
        brief = self.latest_intent_brief()
        if not brief:
            return {"ok": False, "error": "No intent brief exists to approve."}
        approval = {
            "approved_by": str(approved_by or "user"),
            "approved_at": now_iso(),
            "notes": str(notes or "").strip(),
        }
        brief["approved"] = True
        brief["approval"] = approval
        self._write_intent_artifacts(brief)
        manifest = self.load_manifest()
        manifest["intent"] = {
            "approved": True,
            "brief_version": int(brief.get("version", 1) or 1),
            "brief_path": str(self._intent_json_path()),
            "brief_markdown_path": str(self._intent_markdown_path()),
            "approval": approval,
        }
        manifest["approved_intent_version"] = int(brief.get("version", 1) or 1)
        manifest.setdefault("phases", {}).setdefault("intent", {})["status"] = "approved"
        if transition_to_design:
            manifest["active_phase"] = "design"
            manifest.setdefault("phases", {}).setdefault("design", {})["status"] = "active"
        self.save_manifest(manifest)
        return {
            "ok": True,
            "approved_intent_version": manifest["approved_intent_version"],
            "active_phase": manifest.get("active_phase"),
            "brief_path": str(self._intent_json_path()),
            "approval": approval,
        }

    def intent_readiness(self, brief: dict[str, Any] | None) -> dict[str, Any]:
        if not brief:
            return {
                "score": 0,
                "ready_for_next_phase": False,
                "missing_fields": [item["key"] for item in INTENT_REQUIREMENT_FIELDS],
                "open_questions": [],
            }
        requirements = _json_safe_dict(brief.get("requirements"))
        missing = [
            item["key"]
            for item in INTENT_REQUIREMENT_FIELDS
            if not self._requirement_has_value(requirements.get(item["key"]))
        ]
        open_questions = _json_safe_list(brief.get("open_questions"))
        explicit_score = self._normalize_readiness_score(brief.get("readiness_score"))
        if explicit_score is None:
            answered = len(INTENT_REQUIREMENT_FIELDS) - len(missing)
            explicit_score = int(round((answered / max(1, len(INTENT_REQUIREMENT_FIELDS))) * 100))
            if open_questions:
                explicit_score = max(0, explicit_score - min(30, len(open_questions) * 10))
        ready = bool(brief.get("ready_for_next_phase")) and not missing[:3]
        return {
            "score": explicit_score,
            "ready_for_next_phase": ready,
            "missing_fields": missing,
            "open_questions": open_questions,
        }

    @staticmethod
    def _requirement_has_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, dict)):
            return bool(value)
        return True

    @staticmethod
    def _normalize_readiness_score(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return max(0, min(100, int(round(float(value)))))
        except Exception:
            return None

    def _default_manifest(self, scope: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": PROJECT_SCHEMA,
            "version": 1,
            "project_id": scope["project_id"],
            "title": scope["title"],
            "summary": "",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "active_phase": "intent",
            "approved_intent_version": None,
            "intent": {"approved": False, "brief_version": None},
            "documents": {"active": scope.get("document", {})},
            "phases": {
                phase: {
                    "status": "active" if phase == "intent" else "not_started",
                    "artifact_paths": {},
                }
                for phase in PHASE_ORDER
            },
            "phase_history": [],
        }

    def _merge_manifest_defaults(self, manifest: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
        default = self._default_manifest(scope)
        merged = dict(default)
        merged.update({key: value for key, value in manifest.items() if value is not None})
        merged["schema"] = PROJECT_SCHEMA
        merged["project_id"] = scope["project_id"]
        merged["documents"] = dict(merged.get("documents") or {})
        merged["documents"]["active"] = scope.get("document", {})
        merged["active_phase"] = normalize_phase(str(merged.get("active_phase") or "intent"))
        phases = dict(default["phases"])
        phases.update(_json_safe_dict(merged.get("phases")))
        merged["phases"] = phases
        return merged

    def _intent_json_path(self) -> Path:
        return Path(str(self.project_scope()["root"])) / "intent" / "brief.v1.json"

    def _intent_markdown_path(self) -> Path:
        return Path(str(self.project_scope()["root"])) / "intent" / "brief.md"

    def _write_intent_artifacts(self, brief: dict[str, Any]) -> None:
        json_path = self._intent_json_path()
        markdown_path = self._intent_markdown_path()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = json_path.with_name(f"{json_path.name}.tmp")
        tmp.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(json_path)
        tmp_md = markdown_path.with_name(f"{markdown_path.name}.tmp")
        tmp_md.write_text(self._brief_markdown(brief), encoding="utf-8")
        tmp_md.replace(markdown_path)

    def _brief_markdown(self, brief: dict[str, Any]) -> str:
        requirements = _json_safe_dict(brief.get("requirements"))
        lines = [
            f"# {brief.get('title') or 'VibeCAD Intent Brief'}",
            "",
            f"Updated: {brief.get('updated_at') or now_iso()}",
            f"Version: {brief.get('version') or 1}",
            f"Readiness: {brief.get('readiness_score', 0)}/100",
            f"Approved: {'yes' if brief.get('approved') else 'no'}",
            "",
            "## Summary",
            "",
            str(brief.get("summary") or "").strip() or "No summary captured yet.",
            "",
            "## Requirements",
            "",
        ]
        for item in INTENT_REQUIREMENT_FIELDS:
            value = requirements.get(item["key"])
            lines.append(f"- {item['label']}: {self._markdown_value(value)}")
        lines.extend(["", "## Assumptions", ""])
        assumptions = _json_safe_list(brief.get("assumptions"))
        lines.extend(f"- {item}" for item in assumptions) if assumptions else lines.append("- None")
        lines.extend(["", "## Open Questions", ""])
        questions = _json_safe_list(brief.get("open_questions"))
        lines.extend(f"- {item}" for item in questions) if questions else lines.append("- None")
        lines.extend(["", "## Acceptance Criteria", ""])
        criteria = _json_safe_list(brief.get("acceptance_criteria"))
        lines.extend(f"- {item}" for item in criteria) if criteria else lines.append("- Not captured")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _markdown_value(value: Any) -> str:
        if isinstance(value, list):
            return "; ".join(str(item) for item in value) or "Not captured"
        if isinstance(value, dict):
            return json.dumps(value, sort_keys=True)
        text = str(value or "").strip()
        return text or "Not captured"

    def _update_index(self, manifest: dict[str, Any], scope: dict[str, Any]) -> None:
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS projects (
                        project_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        root TEXT NOT NULL,
                        manifest_path TEXT NOT NULL,
                        cad_file TEXT,
                        active_phase TEXT NOT NULL,
                        approved_intent_version INTEGER,
                        updated_at TEXT NOT NULL,
                        tags_json TEXT NOT NULL
                    )
                    """
                )
                brief = self.latest_intent_brief() or {}
                conn.execute(
                    """
                    INSERT INTO projects (
                        project_id, title, summary, root, manifest_path, cad_file,
                        active_phase, approved_intent_version, updated_at, tags_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id) DO UPDATE SET
                        title=excluded.title,
                        summary=excluded.summary,
                        root=excluded.root,
                        manifest_path=excluded.manifest_path,
                        cad_file=excluded.cad_file,
                        active_phase=excluded.active_phase,
                        approved_intent_version=excluded.approved_intent_version,
                        updated_at=excluded.updated_at,
                        tags_json=excluded.tags_json
                    """,
                    (
                        manifest["project_id"],
                        str(manifest.get("title") or scope.get("title") or ""),
                        str(manifest.get("summary") or ""),
                        str(scope["root"]),
                        str(scope["manifest_path"]),
                        (scope.get("document") or {}).get("file_path"),
                        str(manifest.get("active_phase") or "intent"),
                        manifest.get("approved_intent_version"),
                        str(manifest.get("updated_at") or now_iso()),
                        json.dumps(_json_safe_list(brief.get("tags"))),
                    ),
                )
        except Exception:
            return
