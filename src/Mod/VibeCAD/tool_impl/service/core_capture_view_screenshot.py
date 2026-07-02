# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``core.capture_view_screenshot``."""

from __future__ import annotations

import os
from pathlib import Path
import re
import time


TOOL_SPEC = {'description': 'Capture the active FreeCAD viewport to a durable project PNG and return '
                'redacted metadata.',
 'name': 'core.capture_view_screenshot',
 'safety': 'VIEW'}


def run(service, **kwargs):
    try:
        import FreeCAD as App
        import FreeCADGui as Gui
    except Exception as exc:
        result = {"ok": False, "captured": False, "path": None, "file_size": 0, "error": str(exc)}
        service._last_view_screenshot = result
        return result

    try:
        screenshot_dir = _screenshot_artifact_dir(service)
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        document_name = _slug(_active_document_name(App) or "view")
        path = screenshot_dir / f"{document_name}-{int(time.time() * 1000)}.png"
        view = Gui.ActiveDocument.ActiveView if Gui.ActiveDocument else None
        if view is None:
            result = {
                "ok": False,
                "captured": False,
                "path": None,
                "file_size": 0,
                "error": "No active 3D view is available.",
            }
            service._last_view_screenshot = result
            return result
        try:
            view.viewAxometric()
            view.fitAll()
        except Exception:
            pass
        view.saveImage(str(path), 1280, 900, "White")
        captured = path.exists()
        result = {
            "ok": captured,
            "captured": captured,
            "path": str(path) if captured else None,
            "file_size": path.stat().st_size if captured else 0,
            "size": [1280, 900],
            "format": "png",
            "background": "White",
            "artifact_role": "visual_verification",
            "workbench": _active_workbench_name(Gui),
            "document": _active_document_name(App),
        }
        if captured:
            result["visual_observation"] = service._screenshot_visual_observation(path)
        else:
            result["error"] = "View saveImage did not create a file."
        service._last_view_screenshot = result
        return result
    except Exception as exc:
        result = {"ok": False, "captured": False, "path": None, "file_size": 0, "error": str(exc)}
        service._last_view_screenshot = result
        return result


def _active_workbench_name(gui):
    try:
        workbench = gui.activeWorkbench()
        if workbench:
            return workbench.name()
    except Exception:
        pass
    return None


def _screenshot_artifact_dir(service) -> Path:
    try:
        phase_context = service.phase_context()
    except Exception:
        phase_context = {}
    root = phase_context.get("root") if isinstance(phase_context, dict) else None
    if root:
        return Path(str(root)).expanduser() / "artifacts" / "screenshots"
    configured = str(os.environ.get("VIBECAD_HOME") or "").strip()
    if configured:
        return Path(configured).expanduser() / "artifacts" / "screenshots"
    try:
        return Path.home() / ".vibecad" / "artifacts" / "screenshots"
    except Exception:
        return Path.cwd() / ".vibecad" / "artifacts" / "screenshots"


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("._")
    return slug[:64] or "view"


def _active_document_name(app):
    try:
        document = app.ActiveDocument
        if document is not None:
            return document.Name
    except Exception:
        pass
    return None
