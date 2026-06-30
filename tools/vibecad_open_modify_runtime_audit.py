#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Audit VibeCAD open-and-modify workflow in real FreeCAD GUI."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui

try:
    from PySide import QtCore, QtWidgets
except Exception as exc:  # pragma: no cover - requires GUI FreeCAD
    print(json.dumps({"ok": False, "error": f"PySide unavailable: {exc}"}))
    sys.exit(1)

from VibeCADCore import VibeCADService
from VibeCADPreferences import VibeCADSettings, load_settings, save_settings
from VibeCADSession import make_provider_tool_runner


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "build"
    / "release"
    / "Mod"
    / "CAM"
    / "CAMTests"
    / "boxtest.fcstd"
)
_OLD_SETTINGS = None


def process_events(repeats: int = 5) -> None:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    for _ in range(repeats):
        app.processEvents()


def main() -> int:
    global _OLD_SETTINGS
    failures = []
    for document in list(App.listDocuments().values()):
        App.closeDocument(document.Name)

    main_window = Gui.getMainWindow()
    main_window.resize(1400, 900)
    main_window.show()
    process_events()

    if not FIXTURE.exists():
        failures.append(f"fixture missing: {FIXTURE}")
        print(json.dumps({"ok": False, "failures": failures}, indent=2, sort_keys=True))
        return 1

    _OLD_SETTINGS = load_settings()
    save_settings(
        VibeCADSettings(
            use_online_provider=_OLD_SETTINGS.use_online_provider,
            model=_OLD_SETTINGS.model,
            dotenv_path=_OLD_SETTINGS.dotenv_path,
            disabled_workbenches=_OLD_SETTINGS.disabled_workbenches,
            reasoning_effort=_OLD_SETTINGS.reasoning_effort,
            allow_primitive_provider_tools=True,
        )
    )
    service = VibeCADService()
    Gui.activateWorkbench("PartWorkbench")
    process_events()
    runner = make_provider_tool_runner(service, "PartWorkbench")

    open_result = runner("core.open_document", json.dumps({"file_path": str(FIXTURE)}))
    process_events(10)
    if not open_result.get("ok"):
        failures.append(f"core.open_document failed: {open_result}")

    document = service.document_summary()
    cube_before = next(
        (
            item
            for item in document.get("objects", [])
            if item.get("name") == "Box" or item.get("label") == "Cube"
        ),
        None,
    )
    if cube_before is None:
        failures.append("opened document did not expose Cube/Box object")

    edit_result = runner(
        "part.set_primitive_dimensions",
        json.dumps({"object_name": "Cube", "length": 12, "width": 8, "height": 4}),
    )
    process_events(10)
    if not edit_result.get("ok"):
        failures.append(f"part.set_primitive_dimensions failed: {edit_result}")

    active_doc = App.ActiveDocument
    cube = active_doc.getObject("Box") if active_doc else None
    if cube is None:
        failures.append("Cube object missing after edit")
    else:
        try:
            dimensions = [float(cube.Length), float(cube.Width), float(cube.Height)]
            if dimensions != [12.0, 8.0, 4.0]:
                failures.append(f"Cube dimensions not edited: {dimensions}")
        except Exception as exc:
            failures.append(f"could not read Cube dimensions: {exc}")

    screenshot = service.capture_view_screenshot()
    if not screenshot.get("captured"):
        failures.append(f"screenshot not captured: {screenshot}")
    elif int(screenshot.get("file_size", 0) or 0) < 1000:
        failures.append(f"screenshot file too small: {screenshot.get('file_size')}")

    final_document = service.document_summary()
    cube_summary = next(
        (
            item
            for item in final_document.get("objects", [])
            if item.get("name") == "Box" or item.get("label") == "Cube"
        ),
        None,
    )
    result = {
        "ok": not failures,
        "failures": failures,
        "fixture": str(FIXTURE),
        "open_ok": bool(open_result.get("ok")),
        "edit_ok": bool(edit_result.get("ok")),
        "document": {
            "name": final_document.get("document"),
            "object_count": final_document.get("object_count"),
            "cube": cube_summary,
        },
        "screenshot": {
            "captured": bool(screenshot.get("captured")),
            "file_size": screenshot.get("file_size"),
            "path": screenshot.get("path"),
            "visual_observation": screenshot.get("visual_observation"),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if _OLD_SETTINGS is not None:
        save_settings(_OLD_SETTINGS)
        _OLD_SETTINGS = None
    return 1 if failures else 0


def run_and_exit() -> None:
    global _OLD_SETTINGS
    code = 1
    try:
        code = main()
    except Exception:
        print(
            json.dumps(
                {"ok": False, "traceback": traceback.format_exc()},
                indent=2,
                sort_keys=True,
            )
        )
    finally:
        if _OLD_SETTINGS is not None:
            save_settings(_OLD_SETTINGS)
            _OLD_SETTINGS = None
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.exit(code)


QtCore.QTimer.singleShot(1500, run_and_exit)
