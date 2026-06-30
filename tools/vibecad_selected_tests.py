#!/usr/bin/env python3

"""Run selected VibeCAD unittest names inside FreeCAD."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build" / "release" / "Mod" / "VibeCAD"))

from PySide import QtCore, QtWidgets


def main() -> int:
    names = [item for item in sys.argv[1:] if item.startswith("TestVibeCAD.")]
    if not names:
        print("usage: vibecad_selected_tests.py TEST_NAME [TEST_NAME ...]", file=sys.stderr)
        return 2
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    for name in names:
        suite.addTests(loader.loadTestsFromName(name))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def run_and_exit() -> None:
    code = main()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.exit(code)


QtCore.QTimer.singleShot(0, run_and_exit)
