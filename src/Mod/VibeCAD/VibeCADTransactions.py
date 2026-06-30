# SPDX-License-Identifier: LGPL-2.1-or-later

"""Approval queue and transaction helpers for VibeCAD write tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
import itertools


ActionHandler = Callable[[], dict[str, Any]]
VerificationHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class ActionProposal:
    id: str
    title: str
    description: str
    safety: str
    workbench: str | None
    handler: ActionHandler
    verifier: VerificationHandler | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "safety": self.safety,
            "workbench": self.workbench,
            "metadata": self.metadata,
        }


class ApprovalQueue:
    def __init__(self) -> None:
        self._counter = itertools.count(1)
        self._pending: dict[str, ActionProposal] = {}
        self._history: list[dict[str, Any]] = []

    def propose(
        self,
        title: str,
        description: str,
        safety: str,
        workbench: str | None,
        handler: ActionHandler,
        verifier: VerificationHandler | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        action_id = f"action-{next(self._counter)}"
        proposal = ActionProposal(
            id=action_id,
            title=title,
            description=description,
            safety=safety,
            workbench=workbench,
            handler=handler,
            verifier=verifier,
            metadata=metadata or {},
        )
        self._pending[action_id] = proposal
        return proposal.summary()

    def pending(self) -> list[dict[str, Any]]:
        return [proposal.summary() for proposal in self._pending.values()]

    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

    def clear(self) -> dict[str, Any]:
        pending_count = len(self._pending)
        history_count = len(self._history)
        self._pending.clear()
        self._history.clear()
        return {
            "cleared": True,
            "pending_count": pending_count,
            "history_count": history_count,
        }

    def last_applied(self) -> dict[str, Any] | None:
        undone_ids = {
            record.get("target_action_id")
            for record in self._history
            if record.get("status") == "undone"
        }
        for record in reversed(self._history):
            if record.get("status") == "applied" and record.get("id") not in undone_ids:
                return dict(record)
        return None

    def record_undo(self, action_id: str, title: str, result: dict[str, Any]) -> dict[str, Any]:
        record = {
            "id": f"undo-{action_id}",
            "target_action_id": action_id,
            "status": "undone" if result.get("ok") else "undo_failed",
            "title": f"Undo: {title}",
            "result": result,
        }
        self._history.append(record)
        return record

    def reject(self, action_id: str) -> dict[str, Any]:
        proposal = self._pending.pop(action_id)
        result = {
            "id": action_id,
            "status": "rejected",
            "title": proposal.title,
        }
        self._history.append(result)
        return result

    def apply(self, action_id: str) -> dict[str, Any]:
        proposal = self._pending.pop(action_id)
        result = run_freecad_transaction(proposal.title, proposal.handler, proposal.verifier)
        record = {
            "id": action_id,
            "status": "applied" if result.get("ok") else "failed",
            "title": proposal.title,
            "result": result,
        }
        self._history.append(record)
        return record


def run_freecad_transaction(
    name: str,
    handler: ActionHandler,
    verifier: VerificationHandler | None = None,
) -> dict[str, Any]:
    try:
        import FreeCAD as App
    except Exception as exc:
        return {"ok": False, "error": f"FreeCAD unavailable: {exc}"}

    opened = False
    doc = App.ActiveDocument
    before = _document_snapshot(doc)
    try:
        if doc is not None and hasattr(doc, "openTransaction"):
            doc.openTransaction(name)
            opened = True
        result = handler()
        active_doc = App.ActiveDocument or doc
        if active_doc is not None and hasattr(active_doc, "recompute"):
            active_doc.recompute()
        verification = verifier(result) if verifier else {"ok": True, "checks": []}
        after = _document_snapshot(active_doc)
        document_delta = _document_delta(before, after)
        report_view_errors = report_view_error_summary()
        if opened and hasattr(doc, "commitTransaction"):
            doc.commitTransaction()
        return {
            "ok": bool(verification.get("ok", True)),
            "result": result,
            "verification": verification,
            "document_before": before,
            "document_after": after,
            "document_delta": document_delta,
            "report_view_errors": report_view_errors,
        }
    except Exception as exc:
        if opened and doc is not None and hasattr(doc, "abortTransaction"):
            doc.abortTransaction()
        active_doc = App.ActiveDocument or doc
        after = _document_snapshot(active_doc)
        return {
            "ok": False,
            "error": str(exc),
            "document_before": before,
            "document_after": after,
            "document_delta": _document_delta(before, after),
            "report_view_errors": {
                "captured": True,
                "errors": [str(exc)],
                "source": "transaction_exception",
            },
        }


def _document_snapshot(doc: Any | None) -> dict[str, Any]:
    if doc is None:
        return {"document": None, "object_count": 0, "objects": []}
    objects = []
    for obj in getattr(doc, "Objects", []):
        item = {
            "name": getattr(obj, "Name", ""),
            "label": getattr(obj, "Label", getattr(obj, "Name", "")),
            "type": getattr(obj, "TypeId", ""),
        }
        shape = _shape_summary(obj)
        if shape.get("available") and _should_include_shape_in_snapshot(obj, shape):
            item["shape"] = shape
        objects.append(item)
    return {
        "document": getattr(doc, "Name", None),
        "object_count": len(objects),
        "objects": objects,
    }


def _should_include_shape_in_snapshot(obj: Any, shape: dict[str, Any]) -> bool:
    type_id = str(getattr(obj, "TypeId", ""))
    if type_id.startswith("App::"):
        return False
    return (
        type_id.startswith("Part::")
        or type_id.startswith("PartDesign::")
        or type_id.startswith("Sketcher::")
        or int(shape.get("solids", 0) or 0) > 0
        or abs(float(shape.get("volume", 0.0) or 0.0)) > 1e-9
    )


def _shape_summary(obj: Any) -> dict[str, Any]:
    shape = getattr(obj, "Shape", None)
    if shape is None:
        return {"available": False}
    try:
        summary = {
            "available": True,
            "solids": len(getattr(shape, "Solids", []) or []),
            "faces": len(getattr(shape, "Faces", []) or []),
            "edges": len(getattr(shape, "Edges", []) or []),
            "vertices": len(getattr(shape, "Vertexes", []) or []),
            "volume": float(getattr(shape, "Volume", 0.0) or 0.0),
        }
        bound_box = _bound_box_summary(getattr(shape, "BoundBox", None))
        if bound_box:
            summary["bound_box"] = bound_box
        return summary
    except Exception:
        return {"available": False}


def _bound_box_summary(bound_box: Any) -> dict[str, Any] | None:
    if bound_box is None:
        return None
    try:
        return {
            "xmin": float(bound_box.XMin),
            "ymin": float(bound_box.YMin),
            "zmin": float(bound_box.ZMin),
            "xmax": float(bound_box.XMax),
            "ymax": float(bound_box.YMax),
            "zmax": float(bound_box.ZMax),
            "xlength": float(bound_box.XLength),
            "ylength": float(bound_box.YLength),
            "zlength": float(bound_box.ZLength),
        }
    except Exception:
        return None


def _document_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_objects = {item["name"]: item for item in before.get("objects", [])}
    after_objects = {item["name"]: item for item in after.get("objects", [])}
    before_names = set(before_objects)
    after_names = set(after_objects)
    changed = []
    for name in sorted(before_names.intersection(after_names)):
        before_item = before_objects[name]
        after_item = after_objects[name]
        if before_item != after_item:
            changed.append({"name": name, "before": before_item, "after": after_item})
    return {
        "object_count_before": int(before.get("object_count", 0)),
        "object_count_after": int(after.get("object_count", 0)),
        "object_count_delta": int(after.get("object_count", 0)) - int(before.get("object_count", 0)),
        "created_objects": [after_objects[name] for name in sorted(after_names - before_names)],
        "deleted_objects": [before_objects[name] for name in sorted(before_names - after_names)],
        "changed_objects": changed,
    }


def report_view_error_summary() -> dict[str, Any]:
    try:
        import FreeCADGui as Gui
        from PySide import QtWidgets
    except Exception as exc:
        return {
            "captured": False,
            "errors": [],
            "source": "unavailable",
            "reason": str(exc),
        }

    try:
        main_window = Gui.getMainWindow()
        candidates = main_window.findChildren(QtWidgets.QPlainTextEdit)
        candidates += main_window.findChildren(QtWidgets.QTextEdit)
        lines: list[str] = []
        for widget in candidates:
            object_name = getattr(widget, "objectName", lambda: "")()
            window_title = getattr(widget, "windowTitle", lambda: "")()
            identity = f"{object_name} {window_title} {widget.__class__.__name__}".lower()
            if "report" not in identity:
                continue
            text = widget.toPlainText() if hasattr(widget, "toPlainText") else widget.toHtml()
            for line in text.splitlines():
                stripped = line.strip()
                if not _is_report_view_error_line(stripped):
                    continue
                lines.append(_bounded_report_view_line(stripped))
        return {
            "captured": True,
            "errors": lines[-20:],
            "source": "report_view_widgets",
        }
    except Exception as exc:
        return {
            "captured": False,
            "errors": [],
            "source": "report_view_widgets",
            "reason": str(exc),
        }


def _is_report_view_error_line(line: str) -> bool:
    lowered = line.lower()
    if not line:
        return False
    if lowered == "no report-view errors detected.":
        return False
    if '{"progress":' in line or '"event": "tool_call_completed"' in line:
        return False
    if lowered.startswith("report errors:"):
        return False
    return "error" in lowered or "exception" in lowered or "traceback" in lowered


def _bounded_report_view_line(line: str, limit: int = 500) -> str:
    if len(line) <= limit:
        return line
    return line[: limit - 3] + "..."
