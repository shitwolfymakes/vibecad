# SPDX-License-Identifier: LGPL-2.1-or-later

"""Sketcher-native VibeCAD tool registration."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from VibeCADTools import SafetyLevel, VibeCADTool


TOOL_MODULE_NAMES = (
    "get_sketch",
    "create_sketch",
    "open_sketch",
    "close_sketch",
    "get_solver_status",
    "validate_profile",
    "validate_profile_deep",
    "diagnose_constraints",
    "list_geometry",
    "list_constraints",
    "resolve_geometry",
    "set_geometry_name",
    "list_reference_geometry",
    "list_external_geometry",
    "draw_rectangle",
    "add_line",
    "add_point",
    "add_polyline",
    "add_circle",
    "add_arc",
    "add_ellipse",
    "add_bspline",
    "add_slot",
    "add_constraint",
    "constrain_coincident",
    "constrain_horizontal",
    "constrain_vertical",
    "constrain_parallel",
    "constrain_perpendicular",
    "constrain_tangent",
    "constrain_equal",
    "constrain_distance",
    "constrain_distance_points",
    "constrain_distance_x",
    "constrain_distance_y",
    "constrain_angle_between",
    "constrain_lock_point",
    "constrain_block_geometry",
    "constrain_radius",
    "constrain_diameter",
    "constrain_point_on_object",
    "constrain_point_on_reference",
    "constrain_symmetric",
    "get_constraint_by_name",
    "set_constraint_name",
    "set_constraint_value",
    "set_constraint_value_by_name",
    "set_constraint_driving",
    "set_constraint_expression",
    "move_point",
    "transform_geometry",
    "copy_geometry",
    "rectangular_array",
    "mirror_geometry",
    "offset_geometry",
    "trim_geometry",
    "extend_geometry",
    "split_geometry",
    "fillet_corner",
    "add_external_geometry",
    "remove_external_geometry",
    "delete_geometry",
    "delete_constraint",
    "delete_all_geometry",
    "delete_all_constraints",
    "set_construction",
)


def register_tools(registry: Any, service: Any) -> None:
    for module_name in TOOL_MODULE_NAMES:
        module = import_module(f"{__name__}.{module_name}")
        spec = module.TOOL_SPEC
        safety_name = spec.get("safety", "SAFE_WRITE")
        description = spec["description"]
        if safety_name != "READ":
            description = (
                f"{description} Returns a normalized mutation payload with created, modified, "
                "deleted geometry/constraint indices, old-to-new index maps when applicable, "
                "full post-action Sketcher geometry/constraint summaries, solver status, and "
                "profile validation."
            )
        registry.register(
            VibeCADTool(
                name=spec["name"],
                description=description,
                handler=lambda _module=module, **kwargs: _module.run(service, **kwargs),
                safety=getattr(SafetyLevel, safety_name),
                workbench=spec.get("workbench", "SketcherWorkbench"),
                contextual=bool(spec.get("contextual", False)),
                parameters=spec.get("parameters", {"type": "object", "properties": {}}),
            )
        )
