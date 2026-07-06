# SPDX-License-Identifier: LGPL-2.1-or-later

import json
from pathlib import Path
import tempfile

from VibeCADCore import (
    VibeCADService,
)
from VibeCADProvider import (
    ProviderUnavailable,
    OpenAIAgentsProvider,
)
from VibeCADSession import (
    make_provider_tool_runner,
    run_prompt,
)

from vibecad_tests.support import (
    SettingsSnapshotTestCase,
)


class TestVibeCADCoreMisc(SettingsSnapshotTestCase):
    def test_open_document_requirement_uses_successful_tool_trace(self):
        service = VibeCADService()
        runner = make_provider_tool_runner(service)
        with tempfile.TemporaryDirectory() as tmp:
            missing_path = Path(tmp) / "missing-model.FCStd"
            result = runner(
                "core.open_document",
                json.dumps({"file_path": str(missing_path)}),
            )
        self.assertFalse(result["ok"])
        self.assertFalse(
            make_provider_tool_runner(service)(
                "part.set_placement",
                '{"object_name": "NoSuchObject", "x": 0}',
            )["ok"]
        )

    def test_delete_object_removes_existing_object_for_iteration(self):
        import FreeCAD as App

        doc = App.newDocument("VibeCADDeleteObjectIterationTest")
        try:
            service = VibeCADService()
            box = doc.addObject("Part::Box", "WrongBlock")
            box.Label = "Wrong Block"
            doc.recompute()
            object_name = box.Name
            self.assertIsNotNone(doc.getObject(object_name))

            delete_result = service.registry.call(
                "core.delete_object",
                object_name="Wrong Block",
                reason="Replace with corrected geometry",
            )
            self.assertTrue(delete_result["ok"], delete_result)
            self.assertIsNone(doc.getObject(object_name))
            self.assertEqual(delete_result["before"]["object_count"], 1)
            self.assertEqual(delete_result["after"]["object_count"], 0)
        finally:
            App.closeDocument(doc.Name)

    def test_core_tool_descriptions_frame_fallback_and_cross_references(self):
        service = VibeCADService()

        def _description(tool_name):
            return str(service.registry.get(tool_name).to_schema().get("description", "")).lower()

        # run_workbench_command is explicitly framed as the fallback path.
        run_command = _description("core.run_workbench_command")
        self.assertIn("fallback", run_command)
        self.assertIn("no structured", run_command)
        self.assertIn("core.list_active_workbench_commands", run_command)

        # Discovery/read tools cross-reference their siblings.
        self.assertIn("core.run_workbench_command", _description("core.list_active_workbench_commands"))
        self.assertIn(
            "core.list_active_workbench_commands", _description("core.list_registered_commands")
        )
        self.assertIn("core.list_workbench_objects", _description("core.get_object_properties"))
        self.assertIn("core.delete_object", _description("core.undo_last_vibecad_action"))
        self.assertIn("core.undo_last_vibecad_action", _description("core.delete_object"))
        self.assertIn("techdraw.add_view", _description("techdraw.create_page"))
        self.assertIn("techdraw.create_page", _description("techdraw.add_view"))

        # Read-only utility tools stay tight: at most two sentences.
        for tool_name in (
            "core.get_active_document",
            "core.get_selection",
            "core.get_view_state",
            "core.get_task_panel",
            "core.get_report_view_errors",
            "core.list_workbenches",
            "core.capture_view_screenshot",
        ):
            description = str(service.registry.get(tool_name).to_schema().get("description", ""))
            sentence_count = description.count(". ") + 1
            self.assertLessEqual(sentence_count, 2, f"{tool_name}: {description}")
            self.assertLessEqual(len(description.split()), 30, f"{tool_name}: {description}")

    def test_run_prompt_rejects_empty_prompt(self):
        with self.assertRaises(ValueError):
            run_prompt(" ", service=VibeCADService(), prefer_online=False)

    def test_activate_workbench_reports_failure_without_gui(self):
        result = VibeCADService().activate_workbench("NoSuchWorkbench")
        self.assertIn("activated", result)
        self.assertIn("requested", result)

    def test_agents_provider_fails_cleanly_when_sdk_missing(self):
        try:
            import agents  # noqa: F401
        except Exception:
            with self.assertRaises(ProviderUnavailable):
                OpenAIAgentsProvider().run("hello", {})
