# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service-backed VibeCAD tool registration.

Each module in this package owns one provider-visible tool shape and must expose
``run(service, **kwargs)``.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from VibeCADTools import SafetyLevel, VibeCADTool


TOOL_MODULE_NAMES = (
    'core_get_active_document',
    'core_get_selection',
    'core_get_view_state',
    'core_get_task_panel',
    'core_wait_for_user_gui_action',
    'core_capture_view_screenshot',
    'core_get_report_view_errors',
    'core_list_workbenches',
    'core_list_registered_commands',
    'core_list_active_workbench_commands',
    'core_get_tool_shape_report',
    'core_report_tool_shape_gap',
    'core_activate_workbench',
    'core_get_active_workbench_tool_pack',
    'core_list_workbench_tool_packs',
    'core_list_workbench_object_templates',
    'core_list_workbench_objects',
    'core_get_object_properties',
    'part_get_objects',
    'part_create_primitive',
    'part_set_placement',
    'part_set_primitive_dimensions',
    'part_cut_cylindrical_hole',
    'part_apply_fillet',
    'part_apply_chamfer',
    'part_apply_thickness',
    'draft_create_array',
    'mesh_get_objects',
    'points_get_objects',
    'material_get_objects',
    'material_apply_appearance',
    'core_run_workbench_command',
    'core_create_new_document',
    'core_open_document',
    'core_delete_object',
    'partdesign_create_body',
    'partdesign_create_sketch',
    'partdesign_create_datum_plane',
    'partdesign_create_datum_line',
    'partdesign_pad_sketch',
    'partdesign_pocket_sketch',
    'partdesign_hole_from_sketch',
    'partdesign_revolve_sketch',
    'partdesign_groove_sketch',
    'partdesign_fillet_feature',
    'partdesign_loft_profiles',
    'partdesign_sweep_profile',
    'partdesign_helix_profile',
    'partdesign_linear_pattern',
    'partdesign_polar_pattern',
    'partdesign_mirror_feature',
    'partdesign_chamfer_feature',
    'partdesign_thickness_feature',
    'partdesign_draft_feature',
    'partdesign_boolean_bodies',
    'partdesign_set_feature_dimensions',
    'spreadsheet_get_sheet',
    'draft_get_objects',
    'partdesign_get_bodies',
    'techdraw_get_pages',
    'techdraw_create_page',
    'techdraw_add_view',
    'fem_get_analyses',
    'cam_get_jobs',
    'bim_get_objects',
    'assembly_get_assemblies',
    'assembly_create_assembly',
    'assembly_add_component',
    'assembly_set_component_placement',
    'inspection_get_objects',
    'openscad_get_objects',
    'surface_get_objects',
    'reverseengineering_get_objects',
    'robot_get_objects',
    'meshpart_get_objects',
    'core_list_pending_actions',
    'core_apply_action',
    'core_reject_action',
    'core_undo_last_vibecad_action',
    'core_clear_local_session',
)


def register_tools(registry: Any, service: Any) -> None:
    for module_name in TOOL_MODULE_NAMES:
        module = import_module(f"{__name__}.{module_name}")
        spec = module.TOOL_SPEC
        module_run = getattr(module, "run", None)
        if not callable(module_run):
            raise ValueError(f"VibeCAD service tool module has no run(): {module_name}")
        handler = lambda _module=module, **kwargs: _module.run(service, **kwargs)
        registry.register(
            VibeCADTool(
                name=spec["name"],
                description=spec["description"],
                handler=handler,
                safety=getattr(SafetyLevel, spec["safety"]),
                workbench=spec.get("workbench"),
                contextual=bool(spec.get("contextual", False)),
                parameters=spec.get("parameters", {"type": "object", "properties": {}}),
            )
        )
