# SPDX-License-Identifier: LGPL-2.1-or-later

"""Prompt/session orchestration for the VibeCAD assistant."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from typing import Any, Callable

from VibeCADCore import VibeCADService, get_service
from VibeCADProvider import BaseProvider, OfflineProvider, OpenAIAgentsProvider, ProviderUnavailable
from VibeCADTools import SafetyLevel

MAX_AUTONOMOUS_PROVIDER_TURNS: int | None = None
MAX_AUTONOMOUS_PROVIDER_SECONDS: float | None = None
MAX_MUTATING_TOOL_CALLS_PER_PROVIDER_TURN = 12
MAX_MUTATING_TOOL_CALLS_PER_PROVIDER_TURN_ENV = (
    "VIBECAD_MAX_MUTATING_TOOL_CALLS_PER_PROVIDER_TURN"
)
ProgressCallback = Callable[[dict[str, Any]], None]
CancellationCheck = Callable[[], bool]


@dataclass(frozen=True)
class VibeCADResponse:
    provider: str
    final_output: str
    context: dict[str, Any]
    tool_trace: list[dict[str, Any]]
    error: str | None = None


@dataclass(frozen=True)
class ProviderToolScope:
    workbench: str | None
    phase: str
    reason: str
    tool_names: set[str] | None = None


PROVIDER_SAFE_LEVELS = {
    SafetyLevel.READ,
    SafetyLevel.VIEW,
    SafetyLevel.SAFE_WRITE,
}

PROVIDER_COMMAND_WRITE_TOOLS = {
    "core.create_new_document",
    "core.open_document",
    "core.delete_object",
    "core.report_tool_shape_gap",
    "partdesign.create_body",
    "partdesign.create_sketch",
    "partdesign.create_datum_plane",
    "partdesign.create_datum_line",
    "partdesign.pad_sketch",
    "partdesign.pocket_sketch",
    "partdesign.hole_from_sketch",
    "partdesign.revolve_sketch",
    "partdesign.groove_sketch",
    "partdesign.loft_profiles",
    "partdesign.sweep_profile",
    "partdesign.helix_profile",
    "partdesign.linear_pattern",
    "partdesign.polar_pattern",
    "partdesign.mirror_feature",
    "partdesign.fillet_feature",
    "partdesign.chamfer_feature",
    "partdesign.thickness_feature",
    "partdesign.draft_feature",
    "partdesign.boolean_bodies",
    "partdesign.set_feature_dimensions",
    "part.create_primitive",
    "part.set_placement",
    "part.set_primitive_dimensions",
    "part.cut_cylindrical_hole",
    "part.apply_fillet",
    "part.apply_chamfer",
    "part.apply_thickness",
    "draft.create_array",
    "material.apply_appearance",
    "techdraw.create_page",
    "techdraw.add_view",
    "assembly.create_assembly",
    "assembly.add_component",
    "assembly.set_component_placement",
    "sketcher.create_sketch",
    "sketcher.open_sketch",
    "sketcher.close_sketch",
    "sketcher.set_geometry_name",
    "sketcher.set_constraint_name",
    "sketcher.set_constraint_value_by_name",
    "sketcher.set_constraint_driving",
    "sketcher.set_constraint_expression",
    "sketcher.add_external_geometry",
    "sketcher.remove_external_geometry",
    "sketcher.add_line",
    "sketcher.add_point",
    "sketcher.add_polyline",
    "sketcher.add_circle",
    "sketcher.add_arc",
    "sketcher.add_ellipse",
    "sketcher.add_bspline",
    "sketcher.add_slot",
    "sketcher.add_constraint",
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
    "sketcher.draw_rectangle",
    "sketcher.set_constraint_value",
    "sketcher.move_point",
    "sketcher.transform_geometry",
    "sketcher.copy_geometry",
    "sketcher.rectangular_array",
    "sketcher.mirror_geometry",
    "sketcher.offset_geometry",
    "sketcher.trim_geometry",
    "sketcher.extend_geometry",
    "sketcher.split_geometry",
    "sketcher.fillet_corner",
    "sketcher.delete_geometry",
    "sketcher.delete_constraint",
    "sketcher.delete_all_geometry",
    "sketcher.delete_all_constraints",
    "sketcher.set_construction",
}

PROVIDER_PRIMITIVE_WRITE_TOOLS = {
    "part.create_primitive",
    "part.set_placement",
    "part.set_primitive_dimensions",
    "part.cut_cylindrical_hole",
    "part.apply_fillet",
    "part.apply_chamfer",
    "part.apply_thickness",
}

PROVIDER_QUEUE_TOOLS = {
    "core.list_pending_actions",
    "core.apply_action",
    "core.reject_action",
    "core.undo_last_vibecad_action",
    "core.clear_local_session",
}

CORE_PROVIDER_TOOLS = {
    "core.get_active_document",
    "core.capture_view_screenshot",
    "core.get_report_view_errors",
    "core.get_tool_shape_report",
    "core.report_tool_shape_gap",
    "core.activate_workbench",
    "core.get_object_properties",
    "core.create_new_document",
    "core.open_document",
    "core.delete_object",
}

WORKBENCH_READ_TOOLS = {
    "PartDesignWorkbench": {"partdesign.get_bodies"},
    "SketcherWorkbench": {"sketcher.get_sketch"},
    "PartWorkbench": {"part.get_objects"},
    "AssemblyWorkbench": {"assembly.get_assemblies"},
    "TechDrawWorkbench": {"techdraw.get_pages"},
    "MaterialWorkbench": {"material.get_objects"},
}

SKETCHER_PARTDESIGN_BRIDGE_TOOLS = {
    "partdesign.pad_sketch",
    "partdesign.pocket_sketch",
    "partdesign.revolve_sketch",
    "partdesign.loft_profiles",
    "partdesign.sweep_profile",
}

PROVIDER_CONTEXT_CORE_TOOLS = {
    "core.get_active_document",
    "core.capture_view_screenshot",
    "core.get_report_view_errors",
    "core.get_tool_shape_report",
    "core.report_tool_shape_gap",
    "core.activate_workbench",
    "core.get_object_properties",
    "core.create_new_document",
    "core.open_document",
    "core.delete_object",
}

PROVIDER_CONTEXT_READ_TOOLS = {
    "core.get_active_document",
    "core.capture_view_screenshot",
    "core.get_report_view_errors",
    "core.get_tool_shape_report",
    "core.report_tool_shape_gap",
    "core.get_object_properties",
}

SKETCHER_INSPECT_TOOLS = {
    "sketcher.get_sketch",
    "sketcher.open_sketch",
    "sketcher.close_sketch",
    "sketcher.get_solver_status",
    "sketcher.validate_profile",
    "sketcher.validate_profile_deep",
    "sketcher.diagnose_constraints",
    "sketcher.list_geometry",
    "sketcher.list_constraints",
    "sketcher.resolve_geometry",
    "sketcher.set_geometry_name",
    "sketcher.set_constraint_name",
    "sketcher.set_constraint_value_by_name",
}

SKETCHER_STATUS_INSPECT_TOOLS = {
    "sketcher.get_sketch",
    "sketcher.close_sketch",
    "sketcher.get_solver_status",
    "sketcher.validate_profile",
    "sketcher.validate_profile_deep",
    "sketcher.diagnose_constraints",
    "sketcher.list_geometry",
    "sketcher.list_constraints",
    "sketcher.resolve_geometry",
}

SKETCHER_CREATE_TOOLS = {
    "sketcher.create_sketch",
    "sketcher.add_line",
    "sketcher.add_point",
    "sketcher.add_polyline",
    "sketcher.add_circle",
    "sketcher.add_arc",
    "sketcher.add_ellipse",
    "sketcher.add_bspline",
    "sketcher.add_slot",
    "sketcher.draw_rectangle",
}

SKETCHER_CONSTRAINT_TOOLS = {
    "sketcher.add_constraint",
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
    "sketcher.get_constraint_by_name",
    "sketcher.set_constraint_value",
    "sketcher.set_constraint_driving",
    "sketcher.set_constraint_expression",
}

SKETCHER_PROFILE_CLOSURE_CONSTRAINT_TOOLS = {
    "sketcher.add_constraint",
    "sketcher.constrain_coincident",
    "sketcher.constrain_horizontal",
    "sketcher.constrain_vertical",
    "sketcher.constrain_parallel",
    "sketcher.constrain_perpendicular",
    "sketcher.constrain_tangent",
    "sketcher.constrain_equal",
    "sketcher.constrain_point_on_object",
    "sketcher.constrain_point_on_reference",
    "sketcher.constrain_symmetric",
}

SKETCHER_EDIT_TOOLS = {
    "sketcher.move_point",
    "sketcher.transform_geometry",
    "sketcher.copy_geometry",
    "sketcher.rectangular_array",
    "sketcher.mirror_geometry",
    "sketcher.offset_geometry",
    "sketcher.trim_geometry",
    "sketcher.extend_geometry",
    "sketcher.split_geometry",
    "sketcher.fillet_corner",
    "sketcher.add_external_geometry",
    "sketcher.remove_external_geometry",
    "sketcher.delete_geometry",
    "sketcher.delete_constraint",
    "sketcher.delete_all_geometry",
    "sketcher.delete_all_constraints",
    "sketcher.set_construction",
}

SKETCHER_LOCAL_EDIT_TOOLS = {
    "sketcher.move_point",
    "sketcher.transform_geometry",
    "sketcher.delete_geometry",
    "sketcher.delete_constraint",
    "sketcher.delete_all_geometry",
    "sketcher.delete_all_constraints",
    "sketcher.set_construction",
}

SKETCHER_REPAIR_TOOLS = {
    "sketcher.trim_geometry",
    "sketcher.extend_geometry",
    "sketcher.split_geometry",
    "sketcher.fillet_corner",
    "sketcher.add_external_geometry",
    "sketcher.remove_external_geometry",
}

SKETCHER_DERIVED_EDIT_TOOLS = {
    "sketcher.copy_geometry",
    "sketcher.rectangular_array",
    "sketcher.mirror_geometry",
    "sketcher.offset_geometry",
}

SKETCHER_MINIMAL_CREATE_TOOLS = {
    "sketcher.add_line",
    "sketcher.add_point",
    "sketcher.add_circle",
    "sketcher.add_arc",
    "sketcher.add_slot",
    "sketcher.draw_rectangle",
}

PARTDESIGN_SETUP_TOOLS = {
    "partdesign.get_bodies",
    "partdesign.create_body",
    "partdesign.create_sketch",
    "partdesign.create_datum_plane",
    "partdesign.create_datum_line",
}

PARTDESIGN_FEATURE_TOOLS = {
    "partdesign.pad_sketch",
    "partdesign.pocket_sketch",
    "partdesign.hole_from_sketch",
    "partdesign.revolve_sketch",
    "partdesign.groove_sketch",
    "partdesign.loft_profiles",
    "partdesign.sweep_profile",
    "partdesign.helix_profile",
    "partdesign.linear_pattern",
    "partdesign.polar_pattern",
    "partdesign.mirror_feature",
    "partdesign.fillet_feature",
    "partdesign.chamfer_feature",
    "partdesign.thickness_feature",
    "partdesign.draft_feature",
    "partdesign.boolean_bodies",
    "partdesign.set_feature_dimensions",
}

PARTDESIGN_BASE_FEATURE_TOOLS = {
    "partdesign.pad_sketch",
    "partdesign.pocket_sketch",
    "partdesign.hole_from_sketch",
    "partdesign.revolve_sketch",
    "partdesign.groove_sketch",
    "partdesign.loft_profiles",
    "partdesign.sweep_profile",
}

PARTDESIGN_FEATURE_REVISION_TOOLS = {
    "partdesign.linear_pattern",
    "partdesign.polar_pattern",
    "partdesign.mirror_feature",
    "partdesign.fillet_feature",
    "partdesign.chamfer_feature",
    "partdesign.thickness_feature",
    "partdesign.draft_feature",
    "partdesign.boolean_bodies",
    "partdesign.set_feature_dimensions",
}

PARTDESIGN_ADVANCED_PROFILE_TOOLS = {
    "partdesign.loft_profiles",
    "partdesign.sweep_profile",
    "partdesign.helix_profile",
}

WORKBENCH_EXECUTION_CONTRACTS: dict[str, dict[str, Any]] = {
    "PartDesignWorkbench": {
        "mode": "parametric_partdesign",
        "required_order": [
            "create/select PartDesign body",
            "create sketch on a deliberate plane/support",
            "add native Sketcher geometry",
            "fully constrain sketch geometry and dimensions",
            "verify sketch DoF is 0 before pad/pocket/revolve/sweep/loft",
            "create native PartDesign features",
            "add requested detail features chosen by the model",
            "inspect document state and screenshot when visual judgement matters",
        ],
        "completion_gates": [
            "no sketch with geometry may remain under-constrained",
            "PartDesign solids require native PartDesign features, not Part primitive substitutes",
        ],
        "preferred_tools": [
            "partdesign.create_body",
            "partdesign.create_sketch",
            "partdesign.create_datum_plane",
            "partdesign.create_datum_line",
            "sketcher.open_sketch",
            "sketcher.close_sketch",
            "sketcher.get_solver_status",
            "sketcher.validate_profile",
            "sketcher.validate_profile_deep",
            "sketcher.diagnose_constraints",
            "sketcher.list_geometry",
            "sketcher.list_constraints",
            "sketcher.resolve_geometry",
            "sketcher.set_geometry_name",
            "sketcher.list_reference_geometry",
            "sketcher.list_external_geometry",
            "sketcher.add_line",
            "sketcher.add_point",
            "sketcher.add_polyline",
            "sketcher.add_circle",
            "sketcher.add_arc",
            "sketcher.add_ellipse",
            "sketcher.add_bspline",
            "sketcher.add_slot",
            "sketcher.draw_rectangle",
            "sketcher.add_constraint",
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
            "sketcher.get_constraint_by_name",
            "sketcher.set_constraint_name",
            "sketcher.set_constraint_value",
            "sketcher.set_constraint_value_by_name",
            "sketcher.set_constraint_driving",
            "sketcher.set_constraint_expression",
            "sketcher.move_point",
            "sketcher.transform_geometry",
            "sketcher.copy_geometry",
            "sketcher.rectangular_array",
            "sketcher.mirror_geometry",
            "sketcher.offset_geometry",
            "sketcher.trim_geometry",
            "sketcher.extend_geometry",
            "sketcher.split_geometry",
            "sketcher.fillet_corner",
            "sketcher.add_external_geometry",
            "sketcher.remove_external_geometry",
            "sketcher.delete_geometry",
            "sketcher.delete_constraint",
            "sketcher.delete_all_geometry",
            "sketcher.delete_all_constraints",
            "sketcher.set_construction",
            "partdesign.pad_sketch",
            "partdesign.pocket_sketch",
            "partdesign.hole_from_sketch",
            "partdesign.revolve_sketch",
            "partdesign.groove_sketch",
            "partdesign.loft_profiles",
            "partdesign.sweep_profile",
            "partdesign.helix_profile",
            "partdesign.linear_pattern",
            "partdesign.polar_pattern",
            "partdesign.mirror_feature",
            "partdesign.fillet_feature",
            "partdesign.chamfer_feature",
            "partdesign.thickness_feature",
            "partdesign.draft_feature",
            "partdesign.boolean_bodies",
            "partdesign.set_feature_dimensions",
        ],
    },
    "SketcherWorkbench": {
        "mode": "constrained_sketching",
        "required_order": [
            "create/select sketch",
            "inspect solver/profile state before and after edits",
            "add one or a small set of native geometry elements",
            "add geometric and dimensional constraints",
            "inspect geometry, constraints, profile status, and DoF",
            "iterate until the sketch is closed when a profile is needed and DoF is 0 unless intentionally construction-only",
        ],
        "completion_gates": [
            "requested dimensions must be constraints, not prose",
            "closed profile requests require closed_profile=true",
            "finished design sketches should be fully constrained",
        ],
        "preferred_tools": [
            "sketcher.create_sketch",
            "sketcher.open_sketch",
            "sketcher.close_sketch",
            "sketcher.get_solver_status",
            "sketcher.validate_profile",
            "sketcher.validate_profile_deep",
            "sketcher.diagnose_constraints",
            "sketcher.list_geometry",
            "sketcher.list_constraints",
            "sketcher.resolve_geometry",
            "sketcher.set_geometry_name",
            "sketcher.list_reference_geometry",
            "sketcher.list_external_geometry",
            "sketcher.add_line",
            "sketcher.add_point",
            "sketcher.add_polyline",
            "sketcher.add_circle",
            "sketcher.add_arc",
            "sketcher.add_ellipse",
            "sketcher.add_bspline",
            "sketcher.add_slot",
            "sketcher.draw_rectangle",
            "sketcher.add_constraint",
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
            "sketcher.get_constraint_by_name",
            "sketcher.set_constraint_name",
            "sketcher.set_constraint_value",
            "sketcher.set_constraint_value_by_name",
            "sketcher.set_constraint_driving",
            "sketcher.set_constraint_expression",
            "sketcher.move_point",
            "sketcher.transform_geometry",
            "sketcher.copy_geometry",
            "sketcher.rectangular_array",
            "sketcher.mirror_geometry",
            "sketcher.offset_geometry",
            "sketcher.trim_geometry",
            "sketcher.extend_geometry",
            "sketcher.split_geometry",
            "sketcher.fillet_corner",
            "sketcher.add_external_geometry",
            "sketcher.remove_external_geometry",
            "sketcher.delete_geometry",
            "sketcher.delete_constraint",
            "sketcher.delete_all_geometry",
            "sketcher.delete_all_constraints",
            "sketcher.set_construction",
        ],
    },
    "PartWorkbench": {
        "mode": "direct_solid_modeling",
        "required_order": [
            "create/select primitive or solid",
            "set exact dimensions and placement",
            "apply boolean/detail operations when requested",
            "inspect shape, bounds, volume, and visible result",
        ],
        "completion_gates": [
            "Part primitives are not substitutes for PartDesign when a parametric sketch-feature workflow is expected",
            "direct solids require verified dimensions and placement",
        ],
        "preferred_tools": [
            "part.create_primitive",
            "part.set_placement",
            "part.set_primitive_dimensions",
            "part.cut_cylindrical_hole",
            "part.apply_fillet",
            "part.apply_chamfer",
            "part.apply_thickness",
        ],
    },
    "AssemblyWorkbench": {
        "mode": "native_assembly",
        "required_order": [
            "verify component objects exist",
            "create native assembly",
            "add each component",
            "inspect assembly component count and screenshot when visual judgement matters",
        ],
        "completion_gates": [
            "assemblies require real generated components, not missing placeholders",
            "all requested components must be added to the assembly",
        ],
        "preferred_tools": [
            "assembly.create_assembly",
            "assembly.add_component",
            "assembly.set_component_placement",
        ],
    },
    "TechDrawWorkbench": {
        "mode": "drawing_documentation",
        "required_order": [
            "verify model objects exist",
            "create TechDraw page",
            "add views of target model objects",
            "inspect page/view objects",
        ],
        "completion_gates": [
            "TechDraw is downstream of model geometry",
            "drawing requests require page and view objects",
        ],
        "preferred_tools": [
            "techdraw.create_page",
            "techdraw.add_view",
        ],
    },
    "MaterialWorkbench": {
        "mode": "appearance_and_material_assignment",
        "required_order": [
            "verify target objects exist",
            "apply requested appearance/material",
            "inspect target object material/appearance state",
        ],
        "completion_gates": [
            "appearance requests require changed target objects",
        ],
        "preferred_tools": [
            "material.apply_appearance",
        ],
    },
}


def is_provider_safe_tool(service: VibeCADService, tool_name: str, workbench: str | None = None) -> bool:
    try:
        tool = service.registry.get(tool_name)
    except KeyError:
        return False
    allowlist = _provider_tool_allowlist_for_workbench(workbench)
    if allowlist is not None and tool_name not in allowlist:
        return False
    if tool.name in PROVIDER_QUEUE_TOOLS:
        return False
    if not is_provider_tool_kind_allowed(tool.safety, tool.name):
        return False
    if _is_primitive_tool_blocked(service, tool.name):
        return False
    return (
        _is_tool_available_for_provider_context(service, tool, workbench)
        and service.is_tool_enabled_for_provider(tool, workbench)
    )


def _provider_tool_allowlist_for_workbench(workbench: str | None) -> set[str] | None:
    if not workbench:
        return None
    contract = WORKBENCH_EXECUTION_CONTRACTS.get(workbench)
    if not contract:
        return None
    allowlist = set(CORE_PROVIDER_TOOLS)
    allowlist.update(WORKBENCH_READ_TOOLS.get(workbench, set()))
    allowlist.update(str(name) for name in contract.get("preferred_tools", []) or [])
    if workbench == "SketcherWorkbench":
        allowlist.update(SKETCHER_PARTDESIGN_BRIDGE_TOOLS)
    return allowlist


def is_provider_tool_kind_allowed(safety: SafetyLevel, tool_name: str) -> bool:
    return safety in {SafetyLevel.READ, SafetyLevel.VIEW} or (
        safety is SafetyLevel.SAFE_WRITE and tool_name in PROVIDER_COMMAND_WRITE_TOOLS
    )


def _is_primitive_tool_blocked(service: VibeCADService, tool_name: str) -> bool:
    return (
        tool_name in PROVIDER_PRIMITIVE_WRITE_TOOLS
        and not service.allow_primitive_provider_tools()
    )


def _is_partdesign_sketcher_tool(tool_name: str) -> bool:
    return tool_name in {
        "sketcher.get_sketch",
        "sketcher.open_sketch",
        "sketcher.close_sketch",
        "sketcher.get_solver_status",
        "sketcher.validate_profile",
        "sketcher.validate_profile_deep",
        "sketcher.diagnose_constraints",
        "sketcher.list_geometry",
        "sketcher.list_constraints",
        "sketcher.resolve_geometry",
        "sketcher.set_geometry_name",
        "sketcher.list_reference_geometry",
        "sketcher.list_external_geometry",
        "sketcher.add_line",
        "sketcher.add_point",
        "sketcher.add_polyline",
        "sketcher.add_circle",
        "sketcher.add_arc",
        "sketcher.add_ellipse",
        "sketcher.add_bspline",
        "sketcher.add_slot",
        "sketcher.add_constraint",
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
        "sketcher.draw_rectangle",
        "sketcher.get_constraint_by_name",
        "sketcher.set_constraint_name",
        "sketcher.set_constraint_value",
        "sketcher.set_constraint_value_by_name",
        "sketcher.set_constraint_driving",
        "sketcher.set_constraint_expression",
        "sketcher.move_point",
        "sketcher.transform_geometry",
        "sketcher.copy_geometry",
        "sketcher.rectangular_array",
        "sketcher.mirror_geometry",
        "sketcher.offset_geometry",
        "sketcher.trim_geometry",
        "sketcher.extend_geometry",
        "sketcher.split_geometry",
        "sketcher.fillet_corner",
        "sketcher.add_external_geometry",
        "sketcher.remove_external_geometry",
        "sketcher.delete_geometry",
        "sketcher.delete_constraint",
        "sketcher.delete_all_geometry",
        "sketcher.delete_all_constraints",
        "sketcher.set_construction",
    }


def _is_tool_available_for_provider_context(
    service: VibeCADService,
    tool: Any,
    workbench: str | None,
) -> bool:
    if tool.is_available_for(workbench):
        return True
    if workbench == "PartDesignWorkbench" and _is_partdesign_sketcher_tool(tool.name):
        return True
    if workbench == "SketcherWorkbench" and _is_sketcher_partdesign_feature_tool(tool.name):
        try:
            return bool(service.sketcher_summary().get("found"))
        except Exception:
            return False
    return False


def _is_sketcher_partdesign_feature_tool(tool_name: str) -> bool:
    return tool_name in {
        "partdesign.pad_sketch",
        "partdesign.pocket_sketch",
        "partdesign.revolve_sketch",
        "partdesign.loft_profiles",
        "partdesign.sweep_profile",
    }


def choose_provider(service: VibeCADService, prefer_online: bool = True) -> BaseProvider:
    auth = service.auth_state()
    if prefer_online and auth.can_call_provider:
        return OpenAIAgentsProvider(
            model=service.provider_model(),
            api_key=service.provider_api_key(),
            reasoning_effort=service.provider_reasoning_effort(),
        )
    return OfflineProvider()


def _run_provider_with_optional_cancellation(
    provider: BaseProvider,
    prompt: str,
    context: dict[str, Any],
    tool_runner: Callable[[str, str], dict[str, Any]],
    cancellation_check: CancellationCheck | None,
):
    try:
        return provider.run(
            prompt,
            context,
            tool_runner=tool_runner,
            cancellation_check=cancellation_check,
        )
    except TypeError as exc:
        if "cancellation_check" not in str(exc):
            raise
        return provider.run(prompt, context, tool_runner=tool_runner)


def run_prompt(
    prompt: str,
    service: VibeCADService | None = None,
    prefer_online: bool = True,
    provider: BaseProvider | None = None,
    progress_callback: ProgressCallback | None = None,
    max_provider_seconds: float | None = MAX_AUTONOMOUS_PROVIDER_SECONDS,
    enforce_small_steps: bool | None = None,
    cancellation_check: CancellationCheck | None = None,
) -> VibeCADResponse:
    clean_prompt = prompt.strip()
    if not clean_prompt:
        raise ValueError("Prompt cannot be empty.")

    active_service = service or get_service()
    _emit_progress(progress_callback, {"event": "context_build_started"})
    active_workbench = active_service.active_workbench_name()
    provider_workbench = _effective_provider_workbench(active_service, active_workbench)
    context = active_service.provider_context_summary()
    _apply_effective_provider_workbench(
        active_service,
        context,
        active_workbench,
        provider_workbench,
    )
    tool_trace: list[dict[str, Any]] = []
    visual_feedback_consumed = _context_has_satisfied_screenshot(context)
    context["vibecad_loop"] = _provider_loop_state(
        clean_prompt,
        context,
        tool_trace,
        turn=1,
        visual_feedback_consumed=visual_feedback_consumed,
    )
    _emit_progress(
        progress_callback,
        {
            "event": "context_build_completed",
            "workbench": context.get("workbench"),
            "active_workbench": active_workbench,
            "provider_tool_count": len(context["provider_tool_schemas"]),
            "next_step": context["vibecad_loop"]["next_step"],
            "remaining_outcomes": context["vibecad_loop"]["remaining_outcomes"],
        },
    )
    active_provider = provider or choose_provider(active_service, prefer_online=prefer_online)
    provider_name = active_provider.__class__.__name__
    small_step_checkpoints = (
        bool(enforce_small_steps)
        if enforce_small_steps is not None
        else isinstance(active_provider, OpenAIAgentsProvider)
    )
    tool_runner = make_provider_tool_runner(
        active_service,
        provider_workbench,
        tool_trace=tool_trace,
        progress_callback=progress_callback,
        turn_state={} if small_step_checkpoints else None,
        cancellation_check=cancellation_check,
    )
    started_at = time.monotonic()

    try:
        provider_prompt = _prompt_with_conversation(clean_prompt, context)
        outputs: list[str] = []
        turn_state = getattr(tool_runner, "_vibecad_turn_state", {})
        unresolved_turn_signature: tuple[Any, ...] | None = None
        unresolved_turn_repeat_count = 0
        turn_index = 0
        while True:
            if cancellation_check is not None and cancellation_check():
                _emit_progress(
                    progress_callback,
                    {
                        "event": "provider_run_cancelled",
                        "provider": provider_name,
                        "turn": turn_index + 1,
                        "tool_count": len(tool_trace),
                    },
                )
                outputs.append("VibeCAD run stopped by user.")
                break
            if _provider_time_exceeded(started_at, max_provider_seconds):
                outputs.append(
                    "The autonomous provider loop reached the configured "
                    f"{max_provider_seconds:g} second limit before completion."
                )
                _emit_progress(
                    progress_callback,
                    {
                        "event": "provider_total_timeout",
                        "provider": provider_name,
                        "turn": turn_index + 1,
                        "elapsed_seconds": time.monotonic() - started_at,
                        "tool_count": len(tool_trace),
                    },
                )
                break
            existing_loop_state = context.get("vibecad_loop")
            if not (
                isinstance(existing_loop_state, dict)
                and int(existing_loop_state.get("turn", 0) or 0) == turn_index + 1
            ):
                context["vibecad_loop"] = _provider_loop_state(
                    clean_prompt,
                    context,
                    tool_trace,
                    turn=turn_index + 1,
                    visual_feedback_consumed=visual_feedback_consumed,
                )
            _emit_progress(
                progress_callback,
                {
                    "event": "provider_turn_started",
                    "provider": provider_name,
                    "turn": turn_index + 1,
                    "tool_count": len(tool_trace),
                    "next_step": context["vibecad_loop"]["next_step"],
                    "remaining_outcomes": context["vibecad_loop"]["remaining_outcomes"],
                    "document_delta": context["vibecad_loop"].get("document_delta"),
                },
            )
            trace_count_before_turn = len(tool_trace)
            turn_started_with_visual_feedback = _context_has_satisfied_screenshot(context)
            if isinstance(turn_state, dict):
                turn_state["turn"] = turn_index + 1
                turn_state["mutating_tool_calls"] = 0
                turn_state["checkpoint_reached"] = False
                turn_state["workbench_switch_reached"] = False
            try:
                result = _run_provider_with_optional_cancellation(
                    active_provider,
                    provider_prompt,
                    context,
                    tool_runner,
                    cancellation_check,
                )
            except ProviderUnavailable as exc:
                if turn_started_with_visual_feedback:
                    visual_feedback_consumed = True
                _emit_progress(
                    progress_callback,
                    {
                        "event": "provider_turn_failed",
                        "provider": provider_name,
                        "turn": turn_index + 1,
                        "error": str(exc),
                        "tool_count": len(tool_trace),
                    },
                )
                if len(tool_trace) <= trace_count_before_turn:
                    raise
                outputs.append(
                    "The provider made partial FreeCAD changes but did not "
                    f"return a final answer before stopping: {exc}"
                )
                context = _refresh_provider_context(
                    active_service,
                    clean_prompt,
                    tool_trace,
                    turn_index + 2,
                    visual_feedback_consumed,
                    previous_context=context,
                )
                if not _should_continue_autonomously(
                    clean_prompt,
                    outputs[-1],
                    active_service,
                    tool_trace,
                    turn_index,
                    visual_feedback_consumed,
                ):
                    break
                provider_prompt = _continuation_prompt(
                    clean_prompt,
                    outputs,
                    context,
                    tool_trace,
                )
                turn_index += 1
                continue
            outputs.append(result.final_output)
            if turn_started_with_visual_feedback:
                visual_feedback_consumed = True
            post_turn_context = _refresh_provider_context(
                active_service,
                clean_prompt,
                tool_trace,
                turn_index + 2,
                visual_feedback_consumed,
                previous_context=context,
            )
            post_turn_missing = tuple(
                _missing_requirement_lines(clean_prompt, post_turn_context, tool_trace)
            )
            _emit_progress(
                progress_callback,
                {
                    "event": "provider_turn_completed",
                    "provider": provider_name,
                    "turn": turn_index + 1,
                    "tool_count": len(tool_trace),
                },
            )
            if (
                len(tool_trace) <= trace_count_before_turn
                and post_turn_missing
                and not (
                    not turn_started_with_visual_feedback
                    and _context_has_satisfied_screenshot(post_turn_context)
                )
            ):
                outputs.append(
                    "Stopping autonomous loop with partial progress because "
                    "the provider returned without using any FreeCAD tools while "
                    "verified requirements remain unresolved."
                )
                break
            if post_turn_missing:
                turn_tool_names = tuple(
                    str(item.get("tool_name", ""))
                    for item in tool_trace[trace_count_before_turn:]
                    if isinstance(item, dict)
                )
                unresolved_signature = (
                    post_turn_missing,
                    result.final_output.strip().lower(),
                    turn_tool_names,
                )
                if unresolved_signature == unresolved_turn_signature:
                    unresolved_turn_repeat_count += 1
                else:
                    unresolved_turn_signature = unresolved_signature
                    unresolved_turn_repeat_count = 1
                if unresolved_turn_repeat_count >= 3:
                    outputs.append(
                        "Stopping autonomous loop with partial progress because "
                        "the provider repeated the same tool sequence and response "
                        "while the same verified requirements remained unresolved."
                    )
                    context = post_turn_context
                    break
            else:
                unresolved_turn_signature = None
                unresolved_turn_repeat_count = 0
            if not _should_continue_autonomously(
                clean_prompt,
                result.final_output,
                active_service,
                tool_trace,
                turn_index,
                visual_feedback_consumed,
            ):
                break
            context = post_turn_context
            provider_prompt = _continuation_prompt(
                clean_prompt,
                outputs,
                context,
                tool_trace,
            )
            turn_index += 1
        raw_output = "\n\n".join(outputs)
        final_output = _verified_document_output(
            clean_prompt,
            active_service,
            raw_output,
            tool_trace,
            visual_feedback_consumed,
        ) or raw_output
        active_service.record_conversation_turn("user", clean_prompt)
        active_service.record_conversation_turn(
            "assistant",
            final_output,
            provider=provider_name,
            tool_trace=tool_trace,
        )
        return VibeCADResponse(
            provider=provider_name,
            final_output=final_output,
            context=context,
            tool_trace=tool_trace,
        )
    except ProviderUnavailable as exc:
        final_output = (
            f"{provider_name} failed before returning a usable AI result: {exc}"
        )
        active_service.record_conversation_turn("user", clean_prompt)
        active_service.record_conversation_turn(
            "assistant",
            final_output,
            provider=provider_name,
            tool_trace=tool_trace,
            metadata={"provider_error": str(exc)},
        )
        return VibeCADResponse(
            provider=provider_name,
            final_output=final_output,
            context=context,
            tool_trace=tool_trace,
            error=str(exc),
        )


def _refresh_provider_context(
    service: VibeCADService,
    prompt: str | None = None,
    tool_trace: list[dict[str, Any]] | None = None,
    turn: int = 1,
    visual_feedback_consumed: bool = False,
    previous_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_workbench = service.active_workbench_name()
    provider_workbench = _effective_provider_workbench(service, active_workbench)
    context = service.provider_context_summary()
    _apply_effective_provider_workbench(
        service,
        context,
        active_workbench,
        provider_workbench,
    )
    if prompt is not None:
        context["vibecad_loop"] = _provider_loop_state(
            prompt,
            context,
            tool_trace or [],
            turn=turn,
            visual_feedback_consumed=visual_feedback_consumed,
            previous_context=previous_context,
        )
    return context


def _effective_provider_workbench(
    service: VibeCADService,
    active_workbench: str | None,
) -> str | None:
    if active_workbench != "SketcherWorkbench":
        return active_workbench
    if not _active_sketch_is_partdesign_body_member(service):
        return active_workbench
    return "PartDesignWorkbench"


def _active_sketch_is_partdesign_body_member(service: VibeCADService) -> bool:
    try:
        sketcher = service.sketcher_summary()
        partdesign = service.partdesign_summary()
    except Exception:
        return False
    if not isinstance(sketcher, dict) or not sketcher.get("found"):
        return False
    sketch = sketcher.get("sketch")
    if not isinstance(sketch, dict):
        return False
    sketch_name = str(sketch.get("name") or "")
    sketch_label = str(sketch.get("label") or "")
    if not sketch_name and not sketch_label:
        return False
    bodies = partdesign.get("bodies", []) if isinstance(partdesign, dict) else []
    if not isinstance(bodies, list):
        return False
    for body in bodies:
        if not isinstance(body, dict):
            continue
        for feature in body.get("features", []) or []:
            if not isinstance(feature, dict):
                continue
            if sketch_name and feature.get("name") == sketch_name:
                return True
            if sketch_label and feature.get("label") == sketch_label:
                return True
    return False


def _apply_effective_provider_workbench(
    service: VibeCADService,
    context: dict[str, Any],
    active_workbench: str | None,
    provider_workbench: str | None,
) -> None:
    scope = provider_tool_scope_for_context(service, provider_workbench)
    schemas = provider_safe_tool_schemas(
        service,
        provider_workbench,
        tool_names=scope.tool_names,
    )
    full_schemas = provider_safe_tool_schemas(service, provider_workbench)
    context["active_workbench"] = active_workbench
    context["workbench"] = provider_workbench
    context["provider_tool_schemas"] = schemas
    context["provider_tool_schemas_workbench"] = provider_workbench
    context["provider_tool_scope"] = {
        "workbench": scope.workbench,
        "phase": scope.phase,
        "reason": scope.reason,
        "active_tool_count": len(schemas),
        "full_workbench_tool_count": len(full_schemas),
        "omitted_tool_count": max(0, len(full_schemas) - len(schemas)),
        "active_tool_names": [schema["name"] for schema in schemas],
    }
    context["provider_tool_surface"] = _provider_tool_surface_from_schemas(
        service,
        provider_workbench,
        schemas,
        full_tool_count=len(full_schemas),
        scope=context["provider_tool_scope"],
    )
    context["tool_shape_report"] = service.tool_shape_report(provider_workbench)
    if provider_workbench == "PartDesignWorkbench":
        context.update(
            {
                "partdesign": service.partdesign_summary(),
                "sketcher": service.sketcher_summary(),
                "material": service.material_summary(),
                "assembly": service.assembly_summary(),
            }
        )


def provider_tool_scope_for_context(
    service: VibeCADService,
    workbench: str | None,
) -> ProviderToolScope:
    if workbench == "SketcherWorkbench":
        return _sketcher_tool_scope_for_context(service, workbench)
    if workbench == "PartDesignWorkbench":
        return _partdesign_tool_scope_for_context(service, workbench)
    return ProviderToolScope(
        workbench=workbench,
        phase="workbench_default",
        reason="Use the full scoped tool surface for this workbench until phase routing is implemented.",
        tool_names=None,
    )


def _sketcher_tool_scope_for_context(
    service: VibeCADService,
    workbench: str | None,
) -> ProviderToolScope:
    try:
        sketcher = service.sketcher_summary()
    except Exception:
        sketcher = {}
    if not isinstance(sketcher, dict) or not sketcher.get("found"):
        return ProviderToolScope(
            workbench=workbench,
            phase="sketcher_no_active_sketch",
            reason="No active sketch is available; expose sketch creation/opening plus inspection tools.",
            tool_names=PROVIDER_CONTEXT_CORE_TOOLS
            | {
                "sketcher.get_sketch",
                "sketcher.create_sketch",
                "sketcher.open_sketch",
                "sketcher.list_reference_geometry",
                "sketcher.list_external_geometry",
            },
        )
    geometry_count = int(sketcher.get("geometry_count", 0) or 0)
    solver = sketcher.get("solver_status", {}) if isinstance(sketcher, dict) else {}
    degrees_of_freedom = None
    if isinstance(solver, dict):
        try:
            degrees_of_freedom = int(solver.get("degrees_of_freedom"))
        except Exception:
            degrees_of_freedom = None
    if geometry_count <= 0:
        return ProviderToolScope(
            workbench=workbench,
            phase="sketcher_geometry_authoring",
            reason="A sketch exists but has no geometry; expose primitive/profile creation and sketch inspection.",
            tool_names=PROVIDER_CONTEXT_READ_TOOLS
            | SKETCHER_STATUS_INSPECT_TOOLS
            | SKETCHER_CREATE_TOOLS
            | {
                "sketcher.list_reference_geometry",
                "sketcher.list_external_geometry",
                "sketcher.add_external_geometry",
                "sketcher.remove_external_geometry",
            },
        )
    profile = sketcher.get("profile_status", {}) if isinstance(sketcher, dict) else {}
    closed_profile = bool(profile.get("closed_profile")) if isinstance(profile, dict) else False
    if not closed_profile:
        return ProviderToolScope(
            workbench=workbench,
            phase="sketcher_profile_authoring",
            reason="A sketch has geometry but no closed profile; expose geometry continuation, profile repair, closure constraints, and inspection.",
            tool_names=PROVIDER_CONTEXT_READ_TOOLS
            | SKETCHER_STATUS_INSPECT_TOOLS
            | SKETCHER_CREATE_TOOLS
            | SKETCHER_REPAIR_TOOLS
            | SKETCHER_LOCAL_EDIT_TOOLS
            | SKETCHER_PROFILE_CLOSURE_CONSTRAINT_TOOLS,
        )
    if degrees_of_freedom is None or degrees_of_freedom > 0:
        return ProviderToolScope(
            workbench=workbench,
            phase="sketcher_constraint_solving",
            reason="A sketch has geometry and remaining degrees of freedom; expose constraints, minimal geometry continuation, local corrections, and inspection.",
            tool_names=PROVIDER_CONTEXT_READ_TOOLS
            | SKETCHER_STATUS_INSPECT_TOOLS
            | SKETCHER_CONSTRAINT_TOOLS
            | SKETCHER_LOCAL_EDIT_TOOLS
        )
    return ProviderToolScope(
        workbench=workbench,
        phase="sketcher_feature_or_revision",
        reason="The active sketch is fully constrained; expose validation, revision tools, and downstream feature tools.",
        tool_names=PROVIDER_CONTEXT_CORE_TOOLS
        | SKETCHER_INSPECT_TOOLS
        | SKETCHER_EDIT_TOOLS
        | SKETCHER_CONSTRAINT_TOOLS
        | SKETCHER_PARTDESIGN_BRIDGE_TOOLS,
    )


def _partdesign_tool_scope_for_context(
    service: VibeCADService,
    workbench: str | None,
) -> ProviderToolScope:
    try:
        partdesign = service.partdesign_summary()
    except Exception:
        partdesign = {}
    try:
        sketcher = service.sketcher_summary()
    except Exception:
        sketcher = {}
    bodies = partdesign.get("bodies", []) if isinstance(partdesign, dict) else []
    body_count = len(bodies) if isinstance(bodies, list) else 0
    sketch_found = bool(isinstance(sketcher, dict) and sketcher.get("found"))
    geometry_count = int(sketcher.get("geometry_count", 0) or 0) if isinstance(sketcher, dict) else 0
    profile = sketcher.get("profile_status", {}) if isinstance(sketcher, dict) else {}
    ready_for_feature = bool(
        isinstance(profile, dict)
        and (profile.get("ready_for_pad") or profile.get("ready_for_pocket"))
    )
    closed_profile = bool(profile.get("closed_profile")) if isinstance(profile, dict) else False
    degrees_of_freedom = None
    if isinstance(profile, dict):
        try:
            degrees_of_freedom = int(profile.get("degrees_of_freedom"))
        except Exception:
            degrees_of_freedom = None
    has_native_feature = _partdesign_has_native_feature(bodies)
    if body_count <= 0:
        return ProviderToolScope(
            workbench=workbench,
            phase="partdesign_setup",
            reason="No PartDesign body exists; expose body/sketch setup and document inspection.",
            tool_names=PROVIDER_CONTEXT_CORE_TOOLS | PARTDESIGN_SETUP_TOOLS,
        )
    if not sketch_found or geometry_count <= 0:
        return ProviderToolScope(
            workbench=workbench,
            phase="partdesign_sketch_authoring",
            reason="A PartDesign body exists but no active populated sketch exists; expose sketch creation and geometry authoring.",
            tool_names=PROVIDER_CONTEXT_READ_TOOLS
            | PARTDESIGN_SETUP_TOOLS
            | SKETCHER_STATUS_INSPECT_TOOLS
            | SKETCHER_CREATE_TOOLS,
        )
    if not closed_profile:
        return ProviderToolScope(
            workbench=workbench,
            phase="partdesign_profile_authoring",
            reason="A PartDesign sketch has geometry but no closed profile; expose profile creation, repair, closure constraints, and inspection.",
            tool_names=PROVIDER_CONTEXT_READ_TOOLS
            | PARTDESIGN_SETUP_TOOLS
            | SKETCHER_STATUS_INSPECT_TOOLS
            | SKETCHER_CREATE_TOOLS
            | SKETCHER_REPAIR_TOOLS
            | SKETCHER_LOCAL_EDIT_TOOLS
            | SKETCHER_PROFILE_CLOSURE_CONSTRAINT_TOOLS,
        )
    if not ready_for_feature or (degrees_of_freedom is not None and degrees_of_freedom > 0):
        return ProviderToolScope(
            workbench=workbench,
            phase="partdesign_constraint_solving",
            reason="A PartDesign sketch has a closed profile that is not feature-ready; expose constraints, local corrections, and inspection.",
            tool_names=PROVIDER_CONTEXT_READ_TOOLS
            | PARTDESIGN_SETUP_TOOLS
            | SKETCHER_STATUS_INSPECT_TOOLS
            | SKETCHER_CONSTRAINT_TOOLS
            | SKETCHER_LOCAL_EDIT_TOOLS,
        )
    if not has_native_feature:
        return ProviderToolScope(
            workbench=workbench,
            phase="partdesign_base_feature_creation",
            reason="A PartDesign sketch is feature-ready and the body has no native solid feature yet; expose native feature creation and inspection.",
            tool_names=PROVIDER_CONTEXT_READ_TOOLS
            | {"partdesign.get_bodies", "partdesign.create_sketch"}
            | SKETCHER_STATUS_INSPECT_TOOLS
            | PARTDESIGN_BASE_FEATURE_TOOLS,
        )
    return ProviderToolScope(
        workbench=workbench,
        phase="partdesign_feature_and_revision",
        reason="A PartDesign body already has native features; expose feature revision, additional feature creation, sketch setup, and inspection.",
        tool_names=PROVIDER_CONTEXT_READ_TOOLS
        | PARTDESIGN_SETUP_TOOLS
        | PARTDESIGN_BASE_FEATURE_TOOLS
        | PARTDESIGN_FEATURE_REVISION_TOOLS
        | PARTDESIGN_ADVANCED_PROFILE_TOOLS
        | SKETCHER_STATUS_INSPECT_TOOLS,
    )


def _partdesign_has_native_feature(bodies: Any) -> bool:
    if not isinstance(bodies, list):
        return False
    ignored_types = {
        "PartDesign::Body",
        "App::Origin",
        "PartDesign::Origin",
        "PartDesign::CoordinateSystem",
        "PartDesign::Plane",
        "PartDesign::Line",
        "PartDesign::Point",
        "Sketcher::SketchObject",
    }
    for body in bodies:
        if not isinstance(body, dict):
            continue
        for feature in body.get("features", []) or []:
            if not isinstance(feature, dict):
                continue
            feature_type = str(feature.get("type") or "")
            if feature_type.startswith("PartDesign::") and feature_type not in ignored_types:
                return True
    return False


def _provider_tool_surface_from_schemas(
    service: VibeCADService,
    workbench: str | None,
    schemas: list[dict[str, Any]],
    full_tool_count: int | None = None,
    scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "active_workbench": workbench,
        "tool_pack_enabled": service.is_workbench_tool_pack_enabled(workbench),
        "tool_count": len(schemas),
        "full_workbench_tool_count": full_tool_count if full_tool_count is not None else len(schemas),
        "scope": scope or {},
        "tools": schemas,
    }


def _provider_loop_state(
    prompt: str,
    context: dict[str, Any],
    tool_trace: list[dict[str, Any]],
    turn: int,
    visual_feedback_consumed: bool,
    previous_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    remaining = _missing_requirement_lines(prompt, context, tool_trace)
    recent_trace = [
        {
            "tool_name": item.get("tool_name"),
            "ok": bool(item.get("ok")),
            "active_workbench": item.get("active_workbench"),
            "result": item.get("result"),
        }
        for item in tool_trace[-12:]
        if isinstance(item, dict)
    ]
    document = context.get("document", {}) if isinstance(context, dict) else {}
    object_count = int(document.get("object_count", 0) or 0) if isinstance(document, dict) else 0
    screenshot = context.get("view_screenshot", {}) if isinstance(context, dict) else {}
    observation = screenshot.get("visual_observation") if isinstance(screenshot, dict) else None
    attention_flags = (
        list(observation.get("attention_flags") or [])
        if isinstance(observation, dict)
        else []
    )
    return {
        "turn": max(1, int(turn)),
        "mode": "autonomous_cad_operator",
        "execution_contract": _execution_contract_for_context(context),
        "max_mutating_tool_calls_per_turn": _max_mutating_tool_calls_per_provider_turn(),
        "next_step": _next_loop_step(remaining, object_count, bool(recent_trace)),
        "remaining_outcomes": remaining,
        "recent_tool_trace": recent_trace,
        "document_delta": _document_delta(previous_context, context),
        "document_object_count": object_count,
        "visual_feedback_consumed": bool(visual_feedback_consumed),
        "screenshot_captured": bool(isinstance(screenshot, dict) and screenshot.get("captured")),
        "visual_attention_flags": attention_flags,
        "instruction": (
            "Take one or a small set of intentional FreeCAD actions, inspect the "
            "returned state, and continue until remaining_outcomes is empty. "
            "The parent loop will checkpoint after a bounded number of mutating "
            "tool calls so state can be inspected before more edits. "
            "Do not ask the user unless the next action is impossible or destructive."
        ),
    }


def _execution_contract_for_context(context: dict[str, Any]) -> dict[str, Any]:
    workbench = context.get("workbench") if isinstance(context, dict) else None
    scope = context.get("provider_tool_scope", {}) if isinstance(context, dict) else {}
    contract = WORKBENCH_EXECUTION_CONTRACTS.get(str(workbench or ""))
    if contract is None:
        return {
            "mode": "generic_native_freecad",
            "active_tool_phase": scope.get("phase") if isinstance(scope, dict) else None,
            "active_tool_count": scope.get("active_tool_count") if isinstance(scope, dict) else None,
            "required_order": [
                "inspect active document/workbench state",
                "use only direct native function tools exposed for the current provider turn",
                "execute one or a small set of meaningful native operations",
                "inspect returned state before claiming progress or completion",
            ],
            "completion_gates": [
                "do not report completion from prose alone",
                "requested geometry must exist in the FreeCAD document",
            ],
            "preferred_tools": [],
        }
    return {
        "workbench": workbench,
        "mode": contract["mode"],
        "active_tool_phase": scope.get("phase") if isinstance(scope, dict) else None,
        "active_tool_scope_reason": scope.get("reason") if isinstance(scope, dict) else None,
        "active_tool_count": scope.get("active_tool_count") if isinstance(scope, dict) else None,
        "full_workbench_tool_count": scope.get("full_workbench_tool_count") if isinstance(scope, dict) else None,
        "required_order": list(contract["required_order"]),
        "completion_gates": list(contract["completion_gates"]),
        "available_tools_this_turn": (
            list(scope.get("active_tool_names") or [])
            if isinstance(scope, dict)
            else []
        ),
    }


def _next_loop_step(
    remaining: list[str],
    object_count: int,
    has_recent_trace: bool,
) -> str:
    if remaining:
        first = remaining[0].lstrip("- ").strip()
        return f"Resolve next verified gap: {first}"
    if object_count <= 0:
        return "Create the first meaningful FreeCAD object for the request."
    if not has_recent_trace:
        return "Inspect the current document, then make the first necessary edit."
    return "Verified requirements are satisfied; report the completed FreeCAD changes."


def _document_delta(
    previous_context: dict[str, Any] | None,
    current_context: dict[str, Any],
    limit: int = 12,
) -> dict[str, Any]:
    previous_objects = _document_object_map(previous_context)
    current_objects = _document_object_map(current_context)
    previous_keys = set(previous_objects)
    current_keys = set(current_objects)
    created_keys = sorted(current_keys.difference(previous_keys))
    deleted_keys = sorted(previous_keys.difference(current_keys))
    changed = []
    for key in sorted(previous_keys.intersection(current_keys)):
        before = previous_objects[key]
        after = current_objects[key]
        changed_fields = [
            field
            for field in ("label", "type", "placement", "bound_box", "shape", "material")
            if before.get(field) != after.get(field)
        ]
        if changed_fields:
            changed.append(
                {
                    "name": key,
                    "label": after.get("label") or key,
                    "fields": changed_fields,
                }
            )
    return {
        "available": previous_context is not None,
        "created": [
            _document_delta_item(current_objects[key], key)
            for key in created_keys[:limit]
        ],
        "deleted": [
            _document_delta_item(previous_objects[key], key)
            for key in deleted_keys[:limit]
        ],
        "changed": changed[:limit],
        "created_omitted": max(0, len(created_keys) - limit),
        "deleted_omitted": max(0, len(deleted_keys) - limit),
        "changed_omitted": max(0, len(changed) - limit),
        "before_object_count": len(previous_objects),
        "after_object_count": len(current_objects),
    }


def _document_object_map(context: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(context, dict):
        return {}
    document = context.get("document")
    if not isinstance(document, dict):
        return {}
    objects = document.get("objects")
    if not isinstance(objects, list):
        return {}
    mapped: dict[str, dict[str, Any]] = {}
    for item in objects:
        if not isinstance(item, dict):
            continue
        key = str(item.get("name") or item.get("label") or "").strip()
        if key:
            mapped[key] = {
                "name": item.get("name"),
                "label": item.get("label"),
                "type": item.get("type"),
                "placement": item.get("placement"),
                "bound_box": item.get("bound_box"),
                "shape": item.get("shape"),
                "material": item.get("material"),
            }
    return mapped


def _document_delta_item(item: dict[str, Any], key: str) -> dict[str, Any]:
    return {
        "name": item.get("name") or key,
        "label": item.get("label") or item.get("name") or key,
        "type": item.get("type"),
    }


def _format_document_delta(delta: Any) -> str:
    if not isinstance(delta, dict) or not delta.get("available"):
        return "not available before the first inspected turn"
    parts = []
    for key, label in (
        ("created", "created"),
        ("deleted", "deleted"),
        ("changed", "changed"),
    ):
        items = delta.get(key)
        if not isinstance(items, list) or not items:
            continue
        names = [
            str(item.get("label") or item.get("name") or item)
            if isinstance(item, dict)
            else str(item)
            for item in items[:8]
        ]
        omitted = int(delta.get(f"{key}_omitted", 0) or 0)
        suffix = f" (+{omitted} more)" if omitted else ""
        parts.append(f"{label}: {', '.join(names)}{suffix}")
    if not parts:
        return (
            "no object-level changes "
            f"({delta.get('before_object_count', 0)} -> {delta.get('after_object_count', 0)} objects)"
        )
    return "; ".join(parts)


def _prompt_with_conversation(prompt: str, context: dict[str, Any]) -> str:
    conversation_context = context.get("conversation", {})
    conversation = (
        conversation_context.get("conversation", [])
        if isinstance(conversation_context, dict)
        else []
    )
    if not conversation:
        return prompt
    scope = (
        conversation_context.get("scope", {})
        if isinstance(conversation_context, dict)
        else {}
    )
    scope_kind = str(scope.get("kind") or "document_scoped")
    document = scope.get("document")
    file_path = scope.get("file_path")
    scope_parts = [f"scope={scope_kind}"]
    if document:
        scope_parts.append(f"document={document}")
    if file_path:
        scope_parts.append(f"file={file_path}")
    lines = [
        "Use this prior VibeCAD conversation only as current document/project memory. "
        "It is scoped by VibeCAD conversation storage; do not treat unrelated documents, "
        "other files, or global chat history as relevant.",
        f"Conversation scope: {', '.join(scope_parts)}",
        "",
        "Conversation so far:",
    ]
    for item in conversation[-12:]:
        role = str(item.get("role", "unknown"))
        content = str(item.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    lines.extend(["", f"Current user request: {prompt}"])
    return "\n".join(lines)


def _continuation_prompt(
    prompt: str,
    outputs: list[str],
    context: dict[str, Any],
    tool_trace: list[dict[str, Any]],
) -> str:
    objects = context.get("document", {}).get("objects", [])
    object_lines = [
        f"- {item.get('label') or item.get('name')} ({item.get('type')})"
        for item in objects[-20:]
        if isinstance(item, dict)
    ]
    trace_lines = []
    for item in tool_trace[-20:]:
        if not isinstance(item, dict):
            continue
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        details = []
        if isinstance(result, dict):
            if result.get("checkpoint"):
                details.append(f"checkpoint={result.get('checkpoint')}")
            if result.get("error"):
                details.append(f"error={_trace_text(result.get('error'), 220)}")
            if result.get("required_next_action"):
                details.append(
                    "required_next_action="
                    + _trace_text(json.dumps(result.get("required_next_action"), default=str), 360)
                )
            elif result.get("next_action"):
                details.append(f"next_action={_trace_text(result.get('next_action'), 240)}")
        suffix = f" ({'; '.join(details)})" if details else ""
        trace_lines.append(
            f"- {item.get('tool_name')}: {'ok' if item.get('ok') else 'failed'}{suffix}"
        )
    missing_lines = _missing_requirement_lines(prompt, context, tool_trace)
    loop_state = context.get("vibecad_loop", {})
    loop_lines = []
    if isinstance(loop_state, dict):
        delta = loop_state.get("document_delta")
        contract = loop_state.get("execution_contract")
        loop_lines.extend(
            [
                f"- turn: {loop_state.get('turn')}",
                f"- next step: {loop_state.get('next_step')}",
                f"- document object count: {loop_state.get('document_object_count')}",
                f"- document delta: {_format_document_delta(delta)}",
                f"- screenshot captured: {loop_state.get('screenshot_captured')}",
                f"- visual feedback consumed: {loop_state.get('visual_feedback_consumed')}",
                f"- visual attention flags: {loop_state.get('visual_attention_flags', [])}",
            ]
        )
        if isinstance(contract, dict):
            loop_lines.append(f"- execution mode: {contract.get('mode')}")
            required_order = contract.get("required_order")
            if isinstance(required_order, list) and required_order:
                loop_lines.append(
                    "- required workflow order: "
                    + " -> ".join(str(item) for item in required_order)
                )
            completion_gates = contract.get("completion_gates")
            if isinstance(completion_gates, list) and completion_gates:
                loop_lines.append(
                    "- completion gates: "
                    + "; ".join(str(item) for item in completion_gates)
                )
    screenshot = context.get("view_screenshot", {})
    visual = screenshot.get("visual_observation", {}) if isinstance(screenshot, dict) else {}
    visual_lines = []
    if isinstance(visual, dict) and visual.get("available"):
        visual_lines.extend(
            [
                f"- captured: {bool(screenshot.get('captured'))}",
                f"- foreground ratio: {visual.get('foreground_pixel_ratio')}",
                f"- foreground bbox: {visual.get('foreground_bbox')}",
                f"- foreground bbox coverage: {visual.get('foreground_bbox_coverage')}",
                f"- foreground components: {visual.get('foreground_component_count')}",
                f"- largest component ratio: {visual.get('largest_component_pixel_ratio')}",
                f"- center offset: {visual.get('foreground_center_offset')}",
                f"- attention flags: {visual.get('attention_flags', [])}",
                f"- layout: {visual.get('layout_summary')}",
                f"- summary: {visual.get('inspection_summary')}",
            ]
        )
    elif isinstance(screenshot, dict) and screenshot.get("captured"):
        visual_lines.append("- screenshot captured, but no provider-readable visual observation is available")
    return "\n".join(
        [
            "Continue the same VibeCAD CAD job. Do not ask follow-up questions, "
            "do not stop at a plan, and do not report that work will happen later. "
            "Use best judgement, switch workbenches if needed, and create or modify "
            "real FreeCAD document objects with the direct function tools exposed "
            "to this provider turn.",
            "",
            f"Original user request: {prompt}",
            "",
            "Previous assistant output:",
            outputs[-1],
            "",
            "Recent tool trace:",
            "\n".join(trace_lines) or "- none",
            "",
            "Current deliberate loop state:",
            "\n".join(loop_lines) or "- unavailable",
            "",
            "Current document objects:",
            "\n".join(object_lines) or "- none",
            "",
            "Current viewport visual observation:",
            "\n".join(visual_lines) or "- no screenshot observation yet",
            "",
            "Remaining state-based outcomes:",
            "\n".join(missing_lines) or "- none detected from current FreeCAD state",
            "",
            "Continue now. If a tool failed, choose a different function tool or "
            "recover using the current document state.",
        ]
    )


def _should_continue_autonomously(
    prompt: str,
    output: str,
    service: VibeCADService,
    tool_trace: list[dict[str, Any]],
    turn_index: int,
    visual_feedback_consumed: bool = False,
) -> bool:
    if (
        MAX_AUTONOMOUS_PROVIDER_TURNS is not None
        and turn_index >= MAX_AUTONOMOUS_PROVIDER_TURNS - 1
    ):
        return False
    output_text = output.lower()
    doc_count = int(service.document_summary().get("object_count", 0) or 0)
    verified_state_satisfied = False
    try:
        if _missing_requirement_lines(prompt, service.provider_context_summary(), tool_trace):
            return True
        verified_state_satisfied = True
    except Exception:
        pass
    if verified_state_satisfied and doc_count > 0 and _provider_attempted_write(tool_trace):
        return False
    if _assistant_reported_checkpoint(output_text):
        return True
    if _assistant_stopped_without_finishing(output_text):
        return True
    if _active_sketch_or_task_requires_more_work(service):
        return True
    if _tool_batch_checkpoint_reached(tool_trace):
        return True
    if _assistant_asked_questions(output_text) and _provider_attempted_write(tool_trace):
        return True
    if doc_count == 0 and _provider_attempted_write(tool_trace):
        return True
    return False


def _verified_document_output(
    prompt: str,
    service: VibeCADService,
    raw_output: str,
    tool_trace: list[dict[str, Any]],
    visual_feedback_consumed: bool = False,
) -> str | None:
    summary = service.document_summary()
    object_count = int(summary.get("object_count", 0) or 0)
    if object_count <= 0:
        return None
    raw_text = raw_output.lower()
    should_replace = (
        "partial freecad changes" in raw_text
    ) or (
        "no geometry was created" in raw_text and object_count > 0
    )
    if not should_replace:
        return None
    objects = [
        item
        for item in summary.get("objects", [])
        if isinstance(item, dict)
    ]
    labels = [
        str(item.get("label") or item.get("name"))
        for item in objects[:12]
        if item.get("label") or item.get("name")
    ]
    lead = f"I made partial progress and verified {object_count} FreeCAD document objects were created."
    if labels:
        return lead + "\n\nCreated objects:\n" + "\n".join(f"- {label}" for label in labels)
    return lead


def _context_has_satisfied_screenshot(context: dict[str, Any]) -> bool:
    screenshot = context.get("view_screenshot", {})
    if not isinstance(screenshot, dict):
        return False
    return _screenshot_summary_is_visually_satisfied(screenshot)


def _screenshot_requirement_satisfied(service: VibeCADService) -> bool:
    try:
        summary = service.view_screenshot_summary()
    except Exception:
        return False
    return _screenshot_summary_is_visually_satisfied(summary)


def _screenshot_summary_is_visually_satisfied(summary: dict[str, Any]) -> bool:
    observation = summary.get("visual_observation")
    return (
        bool(summary.get("captured"))
        and int(summary.get("file_size", 0) or 0) > 0
        and isinstance(observation, dict)
        and bool(observation.get("available"))
        and not bool(observation.get("mostly_blank"))
        and not _visual_attention_flags(observation)
    )


def _visual_attention_flags(observation: dict[str, Any]) -> list[str]:
    raw_flags = observation.get("attention_flags", [])
    if not isinstance(raw_flags, list):
        return []
    return [
        str(flag)
        for flag in raw_flags
        if str(flag) in {
            "mostly_blank",
            "tiny_visible_model",
            "off_center_model",
            "model_fills_view_edges",
        }
    ]


def _native_partdesign_feature_count_from_context(context: dict[str, Any]) -> int:
    excluded = {
        "PartDesign::Body",
        "PartDesign::CoordinateSystem",
        "PartDesign::Origin",
    }
    partdesign = context.get("partdesign", {}) if isinstance(context, dict) else {}
    bodies = partdesign.get("bodies", []) if isinstance(partdesign, dict) else []
    count = 0
    if isinstance(bodies, list):
        for body in bodies:
            if not isinstance(body, dict):
                continue
            features = body.get("features", [])
            if not isinstance(features, list):
                continue
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                type_id = str(feature.get("type", ""))
                if type_id.startswith("PartDesign::") and type_id not in excluded:
                    count += 1
    if count:
        return count
    document = context.get("document", {}) if isinstance(context, dict) else {}
    objects = document.get("objects", []) if isinstance(document, dict) else []
    if not isinstance(objects, list):
        return 0
    return sum(
        1
        for item in objects
        if isinstance(item, dict)
        and str(item.get("type", "")).startswith("PartDesign::")
        and str(item.get("type", "")) not in excluded
    )


def _partdesign_body_count_from_context(context: dict[str, Any]) -> int:
    partdesign = context.get("partdesign", {}) if isinstance(context, dict) else {}
    if isinstance(partdesign, dict):
        body_count = partdesign.get("body_count")
        if body_count is not None:
            try:
                return max(0, int(body_count))
            except (TypeError, ValueError):
                pass
        bodies = partdesign.get("bodies", [])
        if isinstance(bodies, list) and bodies:
            return len([item for item in bodies if isinstance(item, dict)])
    document = context.get("document", {}) if isinstance(context, dict) else {}
    objects = document.get("objects", []) if isinstance(document, dict) else []
    if not isinstance(objects, list):
        return 0
    return sum(
        1
        for item in objects
        if isinstance(item, dict)
        and str(item.get("type", "")) == "PartDesign::Body"
    )


def _assembly_state_from_context(context: dict[str, Any]) -> tuple[int, int]:
    assembly = context.get("assembly", {}) if isinstance(context, dict) else {}
    if not isinstance(assembly, dict):
        return 0, 0
    try:
        assembly_count = max(0, int(assembly.get("assembly_count", 0) or 0))
    except (TypeError, ValueError):
        assembly_count = 0
    assemblies = assembly.get("assemblies", [])
    component_count = 0
    if isinstance(assemblies, list):
        for item in assemblies:
            if not isinstance(item, dict):
                continue
            for key in ("components", "component_count", "component_children_count"):
                if key not in item:
                    continue
                try:
                    component_count = max(component_count, int(item.get(key) or 0))
                except (TypeError, ValueError):
                    pass
            children = item.get("component_children")
            if isinstance(children, list):
                component_count = max(component_count, len(children))
    return assembly_count, component_count


def _missing_requirement_lines(
    prompt: str,
    context: dict[str, Any],
    tool_trace: list[dict[str, Any]],
) -> list[str]:
    lines = []
    objects = context.get("document", {}).get("objects", [])
    document = context.get("document", {})
    object_count = int(document.get("object_count", 0) or 0) if isinstance(document, dict) else 0
    if object_count <= 0:
        object_count = len(objects) if isinstance(objects, list) else 0
    if object_count <= 0 and _provider_attempted_write(tool_trace):
        return [
            "- create the first meaningful native FreeCAD geometry for the request "
            "using the active workbench tools before reporting completion"
        ]
    sketcher = context.get("sketcher", {}) if isinstance(context, dict) else {}
    profile_status = (
        sketcher.get("profile_status", {}) if isinstance(sketcher, dict) else {}
    )
    if isinstance(profile_status, dict) and profile_status.get("found"):
        geometry_count = int(profile_status.get("geometry_count", 0) or 0)
        if geometry_count > 0 and not profile_status.get("closed_profile"):
            sketch_name = profile_status.get("sketch") or "the active sketch"
            return [
                f"- finish {sketch_name} into a closed profile before reporting completion"
            ]
        if geometry_count > 0 and not profile_status.get("fully_constrained"):
            sketch_name = profile_status.get("sketch") or "the active sketch"
            dof = profile_status.get("degrees_of_freedom")
            suffix = f" ({dof} degrees of freedom)" if dof is not None else ""
            return [
                f"- fully constrain {sketch_name}{suffix} before creating dependent features"
            ]
        feature_types = {
            str(item.get("type", ""))
            for item in objects
            if isinstance(item, dict)
        }
        has_partdesign_feature = any(
            item_type.startswith("PartDesign::")
            and item_type not in {"PartDesign::Body", "PartDesign::CoordinateSystem"}
            for item_type in feature_types
        )
        if (
            geometry_count > 0
            and profile_status.get("closed_profile")
            and not has_partdesign_feature
        ):
            sketch_name = profile_status.get("sketch") or "the active sketch"
            return [
                f"- create a native PartDesign feature from {sketch_name} before reporting completion"
            ]
    body_count = _partdesign_body_count_from_context(context)
    if body_count >= 2:
        assembly_count, component_count = _assembly_state_from_context(context)
        if assembly_count <= 0:
            lines.append(
                "- multi-body component geometry exists but no native Assembly object exists; "
                "switch to AssemblyWorkbench, create a native assembly, and add the generated component bodies before reporting completion"
            )
        elif component_count < body_count:
            lines.append(
                "- native Assembly has fewer components than generated PartDesign bodies "
                f"({component_count}/{body_count}); add the remaining generated component bodies before reporting completion"
            )
    visual_lines: list[str] = []
    screenshot = context.get("view_screenshot", {})
    observation = screenshot.get("visual_observation") if isinstance(screenshot, dict) else None
    if isinstance(screenshot, dict) and screenshot.get("captured"):
        if not isinstance(observation, dict) or not observation.get("available"):
            visual_lines.append("- captured viewport screenshot has no provider-readable visual observation; capture again")
        elif observation.get("mostly_blank"):
            visual_lines.append("- viewport screenshot observation is mostly blank; fit/view the model and capture again")
        elif _visual_attention_flags(observation):
            flags = ", ".join(_visual_attention_flags(observation))
            visual_lines.append(
                "- viewport visual observation needs correction before completion "
                f"({flags}); revise/fit/organize the model, capture again, then inspect the new image"
            )
    if _needs_screenshot_after_latest_successful_write(tool_trace):
        visual_lines.append(
            "- capture and inspect a viewport screenshot after the latest geometry changes before reporting completion"
        )
    lines.extend(visual_lines)
    return lines


def _assistant_asked_questions(output_text: str) -> bool:
    return "?" in output_text or "please confirm" in output_text


def _assistant_stopped_without_finishing(output_text: str) -> bool:
    phrases = (
        "required next inspection",
        "next step after refresh",
        "next step after context refresh",
        "next step can",
        "next modeling steps",
        "next steps",
        "next i will",
        "then i will",
        "will be the",
        "will include",
        "started the",
        "i started",
        "created:",
        "to continue",
        "continue by",
        "i can design",
        "i can create",
        "i'm ready",
        "once the",
        "once tools",
        "once the tool",
        "could not",
        "cannot",
        "can't",
        "not currently",
        "not modified",
        "not actually",
        "not subtracting",
        "not cutting",
        "remained unchanged",
        "did not change",
        "didn't change",
        "ineffective",
        "attempted pockets",
        "can be recreated",
        "no document objects",
        "no objects were created",
        "tool bridge",
        "hit an internal",
        "before geometry could be generated",
        "please confirm",
        "please click",
        "please select",
        "i need",
    )
    return any(phrase in output_text for phrase in phrases)


def _assistant_reported_checkpoint(output_text: str) -> bool:
    checkpoint_phrases = (
        "progress checkpoint",
        "checkpoint progress",
        "checkpoint after",
        "requested a checkpoint",
        "checkpoint before",
        "checkpoint so the tool context can refresh",
        "workbench switch requires ending",
        "hit the vibecad",
        "vibecad requested",
    )
    return any(phrase in output_text for phrase in checkpoint_phrases)


def _active_sketch_or_task_requires_more_work(service: VibeCADService) -> bool:
    try:
        sketcher = service.sketcher_summary()
    except Exception:
        sketcher = {}
    profile_status = (
        sketcher.get("profile_status", {}) if isinstance(sketcher, dict) else {}
    )
    if isinstance(profile_status, dict) and profile_status.get("found"):
        geometry_count = int(profile_status.get("geometry_count", 0) or 0)
        if geometry_count > 0 and (
            not profile_status.get("closed_profile")
            or not profile_status.get("fully_constrained")
        ):
            return True
    return False


def _provider_attempted_write(tool_trace: list[dict[str, Any]]) -> bool:
    for item in tool_trace:
        if item.get("safety") == SafetyLevel.SAFE_WRITE.value:
            return True
    return False


def _needs_screenshot_after_latest_successful_write(
    tool_trace: list[dict[str, Any]],
) -> bool:
    latest_write_index = -1
    latest_screenshot_index = -1
    for index, item in enumerate(tool_trace):
        if not isinstance(item, dict) or not item.get("ok"):
            continue
        tool_name = str(item.get("tool_name") or "")
        if tool_name == "core.capture_view_screenshot":
            latest_screenshot_index = index
            continue
        if item.get("safety") == SafetyLevel.SAFE_WRITE.value:
            latest_write_index = index
    return latest_write_index >= 0 and latest_screenshot_index < latest_write_index


def _tool_batch_checkpoint_reached(tool_trace: list[dict[str, Any]]) -> bool:
    for item in reversed(tool_trace):
        result = item.get("result")
        if not isinstance(result, dict):
            continue
        if result.get("checkpoint") in {
            "small_step",
            "workbench_switch",
            "tool_surface_refresh",
        }:
            return True
        if result.get("status") == "deferred_checkpoint":
            return True
        error = str(result.get("error", "")).lower()
        if "small-step checkpoint" in error or "workbench-switch checkpoint" in error:
            return True
        if item.get("ok"):
            return False
    return False


def provider_safe_tool_schemas(
    service: VibeCADService,
    workbench: str | None = None,
    tool_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    schemas = []
    for tool_name in service.registry.names():
        if tool_names is not None and tool_name not in tool_names:
            continue
        if is_provider_safe_tool(service, tool_name, workbench):
            schemas.append(
                service.registry.get(tool_name).to_schema(active_workbench=workbench)
            )
    return schemas


def make_provider_tool_runner(
    service: VibeCADService,
    workbench: str | None = None,
    tool_trace: list[dict[str, Any]] | None = None,
    progress_callback: ProgressCallback | None = None,
    turn_state: dict[str, Any] | None = None,
    cancellation_check: CancellationCheck | None = None,
):
    enforce_small_step_checkpoint = turn_state is not None
    active_turn_state = turn_state if turn_state is not None else {}
    current_workbench = workbench

    def _run(tool_name: str, arguments_json: str = "{}") -> dict[str, Any]:
        nonlocal current_workbench
        actual_workbench = service.active_workbench_name()
        if actual_workbench:
            current_workbench = actual_workbench
        live_workbench = current_workbench or actual_workbench
        trace_entry: dict[str, Any] = {
            "tool_name": tool_name,
            "active_workbench": live_workbench,
            "arguments_json": _trace_text(arguments_json or "{}"),
            "ok": False,
        }
        if cancellation_check is not None and cancellation_check():
            result = {
                "ok": False,
                "error": "VibeCAD run stopped by user before executing tool.",
                "cancelled": True,
                "active_workbench": live_workbench,
            }
            _record_tool_trace(tool_trace, trace_entry, result, progress_callback)
            return result
        try:
            tool = service.registry.get(tool_name)
        except KeyError:
            result = {"ok": False, "error": f"Unknown VibeCAD tool: {tool_name}"}
            _record_tool_trace(tool_trace, trace_entry, result, progress_callback)
            return result

        trace_entry["safety"] = tool.safety.value
        trace_entry["tool_workbench"] = tool.workbench

        if not is_provider_tool_kind_allowed(tool.safety, tool.name):
            result = {
                "ok": False,
                "error": (
                    "Tool is not exposed to the AI loop because VibeCAD actions "
                    f"must drive human-equivalent FreeCAD commands: {tool_name}"
                ),
                "safety": tool.safety.value,
                "active_workbench": live_workbench,
                "tool_workbench": tool.workbench,
            }
            _record_tool_trace(tool_trace, trace_entry, result, progress_callback)
            return result

        if _is_primitive_tool_blocked(service, tool.name):
            result = {
                "ok": False,
                "error": (
                    "Part primitive write tools are disabled for the AI loop. "
                    "Use native PartDesign sketch/feature tools, or explicitly "
                    f"enable primitive provider tools before calling: {tool_name}"
                ),
                "active_workbench": live_workbench,
                "tool_workbench": tool.workbench,
                "opt_in_required": "AllowPrimitiveProviderTools",
            }
            _record_tool_trace(tool_trace, trace_entry, result, progress_callback)
            return result

        try:
            args = json.loads(arguments_json or "{}")
        except json.JSONDecodeError as exc:
            result = {"ok": False, "error": f"Invalid JSON arguments: {exc}"}
            _record_tool_trace(tool_trace, trace_entry, result, progress_callback)
            return result
        if not isinstance(args, dict):
            result = {"ok": False, "error": "Tool arguments must be a JSON object."}
            _record_tool_trace(tool_trace, trace_entry, result, progress_callback)
            return result

        if enforce_small_step_checkpoint and active_turn_state.get("workbench_switch_reached"):
            checkpoint_name = str(active_turn_state.get("deferred_checkpoint") or "workbench_switch")
            result = {
                "ok": True,
                "status": "deferred_checkpoint",
                "executed": False,
                "mutated_document": False,
                "active_workbench": live_workbench,
                "tool_workbench": tool.workbench,
                "checkpoint": checkpoint_name,
                "blocked_tool": tool_name,
                "blocked_arguments_json": _trace_text(arguments_json or "{}"),
                "recoverable": True,
                "required_next_action": {
                    "finish_current_turn": True,
                    "retry_tool_next_turn": tool_name,
                    "retry_arguments_json": _trace_text(arguments_json or "{}"),
                    "why": (
                        "VibeCAD paused before running this tool so the active "
                        "workbench tool surface can refresh."
                    ),
                },
                "turn": active_turn_state.get("turn"),
            }
            _record_tool_trace(tool_trace, trace_entry, result, progress_callback)
            _emit_progress(
                progress_callback,
                {
                    "event": "tool_workbench_switch_checkpoint_reached",
                    "tool_name": tool_name,
                    "active_workbench": live_workbench,
                    "turn": active_turn_state.get("turn"),
                },
            )
            return result

        if not _is_tool_available_in_live_context(service, tool, live_workbench):
            auto_switched = _try_auto_activate_tool_workbench(service, tool, live_workbench)
            if auto_switched:
                live_workbench = service.active_workbench_name()
                current_workbench = live_workbench
                trace_entry["active_workbench"] = live_workbench
                _emit_progress(
                    progress_callback,
                    {
                        "event": "tool_workbench_auto_activated",
                        "tool_name": tool_name,
                        "active_workbench": live_workbench,
                        "tool_workbench": tool.workbench,
                    },
                )
            if not _is_tool_available_in_live_context(service, tool, live_workbench):
                result = {
                    "ok": False,
                    "error": (
                        f"Tool is not available for the active workbench: {tool_name}"
                    ),
                    "active_workbench": live_workbench,
                    "tool_workbench": tool.workbench,
                    "recoverable": True,
                    "required_next_action": (
                        {
                            "tool": "core.activate_workbench",
                            "arguments": {"name": tool.workbench},
                            "then_retry_tool": tool_name,
                            "why": "Switch to the workbench that owns this human-equivalent FreeCAD tool.",
                        }
                        if tool.workbench
                        else None
                    ),
                }
                _record_tool_trace(tool_trace, trace_entry, result, progress_callback)
                return result

        if not service.is_tool_enabled_for_provider(tool, live_workbench):
            result = {
                "ok": False,
                "error": f"Tool pack is disabled for the active workbench: {tool_name}",
                "active_workbench": live_workbench,
                "tool_workbench": tool.workbench,
            }
            _record_tool_trace(tool_trace, trace_entry, result, progress_callback)
            return result

        if (
            enforce_small_step_checkpoint
            and _counts_toward_small_step_checkpoint(tool.name, tool.safety)
            and _mutating_tool_checkpoint_reached(active_turn_state)
        ):
            result = {
                "ok": True,
                "status": "deferred_checkpoint",
                "executed": False,
                "mutated_document": False,
                "active_workbench": live_workbench,
                "tool_workbench": tool.workbench,
                "checkpoint": "small_step",
                "blocked_tool": tool_name,
                "blocked_arguments_json": _trace_text(arguments_json or "{}"),
                "recoverable": True,
                "required_next_action": {
                    "finish_current_turn": True,
                    "retry_tool_next_turn": tool_name,
                    "retry_arguments_json": _trace_text(arguments_json or "{}"),
                    "inspect_first": ["core.get_active_document", "core.capture_view_screenshot"],
                },
                "turn": active_turn_state.get("turn"),
                "mutating_tool_calls": active_turn_state.get("mutating_tool_calls", 0),
                "limit": _max_mutating_tool_calls_per_provider_turn(),
            }
            active_turn_state["checkpoint_reached"] = True
            _record_tool_trace(tool_trace, trace_entry, result, progress_callback)
            _emit_progress(
                progress_callback,
                {
                    "event": "tool_batch_checkpoint_reached",
                    "tool_name": tool_name,
                    "active_workbench": live_workbench,
                    "turn": active_turn_state.get("turn"),
                    "mutating_tool_calls": active_turn_state.get("mutating_tool_calls", 0),
                    "limit": _max_mutating_tool_calls_per_provider_turn(),
                },
            )
            return result

        if enforce_small_step_checkpoint and _counts_toward_small_step_checkpoint(tool.name, tool.safety):
            active_turn_state["mutating_tool_calls"] = (
                int(active_turn_state.get("mutating_tool_calls", 0) or 0) + 1
            )

        try:
            if cancellation_check is not None and cancellation_check():
                result = {
                    "ok": False,
                    "error": "VibeCAD run stopped by user before executing tool.",
                    "cancelled": True,
                    "active_workbench": live_workbench,
                    "tool_workbench": tool.workbench,
                }
                _record_tool_trace(tool_trace, trace_entry, result, progress_callback)
                return result
            payload = service.registry.call(tool_name, **args)
            result = {
                "ok": not (isinstance(payload, dict) and payload.get("ok") is False),
                "result": payload,
            }
            if result["ok"] and tool_name == "core.activate_workbench":
                requested_workbench = str(args.get("name", "") or "").strip()
                if requested_workbench and requested_workbench != live_workbench:
                    current_workbench = requested_workbench
                    trace_entry["active_workbench"] = requested_workbench
                    result["checkpoint"] = "workbench_switch"
                    result["next_step"] = (
                        "Return progress now so VibeCAD can refresh provider "
                        f"function tools for {requested_workbench}."
                    )
                    result["required_next_action"] = {
                        "finish_current_turn": True,
                        "next_turn_workbench": requested_workbench,
                        "why": "Workbench-scoped tool lists are refreshed between provider turns.",
                    }
                    if enforce_small_step_checkpoint:
                        active_turn_state["workbench_switch_reached"] = True
                        active_turn_state["deferred_checkpoint"] = "workbench_switch"
                    _emit_progress(
                        progress_callback,
                        {
                            "event": "tool_workbench_switch_checkpoint_reached",
                            "tool_name": tool_name,
                            "active_workbench": requested_workbench,
                            "turn": active_turn_state.get("turn"),
                        },
                    )
            if result["ok"] and _tool_surface_refresh_checkpoint(tool_name):
                result_payload = result.get("result") if isinstance(result.get("result"), dict) else {}
                next_workbench, next_tools = _tool_surface_refresh_target(tool_name, result_payload)
                if next_workbench:
                    current_workbench = next_workbench
                    trace_entry["active_workbench"] = next_workbench
                    result["checkpoint"] = "tool_surface_refresh"
                    result["next_step"] = (
                        "Return progress now so VibeCAD can refresh provider "
                        f"function tools for {next_workbench}."
                    )
                    result["required_next_action"] = {
                        "finish_current_turn": True,
                        "next_turn_workbench": next_workbench,
                        "expected_tools": next_tools,
                        "why": (
                            "The active Sketcher edit/task state changed, so "
                            "the direct callable tool surface must refresh before "
                            "continuing native CAD operations."
                        ),
                    }
                    if enforce_small_step_checkpoint:
                        active_turn_state["workbench_switch_reached"] = True
                        active_turn_state["deferred_checkpoint"] = "tool_surface_refresh"
                    _emit_progress(
                        progress_callback,
                        {
                            "event": "tool_surface_refresh_checkpoint_reached",
                            "tool_name": tool_name,
                            "active_workbench": next_workbench,
                            "turn": active_turn_state.get("turn"),
                        },
                    )
            if (
                result["ok"]
                and enforce_small_step_checkpoint
                and _counts_toward_small_step_checkpoint(tool.name, tool.safety)
                and _mutating_tool_checkpoint_reached(active_turn_state)
            ):
                active_turn_state["checkpoint_reached"] = True
                result["checkpoint"] = "small_step"
                result["next_step"] = (
                    "Return concise progress now so VibeCAD can inspect the updated "
                    "document state before more edits."
                )
                result["required_next_action"] = {
                    "finish_current_turn": True,
                    "inspect_first": ["core.get_active_document", "core.capture_view_screenshot"],
                    "why": (
                        "A bounded batch of native FreeCAD mutations completed. "
                        "The parent loop will refresh context and continue if work remains."
                    ),
                }
                result["mutating_tool_calls"] = active_turn_state.get("mutating_tool_calls", 0)
                result["limit"] = _max_mutating_tool_calls_per_provider_turn()
                _emit_progress(
                    progress_callback,
                    {
                        "event": "tool_batch_checkpoint_reached",
                        "tool_name": tool_name,
                        "active_workbench": live_workbench,
                        "turn": active_turn_state.get("turn"),
                        "mutating_tool_calls": active_turn_state.get("mutating_tool_calls", 0),
                        "limit": _max_mutating_tool_calls_per_provider_turn(),
                    },
                )
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        _record_tool_trace(tool_trace, trace_entry, result, progress_callback)
        return result

    setattr(_run, "_vibecad_turn_state", active_turn_state)
    return _run


def _tool_surface_refresh_checkpoint(tool_name: str) -> bool:
    return tool_name in {
        "partdesign.create_sketch",
        "sketcher.create_sketch",
        "sketcher.open_sketch",
        "sketcher.close_sketch",
    }


def _tool_surface_refresh_target(tool_name: str, result: dict[str, Any]) -> tuple[str | None, list[str]]:
    if tool_name in {"partdesign.create_sketch", "sketcher.create_sketch", "sketcher.open_sketch"}:
        return (
            "SketcherWorkbench",
            [
                "sketcher.draw_rectangle",
                "sketcher.add_circle",
                "sketcher.add_line",
                "sketcher.add_polyline",
                "sketcher.close_sketch",
            ],
        )
    if tool_name == "sketcher.close_sketch":
        profile = result.get("profile_status") if isinstance(result, dict) else None
        if isinstance(profile, dict) and (
            profile.get("ready_for_pad") or profile.get("ready_for_pocket")
        ):
            return (
                "PartDesignWorkbench",
                [
                    "partdesign.pad_sketch",
                    "partdesign.pocket_sketch",
                    "partdesign.revolve_sketch",
                ],
            )
    return (None, [])


def _mutating_tool_checkpoint_reached(turn_state: dict[str, Any]) -> bool:
    count = int(turn_state.get("mutating_tool_calls", 0) or 0)
    return count >= _max_mutating_tool_calls_per_provider_turn()


def _max_mutating_tool_calls_per_provider_turn() -> int:
    raw = os.environ.get(MAX_MUTATING_TOOL_CALLS_PER_PROVIDER_TURN_ENV)
    if raw is not None and raw.strip():
        try:
            return max(1, int(raw))
        except ValueError:
            return MAX_MUTATING_TOOL_CALLS_PER_PROVIDER_TURN
    return MAX_MUTATING_TOOL_CALLS_PER_PROVIDER_TURN


def _counts_toward_small_step_checkpoint(tool_name: str, safety: SafetyLevel) -> bool:
    if safety is not SafetyLevel.SAFE_WRITE:
        return False
    return tool_name not in {
        "core.activate_workbench",
        "core.create_new_document",
        "core.open_document",
        "core.report_tool_shape_gap",
    }


def _provider_time_exceeded(started_at: float, max_provider_seconds: float | None) -> bool:
    return (
        max_provider_seconds is not None
        and max_provider_seconds > 0
        and time.monotonic() - started_at >= max_provider_seconds
    )


def _is_tool_available_in_live_context(
    service: VibeCADService,
    tool: Any,
    workbench: str | None,
) -> bool:
    if tool.is_available_for(workbench):
        return True
    if workbench == "PartDesignWorkbench" and _is_partdesign_sketcher_tool(tool.name):
        try:
            return tool.name == "sketcher.get_sketch" or bool(service.sketcher_summary().get("found"))
        except Exception:
            return False
    if tool.name in {"partdesign.pad_sketch", "partdesign.pocket_sketch", "partdesign.revolve_sketch"}:
        try:
            return bool(service.sketcher_summary().get("found"))
        except Exception:
            return False
    return False


def _try_auto_activate_tool_workbench(
    service: VibeCADService,
    tool: Any,
    current_workbench: str | None,
) -> bool:
    """Provider workbench changes must be explicit tool calls.

    Hidden activation makes the model's tool loop diverge from the human UI
    flow and leaves the next workbench-scoped tool surface stale.
    """
    return False
    return False


def _trace_text(value: Any, limit: int = 500) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _summary_value(value: Any, limit: int = 1200) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (dict, list)):
        text = json.dumps(value, default=str)
        if len(text) <= limit:
            return value
        return _trace_text(text, limit)
    return _trace_text(value, limit)


def _result_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"ok": bool(result.get("ok"))}
    for key in (
        "status",
        "error",
        "checkpoint",
        "blocked_tool",
        "blocked_arguments_json",
        "required_next_action",
        "next_action",
        "active_workbench",
        "tool_workbench",
        "recoverable",
        "executed",
        "mutated_document",
        "rolled_back_feature",
    ):
        if key in result:
            summary[key] = _summary_value(result[key])
    payload = result.get("result")
    if isinstance(payload, dict):
        for key in (
            "id",
            "title",
            "status",
            "safety",
            "active_workbench",
            "workbench",
            "assembly",
            "assembly_label",
            "component",
            "component_label",
            "components",
            "components_added",
            "missing_components",
            "already_present",
            "assembly_summary",
            "active_body",
            "active_sketch",
            "active_feature",
            "next_action",
            "required_next_action",
            "profile_status",
            "next_actions",
            "feature_shape",
            "body_shape_before",
            "body_shape_after",
            "body_shape_delta",
            "feature_effect",
            "rolled_back_feature",
            "body_shape_after_rollback",
            "recoverable",
            "error",
        ):
            if key in payload:
                summary[key] = _summary_value(payload[key])
    transaction = result.get("transaction")
    if not isinstance(transaction, dict) and isinstance(payload, dict):
        transaction = payload.get("transaction")
    if isinstance(transaction, dict):
        for key in ("error", "verification", "report_view_errors", "document_delta"):
            if key in transaction:
                summary[f"transaction_{key}"] = _summary_value(transaction[key])
    return summary


def _record_tool_trace(
    tool_trace: list[dict[str, Any]] | None,
    trace_entry: dict[str, Any],
    result: dict[str, Any],
    progress_callback: ProgressCallback | None = None,
) -> None:
    entry = dict(trace_entry)
    entry["ok"] = bool(result.get("ok"))
    entry["result"] = _result_summary(result)
    if tool_trace is not None:
        tool_trace.append(entry)
    _emit_progress(
        progress_callback,
        {
            "event": "tool_call_completed",
            "tool_name": entry.get("tool_name"),
            "ok": entry.get("ok"),
            "result": entry.get("result"),
            "active_workbench": entry.get("active_workbench"),
            "safety": entry.get("safety"),
        },
    )


def _emit_progress(
    progress_callback: ProgressCallback | None,
    event: dict[str, Any],
) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(dict(event))
    except Exception:
        return
