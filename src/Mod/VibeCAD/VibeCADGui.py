# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI commands that existing workbenches can register natively."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from VibeCADCore import get_service
from VibeCADSession import _format_document_delta, run_prompt
from VibeCADWorkbenchTools import get_tool_pack


COMMANDS = [
    "VibeCAD_AskAI",
    "VibeCAD_ExplainSelection",
    "VibeCAD_OpenAssistant",
    "VibeCAD_OpenPreferences",
    "VibeCAD_AuthStatus",
]

CONTEXT_COMMANDS = [
    "VibeCAD_ExplainSelection",
    "VibeCAD_OpenAssistant",
    "VibeCAD_AskAI",
]

_commands_registered = False
_preferences_registered = False
_workbench_manipulator = None
_workbench_activation_connected = False


class _WorkbenchManipulator:
    """Expose VibeCAD commands in C++-backed workbenches."""

    def modifyMenuBar(self) -> list[dict[str, str]]:
        return [
            {"append": command, "menuItem": "Std_DlgParameter"}
            for command in COMMANDS
        ]

    def modifyToolBars(self) -> list[dict[str, str]]:
        return [
            {"append": command, "toolBar": "File"}
            for command in COMMANDS
        ]


def _print(message: str) -> None:
    App.Console.PrintMessage(f"{message}\n")


def _append_output(text: str) -> None:
    try:
        from PySide import QtWidgets
    except Exception:
        _print(text)
        return

    main_window = Gui.getMainWindow()
    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    output = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADOutput") if dock else None
    if output is None:
        _print(text)
        return
    current = output.toPlainText().strip()
    output.setPlainText(f"{current}\n\n{text}".strip())
    from PySide import QtGui

    output.moveCursor(QtGui.QTextCursor.End)


def _set_tool_trace(tool_trace: list[dict[str, Any]]) -> None:
    try:
        from PySide import QtWidgets
    except Exception:
        return

    main_window = Gui.getMainWindow()
    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    trace_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADToolTrace") if dock else None
    if trace_box is None:
        return
    if not tool_trace:
        trace_box.setPlainText("No provider tool calls yet.")
        return
    lines = []
    for index, entry in enumerate(tool_trace, start=1):
        status = "ok" if entry.get("ok") else "blocked"
        result = entry.get("result") or {}
        suffix = ""
        if result.get("title"):
            suffix = f" | {result['title']}"
        elif result.get("error"):
            suffix = f" | {result['error']}"
        lines.append(
            f"{index}. {status} | {entry.get('safety', 'unknown')} | "
            f"{entry.get('tool_name', 'unknown')}{suffix}"
        )
    trace_box.setPlainText("\n".join(lines))


def _format_progress_event(event: dict[str, Any]) -> str:
    name = str(event.get("event", "progress"))
    if name == "context_build_started":
        return "Reading FreeCAD context..."
    if name == "context_build_completed":
        return (
            f"Context ready: {event.get('workbench', 'workbench')} | "
            f"{event.get('provider_tool_count', 0)} provider tools"
        )
    if name == "provider_turn_started":
        base = (
            f"Thinking: {event.get('provider', 'provider')} turn "
            f"{event.get('turn', '?')}..."
        )
        delta = _format_document_delta(event.get("document_delta"))
        if delta and not delta.startswith("not available"):
            return f"{base} | {delta}"
        return base
    if name == "provider_turn_completed":
        return (
            f"Provider turn {event.get('turn', '?')} completed | "
            f"tools: {event.get('tool_count', 0)}"
        )
    if name == "provider_turn_failed":
        return (
            f"Provider turn {event.get('turn', '?')} failed: "
            f"{event.get('error', 'unknown error')}"
        )
    if name == "provider_total_timeout":
        return (
            f"Autonomous loop reached {event.get('elapsed_seconds', 0):.1f}s | "
            f"tools: {event.get('tool_count', 0)}"
        )
    if name == "provider_run_cancelled":
        return "Run stopped by user."
    if name == "tool_call_completed":
        status = "ok" if event.get("ok") else "blocked"
        return f"Tool {status}: {event.get('tool_name', 'unknown')}"
    return name.replace("_", " ")


def _handle_progress_event(dock: Any, event: dict[str, Any], tool_trace: list[dict[str, Any]]) -> None:
    try:
        from PySide import QtWidgets
    except Exception:
        return

    text = _format_progress_event(event)
    run_status = dock.findChild(QtWidgets.QLabel, "VibeCADRunStatus") if dock else None
    progress_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADOutput") if dock else None
    if run_status is not None:
        run_status.setText(text)
    if progress_box is not None:
        current = progress_box.toPlainText().strip()
        line = f"[progress] {text}"
        if not current.endswith(line):
            progress_box.setPlainText(f"{current}\n{line}".strip())
            from PySide import QtGui

            progress_box.moveCursor(QtGui.QTextCursor.End)
    if event.get("event") == "tool_call_completed":
        _set_tool_trace(tool_trace)
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


def _set_screenshot_status(summary: dict[str, Any]) -> None:
    try:
        from PySide import QtWidgets
    except Exception:
        return

    main_window = Gui.getMainWindow()
    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    status = dock.findChild(QtWidgets.QLabel, "VibeCADScreenshotStatus") if dock else None
    if status is None:
        return
    if summary.get("captured"):
        size = summary.get("size") or ["?", "?"]
        status.setText(
            f"View attached: {size[0]}x{size[1]} | {summary.get('camera_type', 'camera')}"
        )
    elif summary.get("error"):
        status.setText(f"View not attached: {summary['error']}")
    else:
        status.setText("No viewport screenshot attached.")


def _capture_view_from_panel() -> None:
    summary = get_service().capture_view_screenshot()
    _set_screenshot_status(summary)
    if summary.get("captured"):
        _append_output(
            "Attached viewport screenshot: "
            f"{summary.get('size', ['?', '?'])} {summary.get('camera_type', 'camera')}"
        )
    else:
        _append_output(f"Viewport screenshot failed: {summary.get('error', 'unknown error')}")
    _refresh_workbench_context()


def _set_prompt_busy(dock: Any, busy: bool, text: str | None = None) -> None:
    try:
        from PySide import QtWidgets
    except Exception:
        return

    run_button = dock.findChild(QtWidgets.QPushButton, "VibeCADRunPrompt") if dock else None
    stop_button = dock.findChild(QtWidgets.QPushButton, "VibeCADStopPrompt") if dock else None
    prompt_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADPrompt") if dock else None
    online_box = dock.findChild(QtWidgets.QCheckBox, "VibeCADUseOnlineProvider") if dock else None
    capture_button = dock.findChild(QtWidgets.QPushButton, "VibeCADCaptureView") if dock else None
    run_status = dock.findChild(QtWidgets.QLabel, "VibeCADRunStatus") if dock else None

    if run_button is not None:
        run_button.setEnabled(not busy)
        run_button.setText("Running" if busy else "Run")
    if stop_button is not None:
        stop_button.setEnabled(busy)
    if prompt_box is not None:
        prompt_box.setReadOnly(busy)
    if online_box is not None:
        online_box.setEnabled(not busy)
    if capture_button is not None:
        capture_button.setEnabled(not busy)
    if run_status is not None:
        run_status.setText(text or ("Running provider request..." if busy else "Ready."))


def _stop_prompt_from_panel() -> None:
    try:
        from PySide import QtWidgets
    except Exception:
        return

    main_window = Gui.getMainWindow()
    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    if dock is None:
        return
    dock.setProperty("VibeCADCancelRequested", True)
    run_status = dock.findChild(QtWidgets.QLabel, "VibeCADRunStatus")
    if run_status is not None:
        run_status.setText("Stopping after the current provider/tool step...")
    _append_output("[progress] Stop requested.")


def _run_prompt_from_panel() -> None:
    try:
        from PySide import QtWidgets
    except Exception:
        _print("VibeCAD assistant panel requires Qt.")
        return

    main_window = Gui.getMainWindow()
    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    if dock is None:
        return

    prompt_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADPrompt")
    online_box = dock.findChild(QtWidgets.QCheckBox, "VibeCADUseOnlineProvider")
    if prompt_box is None:
        return

    run_status = dock.findChild(QtWidgets.QLabel, "VibeCADRunStatus")
    if prompt_box.isReadOnly():
        if run_status is not None:
            run_status.setText("Provider request already running.")
        return

    prompt = prompt_box.toPlainText().strip()
    if not prompt:
        _append_output("Enter a prompt first.")
        return

    service = get_service()
    prefer_online = (
        bool(online_box.isChecked())
        if online_box is not None
        else service.use_online_provider_by_default()
    )
    dock.setProperty("VibeCADCancelRequested", False)
    _set_prompt_busy(dock, True)
    live_tool_trace: list[dict[str, Any]] = []

    def _cancelled() -> bool:
        return bool(dock.property("VibeCADCancelRequested"))

    def _progress(event: dict[str, Any]) -> None:
        if event.get("event") == "tool_call_completed":
            live_tool_trace.append(
                {
                    "tool_name": event.get("tool_name"),
                    "active_workbench": event.get("active_workbench"),
                    "ok": bool(event.get("ok")),
                    "safety": event.get("safety", "unknown"),
                    "result": event.get("result", {}),
                }
            )
        _handle_progress_event(dock, event, live_tool_trace)

    try:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.processEvents()
        response = run_prompt(
            prompt,
            service=service,
            prefer_online=prefer_online,
            progress_callback=_progress,
            cancellation_check=_cancelled,
        )
        error = f"\nProvider note: {response.error}" if response.error else ""
        _append_output(
            f"> {prompt}\n\n[{response.provider}] {response.final_output}{error}"
        )
        _set_tool_trace(response.tool_trace)
        prompt_box.clear()
    except Exception as exc:
        _append_output(f"VibeCAD prompt failed: {exc}")
    finally:
        dock.setProperty("VibeCADCancelRequested", False)
        _set_prompt_busy(dock, False)
        _refresh_pending_actions()
        _refresh_action_history()


def _friendly_status(value: Any) -> str:
    return str(value or "unknown").replace("_", " ")


def _friendly_workbench(value: str | None) -> str:
    if not value:
        return "none"
    return value.removesuffix("Workbench") or value


def _pending_action_ids() -> list[str]:
    service = get_service()
    return [item["id"] for item in service.pending_actions()["pending"]]


def _selected_action_id() -> str | None:
    try:
        from PySide import QtWidgets
    except Exception:
        return None

    main_window = Gui.getMainWindow()
    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    selector = dock.findChild(QtWidgets.QComboBox, "VibeCADActionSelector") if dock else None
    if selector is None:
        return None
    value = selector.currentData()
    return str(value) if value else None


def _refresh_pending_actions() -> None:
    try:
        from PySide import QtWidgets
    except Exception:
        return

    main_window = Gui.getMainWindow()
    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    pending_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADPendingActions") if dock else None
    selector = dock.findChild(QtWidgets.QComboBox, "VibeCADActionSelector") if dock else None
    if pending_box is None:
        return

    pending = get_service().pending_actions()["pending"]
    if selector is not None:
        current = selector.currentData()
        selector.clear()
        for item in pending:
            selector.addItem(f"{item['id']} | {item['title']}", item["id"])
        if current:
            index = selector.findData(current)
            if index >= 0:
                selector.setCurrentIndex(index)
    if not pending:
        pending_box.setPlainText("No pending actions.")
        return
    lines = []
    for item in pending:
        lines.append(
            f"{item['id']} | {item['safety']} | {item['title']}\n{item['description']}"
        )
    pending_box.setPlainText("\n\n".join(lines))


def _refresh_action_history() -> None:
    try:
        from PySide import QtWidgets
    except Exception:
        return

    main_window = Gui.getMainWindow()
    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    history_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADActionHistory") if dock else None
    if history_box is None:
        return

    history = get_service().action_history()["history"]
    if not history:
        history_box.setPlainText("No approved or rejected actions yet.")
        return
    lines = []
    for item in history[-12:]:
        status = item.get("status", "unknown")
        title = item.get("title", "Untitled action")
        detail = ""
        result = item.get("result")
        if isinstance(result, dict):
            if result.get("ok") is False and result.get("error"):
                detail = f" | {result['error']}"
            elif isinstance(result.get("verification"), dict):
                detail = f" | verified: {bool(result['verification'].get('ok', True))}"
                delta = result.get("document_delta")
                if isinstance(delta, dict):
                    detail += f" | objects: {delta.get('object_count_delta', 0):+d}"
                report_errors = result.get("report_view_errors")
                if isinstance(report_errors, dict) and report_errors.get("errors"):
                    detail += f" | report errors: {len(report_errors['errors'])}"
        lines.append(f"{item.get('id', 'action')} | {status} | {title}{detail}")
    history_box.setPlainText("\n".join(lines))


def _refresh_workbench_context() -> None:
    try:
        from PySide import QtWidgets
    except Exception:
        return

    main_window = Gui.getMainWindow()
    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    if dock is None:
        return
    tool_pack_label = dock.findChild(QtWidgets.QLabel, "VibeCADToolPack")
    commands_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADWorkbenchCommands")
    templates_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADObjectTemplates")
    objects_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADWorkbenchObjects")
    provider_tools_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADProviderTools")
    tool_trace_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADToolTrace")
    report_errors_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADReportErrors")
    screenshot_status = dock.findChild(QtWidgets.QLabel, "VibeCADScreenshotStatus")
    part_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADPartContext")
    mesh_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADMeshContext")
    points_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADPointsContext")
    material_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADMaterialContext")
    sketcher_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADSketcherContext")
    spreadsheet_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADSpreadsheetContext")
    draft_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADDraftContext")
    partdesign_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADPartDesignContext")
    techdraw_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADTechDrawContext")
    fem_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADFemContext")
    cam_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADCamContext")
    bim_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADBimContext")
    assembly_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADAssemblyContext")
    inspection_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADInspectionContext")
    openscad_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADOpenSCADContext")
    surface_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADSurfaceContext")
    reen_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADReverseEngineeringContext")
    robot_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADRobotContext")
    meshpart_box = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADMeshPartContext")
    service = get_service()
    pack = service.workbench_tool_pack_summary()["tool_pack"]
    commands = service.workbench_command_summary()
    templates = service.workbench_object_templates()["templates"]
    objects = service.workbench_object_summary()["objects"]
    provider_tools = service.provider_tool_surface()["tools"]
    report_errors = service.report_view_errors()
    part = service.part_summary()
    mesh = service.mesh_summary()
    points = service.points_summary()
    material = service.material_summary()
    sketcher = service.sketcher_summary()
    spreadsheet = service.spreadsheet_summary()
    draft = service.draft_summary()
    partdesign = service.partdesign_summary()
    techdraw = service.techdraw_summary()
    fem = service.fem_summary()
    cam = service.cam_summary()
    bim = service.bim_summary()
    assembly = service.assembly_summary()
    inspection = service.inspection_summary()
    openscad = service.openscad_summary()
    surface = service.surface_summary()
    reen = service.reverseengineering_summary()
    robot = service.robot_summary()
    meshpart = service.meshpart_summary()
    if tool_pack_label is not None:
        if pack:
            state = "enabled" if pack.get("enabled", True) else "disabled"
            friendly_name = _friendly_workbench(pack["workbench"])
            tool_pack_label.setText(
                f"Tool pack: {pack['workbench']} | {friendly_name} tools | "
                f"{pack['domain']} | {state}"
            )
        else:
            tool_pack_label.setText("Tool pack: none")
    if commands_box is not None:
        names = commands["commands"][:40]
        suffix = "" if len(commands["commands"]) <= 40 else "\n..."
        commands_box.setPlainText(
            f"{commands['command_count']} matching commands\n"
            + "\n".join(names)
            + suffix
        )
    if templates_box is not None:
        lines = [
            f"{item['name']} | {item['object_type']}"
            for item in templates
        ]
        templates_box.setPlainText("\n".join(lines) if lines else "No object templates.")
    if objects_box is not None:
        lines = [
            f"{item['name']} | {item['label']} | {item['type']}"
            for item in objects
        ]
        objects_box.setPlainText("\n".join(lines) if lines else "No workbench-owned objects.")
    if provider_tools_box is not None:
        lines = [
            f"{item['name']} | {item['safety']} | {item['availability']}"
            for item in provider_tools
        ]
        provider_tools_box.setPlainText("\n".join(lines) if lines else "No provider tools.")
    if tool_trace_box is not None and not tool_trace_box.toPlainText().strip():
        tool_trace_box.setPlainText("No provider tool calls yet.")
    if report_errors_box is not None:
        errors = report_errors.get("errors") or []
        if errors:
            report_errors_box.setPlainText(
                f"Report errors: {len(errors)}\n" + "\n".join(errors[-8:])
            )
        elif report_errors.get("captured"):
            report_errors_box.setPlainText("No report-view errors detected.")
        else:
            reason = report_errors.get("reason", "report view unavailable")
            report_errors_box.setPlainText(f"Report-view errors unavailable: {reason}")
    if screenshot_status is not None:
        _set_screenshot_status(service.view_screenshot_summary())
    if part_box is not None:
        if part["object_count"]:
            lines = [
                f"{item['name']} | {item['label']} | {item['type']}"
                for item in part["objects"][:8]
            ]
            part_box.setPlainText(
                f"Part objects: {part['object_count']}\n" + "\n".join(lines)
            )
        else:
            part_box.setPlainText("No Part context.")
    if mesh_box is not None:
        if mesh["object_count"]:
            lines = [
                f"{item['name']} | {item['label']} | Facets: {item.get('mesh', {}).get('facets', 0)}"
                for item in mesh["objects"][:8]
            ]
            mesh_box.setPlainText(
                f"Mesh objects: {mesh['object_count']}\n" + "\n".join(lines)
            )
        else:
            mesh_box.setPlainText("No Mesh context.")
    if points_box is not None:
        if points["object_count"]:
            lines = [
                f"{item['name']} | {item['label']} | Points: {item['point_count']}"
                for item in points["objects"][:8]
            ]
            points_box.setPlainText(
                f"Point clouds: {points['object_count']}\n" + "\n".join(lines)
            )
        else:
            points_box.setPlainText("No Points context.")
    if material_box is not None:
        if material["object_count"]:
            lines = []
            for item in material["objects"][:8]:
                color = item.get("diffusecolor") or item.get("first_shape_diffuse_color") or "none"
                lines.append(
                    f"{item['name']} | {item['label']} | "
                    f"Color: {color} | Appearance slots: {item.get('shape_appearance_count')}"
                )
            material_box.setPlainText(
                f"Material-capable objects: {material['object_count']}\n" + "\n".join(lines)
            )
        else:
            material_box.setPlainText("No Material context.")
    if sketcher_box is not None:
        if sketcher["found"]:
            sketch = sketcher["sketch"]
            sketcher_box.setPlainText(
                f"{sketch['name']} | {sketch['label']}\n"
                f"Geometry: {sketcher['geometry_count']} | "
                f"Constraints: {sketcher['constraint_count']}"
            )
        else:
            sketcher_box.setPlainText("No Sketcher sketch context.")
    if spreadsheet_box is not None:
        if spreadsheet["found"]:
            sheet = spreadsheet["sheet"]
            spreadsheet_box.setPlainText(
                f"{sheet['name']} | {sheet['label']}\n"
                f"Non-empty cells: {spreadsheet['non_empty_count']}"
            )
        else:
            spreadsheet_box.setPlainText("No Spreadsheet context.")
    if draft_box is not None:
        if draft["object_count"]:
            lines = [
                f"{item['name']} | {item['label']} | {item['type']}"
                for item in draft["objects"][:8]
            ]
            draft_box.setPlainText(
                f"Draft objects: {draft['object_count']}\n" + "\n".join(lines)
            )
        else:
            draft_box.setPlainText("No Draft context.")
    if partdesign_box is not None:
        if partdesign["body_count"]:
            lines = []
            for body in partdesign["bodies"][:6]:
                tip = body["tip"]["name"] if body["tip"] else "none"
                lines.append(
                    f"{body['name']} | {body['label']} | "
                    f"Features: {body['feature_count']} | Tip: {tip}"
                )
            partdesign_box.setPlainText(
                f"PartDesign bodies: {partdesign['body_count']}\n" + "\n".join(lines)
            )
        else:
            partdesign_box.setPlainText("No PartDesign context.")
    if techdraw_box is not None:
        if techdraw["page_count"]:
            lines = []
            for page in techdraw["pages"][:6]:
                template = page["template"]["name"] if page["template"] else "none"
                lines.append(
                    f"{page['name']} | {page['label']} | "
                    f"Views: {page['view_count']} | Template: {template}"
                )
            techdraw_box.setPlainText(
                f"TechDraw pages: {techdraw['page_count']}\n" + "\n".join(lines)
            )
        else:
            techdraw_box.setPlainText("No TechDraw context.")
    if fem_box is not None:
        if fem["analysis_count"]:
            lines = []
            for analysis in fem["analyses"][:6]:
                lines.append(
                    f"{analysis['name']} | {analysis['label']} | "
                    f"Members: {analysis['member_count']}"
                )
            fem_box.setPlainText(
                f"FEM analyses: {fem['analysis_count']}\n" + "\n".join(lines)
            )
        else:
            fem_box.setPlainText("No FEM context.")
    if cam_box is not None:
        if cam["job_count"]:
            lines = []
            for job in cam["jobs"][:6]:
                operations = job["operations"]["object_count"] if job["operations"] else 0
                tools = job["tools"]["object_count"] if job["tools"] else 0
                lines.append(
                    f"{job['name']} | {job['label']} | "
                    f"Operations: {operations} | Tools: {tools}"
                )
            cam_box.setPlainText(
                f"CAM jobs: {cam['job_count']}\n" + "\n".join(lines)
            )
        else:
            cam_box.setPlainText("No CAM context.")
    if bim_box is not None:
        if bim["object_count"]:
            lines = []
            for obj in bim["objects"][:6]:
                ifc_type = obj["ifc_type"] or "Unclassified"
                lines.append(
                    f"{obj['name']} | {obj['label']} | "
                    f"IfcType: {ifc_type} | Children: {obj['child_count']}"
                )
            bim_box.setPlainText(
                f"BIM objects: {bim['object_count']}\n" + "\n".join(lines)
            )
        else:
            bim_box.setPlainText("No BIM context.")
    if assembly_box is not None:
        if assembly["assembly_count"]:
            lines = []
            for asm in assembly["assemblies"][:6]:
                lines.append(
                    f"{asm['name']} | {asm['label']} | "
                    f"Components: {asm['components']} | Joints: {asm['joints']}"
                )
            assembly_box.setPlainText(
                f"Assemblies: {assembly['assembly_count']}\n" + "\n".join(lines)
            )
        else:
            assembly_box.setPlainText("No Assembly context.")
    if inspection_box is not None:
        if inspection["feature_count"] or inspection["candidate_count"]:
            lines = [
                f"{item['name']} | {item['label']} | Actual: "
                f"{item['actual']['name'] if item.get('actual') else 'none'} | "
                f"Nominals: {item['nominal_count']}"
                for item in inspection["features"][:6]
            ]
            if not lines:
                lines = [
                    f"{item['name']} | {item['label']} | {item['type']}"
                    for item in inspection["candidates"][:6]
                ]
            inspection_box.setPlainText(
                f"Inspection features: {inspection['feature_count']} | "
                f"Candidates: {inspection['candidate_count']}\n" + "\n".join(lines)
            )
        else:
            inspection_box.setPlainText("No Inspection context.")
    if openscad_box is not None:
        if openscad["object_count"]:
            lines = []
            for item in openscad["objects"][:6]:
                detail = item.get("proxy_type") or item["type"]
                lines.append(f"{item['name']} | {item['label']} | {detail}")
            openscad_box.setPlainText(
                f"OpenSCAD objects: {openscad['object_count']} | "
                f"Executable: {'yes' if openscad['openscad_executable_configured'] else 'no'}\n"
                + "\n".join(lines)
            )
        else:
            openscad_box.setPlainText(
                "No OpenSCAD context. Executable: "
                + ("yes" if openscad["openscad_executable_configured"] else "no")
            )
    if surface_box is not None:
        if surface["object_count"]:
            lines = []
            for item in surface["objects"][:6]:
                detail = item.get("boundarylist", item.get("boundaryedges", item.get("nsections", 0)))
                lines.append(
                    f"{item['name']} | {item['label']} | {item['type']} | Refs: {detail}"
                )
            surface_box.setPlainText(
                f"Surface features: {surface['object_count']}\n" + "\n".join(lines)
            )
        else:
            surface_box.setPlainText("No Surface context.")
    if reen_box is not None:
        if reen["candidate_count"] or reen["reconstruction_count"]:
            lines = [
                f"{item['name']} | {item['label']} | {item['type']}"
                for item in reen["candidates"][:4]
            ]
            lines += [
                f"{item['name']} | {item['label']} | {item['type']} | Fit"
                for item in reen["reconstructions"][:4]
            ]
            reen_box.setPlainText(
                f"ReverseEngineering candidates: {reen['candidate_count']} | "
                f"Fits: {reen['reconstruction_count']}\n" + "\n".join(lines)
            )
        else:
            reen_box.setPlainText("No ReverseEngineering context.")
    if robot_box is not None:
        if robot["robot_count"] or robot["trajectory_count"]:
            lines = [
                f"{item['name']} | {item['label']} | Robot"
                for item in robot["robots"][:4]
            ]
            lines += [
                f"{item['name']} | {item['label']} | Waypoints: {item.get('waypoint_count', 0)}"
                for item in robot["trajectories"][:4]
            ]
            robot_box.setPlainText(
                f"Robots: {robot['robot_count']} | "
                f"Trajectories: {robot['trajectory_count']}\n" + "\n".join(lines)
            )
        else:
            robot_box.setPlainText("No Robot context.")
    if meshpart_box is not None:
        if meshpart["part_candidate_count"] or meshpart["mesh_count"]:
            lines = [
                f"{item['name']} | {item['label']} | {item['type']}"
                for item in meshpart["part_candidates"][:4]
            ]
            lines += [
                f"{item['name']} | {item['label']} | Facets: {item.get('mesh', {}).get('facets', 0)}"
                for item in meshpart["meshes"][:4]
            ]
            meshpart_box.setPlainText(
                f"MeshPart candidates: {meshpart['part_candidate_count']} | "
                f"Meshes: {meshpart['mesh_count']}\n" + "\n".join(lines)
            )
        else:
            meshpart_box.setPlainText("No MeshPart context.")

    active_workbench = service.active_workbench_name()
    active_contexts = {
        "AssemblyWorkbench": {assembly_box},
        "BIMWorkbench": {bim_box},
        "CAMWorkbench": {cam_box},
        "DraftWorkbench": {draft_box},
        "FemWorkbench": {fem_box},
        "InspectionWorkbench": {inspection_box},
        "MaterialWorkbench": {material_box},
        "MeshWorkbench": {mesh_box},
        "MeshPartWorkbench": {meshpart_box},
        "OpenSCADWorkbench": {openscad_box},
        "PartDesignWorkbench": {partdesign_box},
        "PartWorkbench": {part_box},
        "PointsWorkbench": {points_box},
        "ReverseEngineeringWorkbench": {reen_box},
        "RobotWorkbench": {robot_box},
        "SketcherWorkbench": {sketcher_box},
        "SpreadsheetWorkbench": {spreadsheet_box},
        "SurfaceWorkbench": {surface_box},
        "TechDrawWorkbench": {techdraw_box},
    }.get(active_workbench, set())
    for context_box in (
        part_box,
        mesh_box,
        points_box,
        material_box,
        sketcher_box,
        spreadsheet_box,
        draft_box,
        partdesign_box,
        techdraw_box,
        fem_box,
        cam_box,
        bim_box,
        assembly_box,
        inspection_box,
        openscad_box,
        surface_box,
        reen_box,
        robot_box,
        meshpart_box,
    ):
        if context_box is not None:
            is_active_context = context_box in active_contexts
            context_box.setProperty("VibeCADContextActive", is_active_context)
            context_box.setVisible(False)


def _apply_selected_action() -> None:
    action_id = _selected_action_id()
    if action_id is None:
        ids = _pending_action_ids()
        action_id = ids[0] if ids else None
    if action_id is None:
        _append_output("No pending action to approve.")
        _refresh_pending_actions()
        return
    result = get_service().apply_action(action_id)
    _append_output(f"Approved {action_id}:\n{result}")
    _refresh_pending_actions()
    _refresh_action_history()
    _refresh_workbench_context()


def _reject_selected_action() -> None:
    action_id = _selected_action_id()
    if action_id is None:
        ids = _pending_action_ids()
        action_id = ids[0] if ids else None
    if action_id is None:
        _append_output("No pending action to reject.")
        _refresh_pending_actions()
        return
    result = get_service().reject_action(action_id)
    _append_output(f"Rejected {action_id}:\n{result}")
    _refresh_pending_actions()
    _refresh_action_history()


def _revise_selected_action() -> None:
    try:
        from PySide import QtWidgets
    except Exception:
        return

    action_id = _selected_action_id()
    if action_id is None:
        ids = _pending_action_ids()
        action_id = ids[0] if ids else None
    if action_id is None:
        _append_output("No pending action to revise.")
        _refresh_pending_actions()
        return

    service = get_service()
    action = next(
        (
            item
            for item in service.pending_actions()["pending"]
            if item.get("id") == action_id
        ),
        None,
    )
    if action is None:
        _append_output(f"Pending action is no longer available: {action_id}")
        _refresh_pending_actions()
        return

    main_window = Gui.getMainWindow()
    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    prompt = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADPrompt") if dock else None
    if prompt is None:
        _append_output("VibeCAD prompt box is unavailable.")
        return

    metadata = action.get("metadata") or {}
    prompt.setPlainText(
        "Revise this pending VibeCAD action before I approve it.\n\n"
        f"Action ID: {action.get('id')}\n"
        f"Title: {action.get('title')}\n"
        f"Safety: {action.get('safety')}\n"
        f"Workbench: {action.get('workbench') or service.active_workbench_name() or 'none'}\n"
        f"Description: {action.get('description')}\n"
        f"Metadata: {json.dumps(metadata, sort_keys=True)}\n\n"
        "Keep the original action pending. Propose a replacement action that "
        "addresses this revision request: "
    )
    prompt.setFocus()
    _append_output(f"Loaded {action_id} into the prompt for revision.")


def _undo_last_vibecad_action() -> None:
    result = get_service().undo_last_vibecad_action()
    _append_output(f"Undo last VibeCAD action:\n{result}")
    _refresh_pending_actions()
    _refresh_action_history()
    _refresh_workbench_context()


def _clear_local_session_from_panel() -> None:
    try:
        from PySide import QtWidgets
    except Exception:
        return

    main_window = Gui.getMainWindow()
    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    result = get_service().clear_local_session()
    if dock is not None:
        output = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADOutput")
        prompt = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADPrompt")
        trace = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADToolTrace")
        if output is not None:
            output.clear()
        if prompt is not None:
            prompt.clear()
        if trace is not None:
            trace.setPlainText("No provider tool calls yet.")
    _set_screenshot_status(get_service().view_screenshot_summary())
    _refresh_pending_actions()
    _refresh_action_history()
    _refresh_workbench_context()
    _append_output(
        "Cleared local VibeCAD session: "
        f"{result['pending_count']} pending, {result['history_count']} history."
    )


def _configure_assistant_window(dock, main_window) -> None:
    try:
        from PySide import QtCore, QtWidgets
    except Exception:
        return

    dock.setAllowedAreas(QtCore.Qt.RightDockWidgetArea | QtCore.Qt.LeftDockWidgetArea)
    dock.setFeatures(
        QtWidgets.QDockWidget.DockWidgetClosable
        | QtWidgets.QDockWidget.DockWidgetMovable
        | QtWidgets.QDockWidget.DockWidgetFloatable
    )
    dock.setMinimumWidth(300)
    dock.setMaximumWidth(520)
    dock.setFloating(False)
    _place_assistant_like_task_panel(dock, main_window)


def _place_assistant_like_task_panel(dock, main_window) -> None:
    try:
        from PySide import QtCore, QtWidgets
    except Exception:
        return

    main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
    try:
        main_window.resizeDocks([dock], [360], QtCore.Qt.Horizontal)
    except Exception:
        pass
    dock.show()
    dock.raise_()


def _find_combo_or_task_dock(main_window):
    try:
        from PySide import QtWidgets
    except Exception:
        return None

    preferred_names = {
        "Combo View",
        "ComboView",
        "Task View",
        "TaskView",
        "Tasks",
        "Tree view",
        "TreeView",
    }
    docks = main_window.findChildren(QtWidgets.QDockWidget)
    for dock in docks:
        title = str(dock.windowTitle() or "")
        name = str(dock.objectName() or "")
        if title in preferred_names or name in preferred_names:
            return dock
    for dock in docks:
        title = str(dock.windowTitle() or "").lower()
        name = str(dock.objectName() or "").lower()
        if "combo" in title or "combo" in name or "task" in title or "task" in name:
            return dock
    return None


def _dock_is_in_overlay(dock) -> bool:
    try:
        parent = dock.parentWidget()
        while parent is not None:
            if "Overlay" in parent.metaObject().className():
                return True
            parent = parent.parentWidget()
    except Exception:
        return False
    return False


def _try_enable_freecad_overlay(dock) -> bool:
    try:
        from PySide import QtCore, QtWidgets
    except Exception:
        return False

    dock.show()
    dock.raise_()
    dock.setFocus(QtCore.Qt.OtherFocusReason)
    QtWidgets.QApplication.processEvents()
    title = dock.titleBarWidget()
    candidates = []
    if title is not None:
        candidates.extend(title.findChildren(QtCore.QObject))
    candidates.extend(dock.findChildren(QtCore.QObject))
    for item in candidates:
        action = item if hasattr(item, "trigger") else None
        if action is None:
            continue
        try:
            if str(action.data()) == "OBTN Overlay":
                action.trigger()
                QtWidgets.QApplication.processEvents()
                return _dock_is_in_overlay(dock)
        except Exception:
            continue
    return False


def _show_panel(text: str = "") -> None:
    try:
        from PySide import QtCore, QtWidgets
    except Exception:
        _print(text or "VibeCAD assistant panel requires Qt.")
        return

    main_window = Gui.getMainWindow()
    dock = main_window.findChild(QtWidgets.QDockWidget, "VibeCADAssistantPanel")
    if dock is None:
        dock = QtWidgets.QDockWidget("VibeCAD", main_window)
        dock.setObjectName("VibeCADAssistantPanel")
        widget = QtWidgets.QWidget(dock)
        layout = QtWidgets.QVBoxLayout(widget)
        status = QtWidgets.QLabel(widget)
        status.setObjectName("VibeCADStatus")
        status.setWordWrap(True)
        output = QtWidgets.QPlainTextEdit(widget)
        output.setObjectName("VibeCADOutput")
        output.setReadOnly(True)
        output.setPlainText(
            "Tell VibeCAD what to create, open, or modify. It can use the active "
            "workbench tools and assumes normal CAD defaults unless you specify them."
        )
        tool_pack = QtWidgets.QLabel(widget)
        tool_pack.setObjectName("VibeCADToolPack")
        tool_pack.setWordWrap(True)
        commands = QtWidgets.QPlainTextEdit(widget)
        commands.setObjectName("VibeCADWorkbenchCommands")
        commands.setReadOnly(True)
        commands.setFixedHeight(92)
        templates = QtWidgets.QPlainTextEdit(widget)
        templates.setObjectName("VibeCADObjectTemplates")
        templates.setReadOnly(True)
        templates.setFixedHeight(64)
        objects = QtWidgets.QPlainTextEdit(widget)
        objects.setObjectName("VibeCADWorkbenchObjects")
        objects.setReadOnly(True)
        objects.setFixedHeight(72)
        provider_tools = QtWidgets.QPlainTextEdit(widget)
        provider_tools.setObjectName("VibeCADProviderTools")
        provider_tools.setReadOnly(True)
        provider_tools.setFixedHeight(92)
        tool_trace = QtWidgets.QPlainTextEdit(widget)
        tool_trace.setObjectName("VibeCADToolTrace")
        tool_trace.setReadOnly(True)
        tool_trace.setFixedHeight(76)
        report_errors = QtWidgets.QPlainTextEdit(widget)
        report_errors.setObjectName("VibeCADReportErrors")
        report_errors.setReadOnly(True)
        report_errors.setFixedHeight(58)
        part = QtWidgets.QPlainTextEdit(widget)
        part.setObjectName("VibeCADPartContext")
        part.setReadOnly(True)
        part.setFixedHeight(64)
        mesh = QtWidgets.QPlainTextEdit(widget)
        mesh.setObjectName("VibeCADMeshContext")
        mesh.setReadOnly(True)
        mesh.setFixedHeight(64)
        points = QtWidgets.QPlainTextEdit(widget)
        points.setObjectName("VibeCADPointsContext")
        points.setReadOnly(True)
        points.setFixedHeight(64)
        material = QtWidgets.QPlainTextEdit(widget)
        material.setObjectName("VibeCADMaterialContext")
        material.setReadOnly(True)
        material.setFixedHeight(64)
        sketcher = QtWidgets.QPlainTextEdit(widget)
        sketcher.setObjectName("VibeCADSketcherContext")
        sketcher.setReadOnly(True)
        sketcher.setFixedHeight(52)
        spreadsheet = QtWidgets.QPlainTextEdit(widget)
        spreadsheet.setObjectName("VibeCADSpreadsheetContext")
        spreadsheet.setReadOnly(True)
        spreadsheet.setFixedHeight(52)
        draft = QtWidgets.QPlainTextEdit(widget)
        draft.setObjectName("VibeCADDraftContext")
        draft.setReadOnly(True)
        draft.setFixedHeight(64)
        partdesign = QtWidgets.QPlainTextEdit(widget)
        partdesign.setObjectName("VibeCADPartDesignContext")
        partdesign.setReadOnly(True)
        partdesign.setFixedHeight(64)
        techdraw = QtWidgets.QPlainTextEdit(widget)
        techdraw.setObjectName("VibeCADTechDrawContext")
        techdraw.setReadOnly(True)
        techdraw.setFixedHeight(64)
        fem = QtWidgets.QPlainTextEdit(widget)
        fem.setObjectName("VibeCADFemContext")
        fem.setReadOnly(True)
        fem.setFixedHeight(64)
        cam = QtWidgets.QPlainTextEdit(widget)
        cam.setObjectName("VibeCADCamContext")
        cam.setReadOnly(True)
        cam.setFixedHeight(64)
        bim = QtWidgets.QPlainTextEdit(widget)
        bim.setObjectName("VibeCADBimContext")
        bim.setReadOnly(True)
        bim.setFixedHeight(64)
        assembly = QtWidgets.QPlainTextEdit(widget)
        assembly.setObjectName("VibeCADAssemblyContext")
        assembly.setReadOnly(True)
        assembly.setFixedHeight(64)
        inspection = QtWidgets.QPlainTextEdit(widget)
        inspection.setObjectName("VibeCADInspectionContext")
        inspection.setReadOnly(True)
        inspection.setFixedHeight(64)
        openscad = QtWidgets.QPlainTextEdit(widget)
        openscad.setObjectName("VibeCADOpenSCADContext")
        openscad.setReadOnly(True)
        openscad.setFixedHeight(64)
        surface = QtWidgets.QPlainTextEdit(widget)
        surface.setObjectName("VibeCADSurfaceContext")
        surface.setReadOnly(True)
        surface.setFixedHeight(64)
        reen = QtWidgets.QPlainTextEdit(widget)
        reen.setObjectName("VibeCADReverseEngineeringContext")
        reen.setReadOnly(True)
        reen.setFixedHeight(64)
        robot = QtWidgets.QPlainTextEdit(widget)
        robot.setObjectName("VibeCADRobotContext")
        robot.setReadOnly(True)
        robot.setFixedHeight(64)
        meshpart = QtWidgets.QPlainTextEdit(widget)
        meshpart.setObjectName("VibeCADMeshPartContext")
        meshpart.setReadOnly(True)
        meshpart.setFixedHeight(64)
        for internal_widget in (
            commands,
            templates,
            objects,
            provider_tools,
            tool_trace,
            report_errors,
            part,
            mesh,
            points,
            material,
            sketcher,
            spreadsheet,
            draft,
            partdesign,
            techdraw,
            fem,
            cam,
            bim,
            assembly,
            inspection,
            openscad,
            surface,
            reen,
            robot,
            meshpart,
        ):
            internal_widget.setVisible(False)
        prompt = QtWidgets.QPlainTextEdit(widget)
        prompt.setObjectName("VibeCADPrompt")
        prompt.setPlaceholderText(
            "Create a centered 10 mm square sketch on the XY plane"
        )
        prompt.setFixedHeight(76)
        run_status = QtWidgets.QLabel("Ready.", widget)
        run_status.setObjectName("VibeCADRunStatus")
        screenshot_status = QtWidgets.QLabel(widget)
        screenshot_status.setObjectName("VibeCADScreenshotStatus")
        capture_view_button = QtWidgets.QPushButton("Capture View", widget)
        capture_view_button.setObjectName("VibeCADCaptureView")
        capture_view_button.clicked.connect(_capture_view_from_panel)
        controls = QtWidgets.QHBoxLayout()
        online = QtWidgets.QCheckBox("Use OpenAI", widget)
        online.setObjectName("VibeCADUseOnlineProvider")
        online.setChecked(get_service().use_online_provider_by_default())
        run_button = QtWidgets.QPushButton("Run", widget)
        run_button.setObjectName("VibeCADRunPrompt")
        run_button.clicked.connect(_run_prompt_from_panel)
        stop_button = QtWidgets.QPushButton("Stop", widget)
        stop_button.setObjectName("VibeCADStopPrompt")
        stop_button.setEnabled(False)
        stop_button.clicked.connect(_stop_prompt_from_panel)
        controls.addWidget(online)
        controls.addStretch(1)
        controls.addWidget(capture_view_button)
        controls.addWidget(run_button)
        controls.addWidget(stop_button)
        def add_labeled(parent_layout, label_text, child):
            label = QtWidgets.QLabel(label_text, widget)
            parent_layout.addWidget(label)
            parent_layout.addWidget(child)

        layout.addWidget(status)
        layout.addWidget(tool_pack)
        add_labeled(layout, "Conversation", output)
        layout.addWidget(screenshot_status)
        add_labeled(layout, "Prompt", prompt)
        layout.addWidget(run_status)
        layout.addLayout(controls)
        dock.setWidget(widget)
        main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
    _configure_assistant_window(dock, main_window)
    dock.show()
    dock.raise_()

    status = dock.findChild(QtWidgets.QLabel, "VibeCADStatus")
    output = dock.findChild(QtWidgets.QPlainTextEdit, "VibeCADOutput")
    service = get_service()
    auth = service.auth_state()
    if status is not None:
        workbench = service.active_workbench_name() or "none"
        status.setText(
            f"OpenAI: {_friendly_status(auth.status.value)}\n"
            f"Workbench: {_friendly_workbench(workbench)}"
        )
    if output is not None and text:
        output.setPlainText(text)
    _refresh_workbench_context()
    _refresh_pending_actions()
    _refresh_action_history()


def _on_workbench_activated(workbench_name: str) -> None:
    if get_tool_pack(str(workbench_name)) is None:
        return
    try:
        from PySide import QtCore
    except Exception:
        _show_panel()
        return
    QtCore.QTimer.singleShot(0, _show_panel)


def _connect_workbench_activation() -> None:
    global _workbench_activation_connected
    if _workbench_activation_connected:
        return
    try:
        main_window = Gui.getMainWindow()
        main_window.workbenchActivated.connect(_on_workbench_activated)
        _workbench_activation_connected = True
    except Exception as exc:
        App.Console.PrintWarning(
            f"VibeCAD AI assistant could not watch workbench activation: {exc}\n"
        )


def _wrap_workbench_activation(workbench: Any) -> None:
    if getattr(workbench, "__VibeCADActivatedWrapped__", False):
        return
    original = getattr(workbench, "Activated", None)

    def _activated_with_vibecad(*args: Any, **kwargs: Any) -> Any:
        result = None
        if callable(original):
            result = original(*args, **kwargs)
        try:
            active = get_service().active_workbench_name()
            if active:
                _on_workbench_activated(active)
        except Exception as exc:
            App.Console.PrintWarning(
                f"VibeCAD assistant could not open after workbench activation: {exc}\n"
            )
        return result

    setattr(workbench, "__VibeCADOriginalActivated__", original)
    setattr(workbench, "Activated", _activated_with_vibecad)
    setattr(workbench, "__VibeCADActivatedWrapped__", True)


class _BaseCommand:
    name = "VibeCAD"
    menu_text = "VibeCAD"
    tooltip = "VibeCAD AI command"

    def GetResources(self) -> dict[str, Any]:
        return {
            "Pixmap": "applications-python",
            "MenuText": self.menu_text,
            "ToolTip": self.tooltip,
        }

    def IsActive(self) -> bool:
        return True


class AskAICommand(_BaseCommand):
    menu_text = "Ask AI"
    tooltip = "Ask VibeCAD in the current workbench context"

    def Activated(self) -> None:
        service = get_service()
        response = run_prompt("Summarize the current FreeCAD context.", service=service)
        _show_panel(f"[{response.provider}] {response.final_output}")


class ExplainSelectionCommand(_BaseCommand):
    menu_text = "Explain Selection"
    tooltip = "Explain the current selection using VibeCAD context tools"

    def Activated(self) -> None:
        selection = get_service().selection_summary()
        _show_panel(f"Selection context:\n{selection}")


class OpenAssistantCommand(_BaseCommand):
    menu_text = "Open AI Assistant"
    tooltip = "Open the VibeCAD assistant panel for the active workbench"

    def Activated(self) -> None:
        _show_panel("VibeCAD assistant is ready for the active workbench.")


class OpenPreferencesCommand(_BaseCommand):
    menu_text = "AI Preferences"
    tooltip = "Open VibeCAD preferences"

    def Activated(self) -> None:
        ensure_preferences_registered()
        try:
            Gui.showPreferencesByName("VibeCAD", "VibeCAD")
        except Exception:
            try:
                Gui.showPreferences("VibeCAD", 0)
            except Exception as exc:
                _show_panel(f"VibeCAD preferences could not be opened: {exc}")


class AuthStatusCommand(_BaseCommand):
    menu_text = "AI Auth Status"
    tooltip = "Show VibeCAD authentication status"

    def Activated(self) -> None:
        auth = get_service().auth_state()
        source = f" from {auth.source}" if auth.source else ""
        _show_panel(f"VibeCAD auth status: {auth.status.value}{source}\n{auth.message}")


def ensure_preferences_registered() -> None:
    global _preferences_registered
    if _preferences_registered:
        return
    import VibeCADPreferences

    Gui.addIconPath(str(Path(__file__).resolve().parent))
    Gui.addPreferencePage(VibeCADPreferences.PreferencesPage, "VibeCAD")
    _preferences_registered = True


def ensure_commands_registered() -> None:
    global _commands_registered, _workbench_manipulator
    ensure_preferences_registered()
    if _commands_registered:
        _connect_workbench_activation()
        return
    Gui.addCommand("VibeCAD_AskAI", AskAICommand())
    Gui.addCommand("VibeCAD_ExplainSelection", ExplainSelectionCommand())
    Gui.addCommand("VibeCAD_OpenAssistant", OpenAssistantCommand())
    Gui.addCommand("VibeCAD_OpenPreferences", OpenPreferencesCommand())
    Gui.addCommand("VibeCAD_AuthStatus", AuthStatusCommand())
    _workbench_manipulator = _WorkbenchManipulator()
    Gui.addWorkbenchManipulator(_workbench_manipulator)
    _connect_workbench_activation()
    _commands_registered = True


def register_ai_commands_for_workbench(workbench: Any, workbench_name: str) -> None:
    """Attach shared VibeCAD commands to an existing workbench.

    This does not create or register a VibeCAD workbench. It adds native AI
    affordances to the workbench that called it.
    """

    ensure_commands_registered()
    _wrap_workbench_activation(workbench)
    native_workbench = getattr(workbench, "__Workbench__", None)
    if native_workbench is None:
        return

    try:
        native_workbench.appendToolbar("AI", COMMANDS)
        native_workbench.appendMenu(["AI"], COMMANDS)
        native_workbench.appendContextMenu("VibeCAD", CONTEXT_COMMANDS)
    except Exception as exc:
        App.Console.PrintWarning(
            f"VibeCAD could not attach AI UI to {workbench_name}: {exc}\n"
        )
