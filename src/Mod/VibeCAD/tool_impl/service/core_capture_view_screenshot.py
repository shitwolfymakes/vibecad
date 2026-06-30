# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``core.capture_view_screenshot``."""

from __future__ import annotations

from pathlib import Path
import time


TOOL_SPEC = {'description': 'Capture the active FreeCAD viewport to a temporary PNG and return '
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
        temp_dir = Path("/tmp") / "vibecad-screenshots"
        temp_dir.mkdir(parents=True, exist_ok=True)
        path = temp_dir / f"vibecad-view-{int(time.time() * 1000)}.png"
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


def _active_document_name(app):
    try:
        document = app.ActiveDocument
        if document is not None:
            return document.Name
    except Exception:
        pass
    return None
