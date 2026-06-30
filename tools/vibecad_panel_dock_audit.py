#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Verify VibeCAD opens as a normal right-side FreeCAD dock panel."""

from __future__ import annotations

import json
import sys
import traceback

import FreeCADGui as Gui

try:
    from PySide import QtCore, QtWidgets
except Exception as exc:  # pragma: no cover - requires GUI FreeCAD
    print(json.dumps({"ok": False, "error": f"PySide unavailable: {exc}"}))
    sys.exit(1)


def process_events(repeats: int = 5) -> None:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    for _ in range(repeats):
        app.processEvents()


def main() -> int:
    main_window = Gui.getMainWindow()
    main_window.resize(1600, 1000)
    main_window.show()
    process_events()

    Gui.activateWorkbench("PartWorkbench")
    process_events()
    Gui.runCommand("VibeCAD_OpenAssistant")
    process_events(10)

    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    if dock is None:
        result = {"ok": False, "failures": ["VibeCADAssistantPanel not found"]}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    area = main_window.dockWidgetArea(dock)
    rect = dock.geometry()
    failures = []
    if not dock.isVisible():
        failures.append("panel is not visible")
    if dock.isFloating():
        failures.append("panel is floating by default")
    if area != QtCore.Qt.RightDockWidgetArea:
        failures.append(f"panel is not right-docked by default: {int(area)}")
    if not (dock.features() & QtWidgets.QDockWidget.DockWidgetMovable):
        failures.append("panel is not movable/dockable")
    if not (dock.features() & QtWidgets.QDockWidget.DockWidgetFloatable):
        failures.append("panel is not floatable like normal docks")
    if rect.width() > 560:
        failures.append(f"panel is too wide by default: {rect.width()}")

    result = {
        "ok": not failures,
        "failures": failures,
        "visible": dock.isVisible(),
        "floating": dock.isFloating(),
        "area": "right" if area == QtCore.Qt.RightDockWidgetArea else int(area),
        "geometry": [rect.x(), rect.y(), rect.width(), rect.height()],
        "features": str(dock.features()),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if failures else 0


def run_and_exit() -> None:
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
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.exit(code)


QtCore.QTimer.singleShot(1500, run_and_exit)
