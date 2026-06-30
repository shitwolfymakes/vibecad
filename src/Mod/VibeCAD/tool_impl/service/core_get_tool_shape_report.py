# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``core.get_tool_shape_report``."""

from __future__ import annotations

from VibeCADTools import SafetyLevel


TOOL_SPEC = {'description': 'Explain provider-visible VibeCAD tools, capability coverage, and '
                'missing CAD tool classes that can make results too primitive.',
 'name': 'core.get_tool_shape_report',
 'parameters': {'properties': {'workbench': {'description': 'Optional workbench name. '
                                                            'Defaults to the active '
                                                            'workbench.',
                                             'type': 'string'}},
                'type': 'object'},
 'safety': 'READ'}


def run(service, **kwargs):
    from VibeCADSession import is_provider_safe_tool
    from . import core_list_active_workbench_commands

    active = kwargs.get("workbench") or _active_workbench_name()
    provider_tools = [
        service.registry.get(name).to_schema(active_workbench=active)
        for name in service.registry.names()
        if is_provider_safe_tool(service, name, active)
    ]
    provider_names = {tool["name"] for tool in provider_tools}
    all_registered = [service.registry.get(name) for name in service.registry.names()]
    registered_safe_write = sorted(tool.name for tool in all_registered if tool.safety is SafetyLevel.SAFE_WRITE)
    blocked_write = sorted(
        tool.name for tool in all_registered
        if tool.safety in {SafetyLevel.WRITE, SafetyLevel.DESTRUCTIVE}
    )
    thickness_tools = (
        {"partdesign.thickness_feature"}
        if active == "PartDesignWorkbench"
        else {"part.apply_thickness"}
    )
    capability_checks = {
        "document_lifecycle": {"core.create_new_document", "core.open_document"},
        "part_primitives": {"part.create_primitive"},
        "component_placement": {"part.set_placement"},
        "primitive_dimension_edits": {"part.set_primitive_dimensions"},
        "sketch_creation": {"partdesign.create_sketch"},
        "atomic_sketch_geometry": {"sketcher.add_line", "sketcher.add_circle", "sketcher.add_arc", "sketcher.add_slot"},
        "atomic_sketch_constraints": {"sketcher.add_constraint"},
        "sketch_rectangle_constraints": {"sketcher.draw_rectangle"},
        "sketch_dimension_edits": {"sketcher.set_constraint_value"},
        "partdesign_pad_features": {"partdesign.pad_sketch"},
        "partdesign_pocket_features": {"partdesign.pocket_sketch"},
        "partdesign_hole_features": {"partdesign.hole_from_sketch"},
        "partdesign_revolution_features": {"partdesign.revolve_sketch"},
        "partdesign_groove_features": {"partdesign.groove_sketch"},
        "partdesign_loft_features": {"partdesign.loft_profiles"},
        "partdesign_sweep_features": {"partdesign.sweep_profile"},
        "partdesign_helix_features": {"partdesign.helix_profile"},
        "partdesign_pattern_features": {"partdesign.linear_pattern", "partdesign.polar_pattern"},
        "partdesign_mirror_features": {"partdesign.mirror_feature"},
        "partdesign_datum_features": {"partdesign.create_datum_plane", "partdesign.create_datum_line"},
        "partdesign_draft_features": {"partdesign.draft_feature"},
        "partdesign_boolean_features": {"partdesign.boolean_bodies"},
        "partdesign_edge_finishing": {"partdesign.fillet_feature", "partdesign.chamfer_feature"},
        "partdesign_feature_dimension_edits": {"partdesign.set_feature_dimensions"},
        "iterative_delete": {"core.delete_object"},
        "holes_and_openings": {"part.cut_cylindrical_hole"},
        "shells_and_wall_thickness": thickness_tools,
        "edge_rounding": {"part.apply_fillet"},
        "edge_chamfering": {"part.apply_chamfer"},
        "material_appearance": {"material.apply_appearance"},
        "detail_drawings": {"techdraw.create_page", "techdraw.add_view"},
        "patterns_and_arrays": {"draft.create_array"},
        "assemblies": {"assembly.create_assembly"},
        "assembly_component_add": {"assembly.add_component"},
        "assembly_component_placement": {"assembly.set_component_placement"},
        "visual_feedback": {"core.capture_view_screenshot"},
        "report_errors": {"core.get_report_view_errors"},
        "user_gui_continuation": {"core.wait_for_user_gui_action"},
    }
    capability_checks.update(_sketcher_capability_checks())
    capability_status = {}
    for capability, required in capability_checks.items():
        capability_status[capability] = {
            "available": bool(required.issubset(provider_names)),
            "tools": sorted(required.intersection(provider_names)),
            "missing_tools": sorted(required.difference(provider_names)),
        }
    try:
        command_summary = core_list_active_workbench_commands.run(service, workbench=active)
    except Exception as exc:
        command_summary = {"error": str(exc), "commands": []}
    missing_capabilities = [
        name for name, status in capability_status.items() if not status["available"]
    ]
    sketcher_human_command_coverage = _sketcher_human_command_coverage(provider_names)
    still_missing_tool_classes = [
        item["tool_class"]
        for item in sketcher_human_command_coverage
        if item["coverage"] != "covered"
    ] + [
        "assembly constraints/joints and kinematic relationships",
        "tolerances, fastener libraries, BOM automation, and manufacturing checks",
        "automated semantic visual quality gates beyond provider screenshot judgment",
    ]
    return {
        "active_workbench": active,
        "tool_pack_enabled": service.is_workbench_tool_pack_enabled(active),
        "provider_tool_count": len(provider_tools),
        "provider_tools": provider_tools,
        "provider_tool_names": sorted(provider_names),
        "provider_primitive_tools_enabled": service.allow_primitive_provider_tools(),
        "recent_tool_shape_feedback": service._tool_shape_feedback[-10:],
        "registered_safe_write_tools": registered_safe_write,
        "blocked_write_tools": blocked_write,
        "capabilities": capability_status,
        "missing_capabilities": missing_capabilities,
        "sketcher_human_command_coverage": sketcher_human_command_coverage,
        "still_missing_tool_classes": still_missing_tool_classes,
        "human_workbench_command_count": len(command_summary.get("commands", []) or []),
        "human_workbench_command_sample": list(command_summary.get("commands", []) or [])[:80],
        "why_results_can_be_primitive": (
            "The provider can only create what appears in provider_tools. "
            "If a design needs one of still_missing_tool_classes, VibeCAD must either "
            "report the missing tool shape or the native tool surface must be expanded before it can reliably "
            "produce production-quality feature history."
        ),
    }


def _sketcher_capability_checks():
    return {
        "sketcher_profile_validation": {
            "sketcher.validate_profile",
            "sketcher.validate_profile_deep",
        },
        "sketcher_solver_diagnosis": {
            "sketcher.get_solver_status",
            "sketcher.diagnose_constraints",
        },
        "sketcher_geometry_listing": {
            "sketcher.list_geometry",
            "sketcher.resolve_geometry",
            "sketcher.list_reference_geometry",
        },
        "sketcher_constraint_listing": {
            "sketcher.list_constraints",
            "sketcher.get_constraint_by_name",
        },
        "sketcher_external_geometry": {
            "sketcher.list_external_geometry",
            "sketcher.add_external_geometry",
            "sketcher.remove_external_geometry",
        },
        "sketcher_named_geometry_and_constraints": {
            "sketcher.set_geometry_name",
            "sketcher.set_constraint_name",
            "sketcher.set_constraint_value_by_name",
        },
        "sketcher_point_editing": {
            "sketcher.move_point",
            "sketcher.transform_geometry",
            "sketcher.copy_geometry",
            "sketcher.rectangular_array",
            "sketcher.mirror_geometry",
            "sketcher.offset_geometry",
        },
        "sketcher_curve_editing": {
            "sketcher.trim_geometry",
            "sketcher.extend_geometry",
            "sketcher.split_geometry",
            "sketcher.fillet_corner",
        },
        "sketcher_delete_editing": {
            "sketcher.delete_geometry",
            "sketcher.delete_constraint",
            "sketcher.delete_all_geometry",
            "sketcher.delete_all_constraints",
        },
        "sketcher_construction_toggle": {"sketcher.set_construction"},
        "sketcher_detailed_constraints": {
            "sketcher.constrain_coincident",
            "sketcher.constrain_horizontal",
            "sketcher.constrain_vertical",
            "sketcher.constrain_parallel",
            "sketcher.constrain_perpendicular",
            "sketcher.constrain_tangent",
            "sketcher.constrain_equal",
            "sketcher.constrain_distance",
            "sketcher.constrain_distance_points",
            "sketcher.constrain_distance_x",
            "sketcher.constrain_distance_y",
            "sketcher.constrain_angle_between",
            "sketcher.constrain_lock_point",
            "sketcher.constrain_block_geometry",
            "sketcher.constrain_radius",
            "sketcher.constrain_diameter",
            "sketcher.constrain_point_on_object",
            "sketcher.constrain_point_on_reference",
            "sketcher.constrain_symmetric",
        },
    }


def _sketcher_human_command_coverage(provider_names):
    command_classes = [
        {
            "tool_class": "Sketcher create primitive/profile geometry",
            "representative_human_commands": [
                "Sketcher_CreateLine",
                "Sketcher_CreatePoint",
                "Sketcher_CreatePolyline",
                "Sketcher_CreateRectangle",
                "Sketcher_CreateCircle",
                "Sketcher_CreateArc",
                "Sketcher_CreateEllipse",
                "Sketcher_CreateBSpline",
                "Sketcher_CreateSlot",
            ],
            "provider_tools": [
                "sketcher.add_line",
                "sketcher.add_point",
                "sketcher.add_polyline",
                "sketcher.draw_rectangle",
                "sketcher.add_circle",
                "sketcher.add_arc",
                "sketcher.add_ellipse",
                "sketcher.add_bspline",
                "sketcher.add_slot",
            ],
            "desired_provider_tools": [],
        },
        {
            "tool_class": "Sketcher named constraints and value edits",
            "representative_human_commands": [
                "Sketcher_ConstrainDistance",
                "Sketcher_ConstrainDistanceX",
                "Sketcher_ConstrainDistanceY",
                "Sketcher_ConstrainRadius",
                "Sketcher_ConstrainDiameter",
                "Sketcher_ConstrainAngle",
            ],
            "provider_tools": sorted(_sketcher_capability_checks()["sketcher_detailed_constraints"]),
            "desired_provider_tools": [],
        },
        {
            "tool_class": "Sketcher solver diagnosis and profile validation",
            "representative_human_commands": [
                "Sketcher_SelectConflictingConstraints",
                "Sketcher_SelectRedundantConstraints",
                "Sketcher_SelectElementsWithDoFs",
            ],
            "provider_tools": [
                "sketcher.get_solver_status",
                "sketcher.diagnose_constraints",
                "sketcher.validate_profile",
                "sketcher.validate_profile_deep",
            ],
            "desired_provider_tools": [],
        },
        {
            "tool_class": "Sketcher curve repair and local editing",
            "representative_human_commands": [
                "Sketcher_Trimming",
                "Sketcher_Extend",
                "Sketcher_Split",
                "Sketcher_CreateFillet",
            ],
            "provider_tools": [
                "sketcher.trim_geometry",
                "sketcher.extend_geometry",
                "sketcher.split_geometry",
                "sketcher.fillet_corner",
            ],
            "desired_provider_tools": [],
        },
        {
            "tool_class": "Sketcher external/reference geometry",
            "representative_human_commands": [
                "Sketcher_External",
                "Sketcher_CarbonCopy",
            ],
            "provider_tools": [
                "sketcher.list_external_geometry",
                "sketcher.add_external_geometry",
                "sketcher.remove_external_geometry",
            ],
            "desired_provider_tools": ["sketcher.carbon_copy"],
        },
        {
            "tool_class": "Sketcher bulk transform and duplicate operations",
            "representative_human_commands": [
                "Sketcher_Copy",
                "Sketcher_Clone",
                "Sketcher_Move",
                "Sketcher_Translate",
                "Sketcher_Rotate",
                "Sketcher_Scale",
                "Sketcher_RectangularArray",
            ],
            "provider_tools": [
                "sketcher.move_point",
                "sketcher.transform_geometry",
                "sketcher.copy_geometry",
                "sketcher.rectangular_array",
            ],
            "desired_provider_tools": [
                "sketcher.clone_geometry",
            ],
        },
        {
            "tool_class": "Sketcher offset and derived-profile operations",
            "representative_human_commands": [
                "Sketcher_Offset",
                "Sketcher_Symmetry",
            ],
            "provider_tools": [
                "sketcher.constrain_symmetric",
                "sketcher.offset_geometry",
                "sketcher.mirror_geometry",
            ],
            "desired_provider_tools": [],
        },
        {
            "tool_class": "Sketcher B-spline advanced editing",
            "representative_human_commands": [
                "Sketcher_BSplineInsertKnot",
                "Sketcher_BSplineIncreaseDegree",
                "Sketcher_BSplineDecreaseDegree",
                "Sketcher_JoinCurves",
            ],
            "provider_tools": ["sketcher.add_bspline"],
            "desired_provider_tools": [
                "sketcher.bspline_insert_knot",
                "sketcher.bspline_set_degree",
                "sketcher.join_curves",
            ],
        },
        {
            "tool_class": "Sketcher text geometry",
            "representative_human_commands": ["Sketcher_CreateText"],
            "provider_tools": [],
            "desired_provider_tools": ["sketcher.add_text"],
        },
        {
            "tool_class": "Sketcher bulk deletion and cleanup",
            "representative_human_commands": [
                "Sketcher_DeleteAllGeometry",
                "Sketcher_DeleteAllConstraints",
                "Sketcher_RemoveAxesAlignment",
            ],
            "provider_tools": [
                "sketcher.delete_geometry",
                "sketcher.delete_constraint",
                "sketcher.delete_all_geometry",
                "sketcher.delete_all_constraints",
            ],
            "desired_provider_tools": [
                "sketcher.remove_axes_alignment",
            ],
        },
    ]
    coverage = []
    for item in command_classes:
        provider_tools = set(item["provider_tools"])
        desired_tools = set(item["desired_provider_tools"])
        present = sorted(provider_tools.intersection(provider_names))
        missing_existing = sorted(provider_tools.difference(provider_names))
        missing_desired = sorted(desired_tools.difference(provider_names))
        if not missing_existing and not missing_desired:
            status = "covered"
        elif present:
            status = "partial"
        else:
            status = "missing"
        coverage.append(
            {
                "tool_class": item["tool_class"],
                "coverage": status,
                "representative_human_commands": item["representative_human_commands"],
                "provider_tools": sorted(provider_tools),
                "available_provider_tools": present,
                "missing_existing_tools": missing_existing,
                "missing_desired_tools": missing_desired,
            }
        )
    return coverage


def _active_workbench_name():
    try:
        import FreeCADGui as Gui

        workbench = Gui.activeWorkbench()
        if workbench:
            return workbench.name()
    except Exception:
        pass
    return None
