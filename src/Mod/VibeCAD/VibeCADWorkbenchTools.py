# SPDX-License-Identifier: LGPL-2.1-or-later

"""Workbench-specific VibeCAD tool-pack metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkbenchToolPack:
    workbench: str
    domain: str
    instructions: str
    command_prefixes: tuple[str, ...]
    object_types: tuple[str, ...] = ()
    object_templates: tuple[dict[str, str], ...] = ()

    def summary(self) -> dict[str, object]:
        return {
            "workbench": self.workbench,
            "domain": self.domain,
            "instructions": self.instructions,
            "command_prefixes": list(self.command_prefixes),
            "object_types": list(self.object_types),
            "object_templates": list(self.object_templates),
        }


WORKBENCH_TOOL_PACKS: dict[str, WorkbenchToolPack] = {
    "AssemblyWorkbench": WorkbenchToolPack(
        "AssemblyWorkbench",
        "assembly constraints and product structure",
        "Prefer assembly-aware inspection and joint commands before changing geometry.",
        ("Assembly_",),
        ("Assembly::AssemblyObject",),
        ({"name": "assembly", "object_type": "Assembly::AssemblyObject"},),
    ),
    "BIMWorkbench": WorkbenchToolPack(
        "BIMWorkbench",
        "building information modeling",
        "Preserve IFC/BIM semantics and prefer non-destructive inspection when IFC support is unavailable.",
        ("BIM_", "Arch_", "Draft_"),
        ("Arch::", "BIM::"),
        (
            {"name": "building", "object_type": "App::DocumentObjectGroup"},
            {"name": "level", "object_type": "App::DocumentObjectGroup"},
        ),
    ),
    "CAMWorkbench": WorkbenchToolPack(
        "CAMWorkbench",
        "toolpaths and manufacturing setup",
        "Treat CAM operations as high-risk until verified; inspect jobs before changing paths.",
        ("CAM_",),
        (),
        ({"name": "job_container", "object_type": "App::DocumentObjectGroup"},),
    ),
    "DraftWorkbench": WorkbenchToolPack(
        "DraftWorkbench",
        "2D drafting and annotation",
        "Prefer Draft commands for 2D geometry, snaps, dimensions, and annotation.",
        ("Draft_",),
        ("Part::Part2DObject",),
        (
            {"name": "draft_group", "object_type": "App::DocumentObjectGroup"},
            {"name": "annotation_group", "object_type": "App::DocumentObjectGroup"},
        ),
    ),
    "FemWorkbench": WorkbenchToolPack(
        "FemWorkbench",
        "finite element analysis",
        "Inspect materials, constraints, mesh, and solver setup before changing analysis data.",
        ("Fem_",),
        ("Fem::",),
        (
            {"name": "analysis_group", "object_type": "App::DocumentObjectGroup"},
            {"name": "constraint_group", "object_type": "App::DocumentObjectGroup"},
        ),
    ),
    "InspectionWorkbench": WorkbenchToolPack(
        "InspectionWorkbench",
        "measurement and inspection",
        "Use inspection tools for measurement workflows and avoid geometry mutation by default.",
        ("Inspection_",),
        (),
        ({"name": "inspection_group", "object_type": "App::DocumentObjectGroup"},),
    ),
    "MaterialWorkbench": WorkbenchToolPack(
        "MaterialWorkbench",
        "materials",
        "Preserve material-card structure and prefer explicit material assignment actions.",
        ("Material_", "Mat"),
        (),
        ({"name": "material_group", "object_type": "App::DocumentObjectGroup"},),
    ),
    "MeshWorkbench": WorkbenchToolPack(
        "MeshWorkbench",
        "mesh repair and editing",
        "Treat mesh simplification and repair as write operations requiring approval.",
        ("Mesh_",),
        ("Mesh::",),
        ({"name": "mesh_group", "object_type": "App::DocumentObjectGroup"},),
    ),
    "MeshPartWorkbench": WorkbenchToolPack(
        "MeshPartWorkbench",
        "mesh/part conversion",
        "Use MeshPart tessellation tools for explicit Part-to-mesh workflows and require approval for generated meshes.",
        ("MeshPart_",),
        ("Mesh::", "Part::"),
        ({"name": "mesh_from_shape", "object_type": "Mesh::Feature"},),
    ),
    "NoneWorkbench": WorkbenchToolPack(
        "NoneWorkbench",
        "no active workbench",
        "Use core document, selection, and view tools until a modeling workbench is active.",
        (),
        (),
        ({"name": "context_group", "object_type": "App::DocumentObjectGroup"},),
    ),
    "OpenSCADWorkbench": WorkbenchToolPack(
        "OpenSCADWorkbench",
        "OpenSCAD import and CSG operations",
        "Inspect imported CSG trees before replacement or refinement operations.",
        ("OpenSCAD_",),
        (),
        ({"name": "csg_group", "object_type": "App::DocumentObjectGroup"},),
    ),
    "PartDesignWorkbench": WorkbenchToolPack(
        "PartDesignWorkbench",
        "parametric solid features",
        (
            "Prefer the same feature flow a human would use: create or reuse a Body, "
            "create constrained sketches, then create PartDesign features such as Pad. "
            "When the document has no model yet, start by creating the document/body "
            "and a deliberate base sketch instead of enumerating tools. Add only the "
            "feature operations the design needs, then inspect solver/profile state "
            "and the resulting solid before completion."
        ),
        ("PartDesign_", "Sketcher_"),
        ("PartDesign::", "Sketcher::SketchObject"),
        (
            {"name": "body", "object_type": "PartDesign::Body"},
            {"name": "sketch", "object_type": "Sketcher::SketchObject"},
        ),
    ),
    "PartWorkbench": WorkbenchToolPack(
        "PartWorkbench",
        "boundary-representation solids",
        "Use Part operations for primitive solids and boolean modeling; preserve object labels.",
        ("Part_",),
        ("Part::",),
        (
            {"name": "box", "object_type": "Part::Box"},
            {"name": "cylinder", "object_type": "Part::Cylinder"},
            {"name": "sphere", "object_type": "Part::Sphere"},
        ),
    ),
    "PointsWorkbench": WorkbenchToolPack(
        "PointsWorkbench",
        "point clouds",
        "Treat point-cloud modification as write operations and preserve original imports.",
        ("Points_",),
        ("Points::",),
        ({"name": "points_group", "object_type": "App::DocumentObjectGroup"},),
    ),
    "ReverseEngineeringWorkbench": WorkbenchToolPack(
        "ReverseEngineeringWorkbench",
        "reverse engineering",
        "Prefer inspection and surface reconstruction actions over destructive mesh edits.",
        ("ReverseEngineering_",),
        (),
        ({"name": "reverse_engineering_group", "object_type": "App::DocumentObjectGroup"},),
    ),
    "RobotWorkbench": WorkbenchToolPack(
        "RobotWorkbench",
        "robot simulation",
        "Inspect trajectories and robot setup before changing simulation data.",
        ("Robot_",),
        ("Robot::",),
        ({"name": "robot_simulation_group", "object_type": "App::DocumentObjectGroup"},),
    ),
    "SketcherWorkbench": WorkbenchToolPack(
        "SketcherWorkbench",
        "2D constrained sketches",
        "Prefer constraint-aware sketch changes and avoid unconstrained geometry edits.",
        ("Sketcher_",),
        ("Sketcher::SketchObject",),
        ({"name": "sketch", "object_type": "Sketcher::SketchObject"},),
    ),
    "SpreadsheetWorkbench": WorkbenchToolPack(
        "SpreadsheetWorkbench",
        "spreadsheet data",
        "Treat cell edits as document writes and preserve alias/formula relationships.",
        ("Spreadsheet_",),
        ("Spreadsheet::Sheet",),
        ({"name": "sheet", "object_type": "Spreadsheet::Sheet"},),
    ),
    "SurfaceWorkbench": WorkbenchToolPack(
        "SurfaceWorkbench",
        "surface modeling",
        "Inspect edge/face selection context before creating or changing surface features.",
        ("Surface_",),
        ("Surface::",),
        (
            {"name": "filling", "object_type": "Surface::Filling"},
            {"name": "geom_fill_surface", "object_type": "Surface::GeomFillSurface"},
            {"name": "sections", "object_type": "Surface::Sections"},
        ),
    ),
    "TechDrawWorkbench": WorkbenchToolPack(
        "TechDrawWorkbench",
        "technical drawing pages and views",
        "Prefer page/view/annotation commands and preserve drawing references.",
        ("TechDraw_",),
        ("TechDraw::",),
        (
            {"name": "page_group", "object_type": "App::DocumentObjectGroup"},
            {"name": "drawing_group", "object_type": "App::DocumentObjectGroup"},
        ),
    ),
    "TestWorkbench": WorkbenchToolPack(
        "TestWorkbench",
        "test framework",
        "Prefer read-only inspection of test commands; require approval before running test commands.",
        ("Test_", "Std_Test"),
        (),
        ({"name": "test_group", "object_type": "App::DocumentObjectGroup"},),
    ),
}


def get_tool_pack(workbench: str | None) -> WorkbenchToolPack | None:
    if not workbench:
        return None
    return WORKBENCH_TOOL_PACKS.get(workbench)


def list_tool_packs() -> list[dict[str, object]]:
    return [pack.summary() for pack in WORKBENCH_TOOL_PACKS.values()]
