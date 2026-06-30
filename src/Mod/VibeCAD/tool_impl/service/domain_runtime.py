# SPDX-License-Identifier: LGPL-2.1-or-later

"""Workbench/domain read-tool implementations outside ``VibeCADCore``."""

from __future__ import annotations

from typing import Any


def bound_box_summary(bound_box: Any) -> dict[str, Any] | None:
    if bound_box is None:
        return None
    try:
        return {
            "xmin": float(bound_box.XMin),
            "ymin": float(bound_box.YMin),
            "zmin": float(bound_box.ZMin),
            "xmax": float(bound_box.XMax),
            "ymax": float(bound_box.YMax),
            "zmax": float(bound_box.ZMax),
            "xlength": float(bound_box.XLength),
            "ylength": float(bound_box.YLength),
            "zlength": float(bound_box.ZLength),
        }
    except Exception:
        return None


def shape_summary(obj: Any) -> dict[str, Any]:
    try:
        shape = getattr(obj, "Shape", None)
    except Exception:
        shape = None
    if shape is None:
        return {
            "available": False,
            "solids": 0,
            "faces": 0,
            "edges": 0,
            "vertices": 0,
            "volume": 0.0,
        }
    try:
        summary = {
            "available": True,
            "solids": len(getattr(shape, "Solids", []) or []),
            "faces": len(getattr(shape, "Faces", []) or []),
            "edges": len(getattr(shape, "Edges", []) or []),
            "vertices": len(getattr(shape, "Vertexes", []) or []),
            "volume": float(getattr(shape, "Volume", 0.0) or 0.0),
        }
    except Exception as exc:
        return {
            "available": False,
            "solids": 0,
            "faces": 0,
            "edges": 0,
            "vertices": 0,
            "volume": 0.0,
            "error": str(exc),
        }
    try:
        bound_box = bound_box_summary(getattr(shape, "BoundBox", None))
    except Exception:
        bound_box = None
    if bound_box:
        summary["bound_box"] = bound_box
    return summary


def shape_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    delta = {
        "volume_delta": float(after.get("volume", 0.0) or 0.0)
        - float(before.get("volume", 0.0) or 0.0),
        "solids_delta": int(after.get("solids", 0) or 0)
        - int(before.get("solids", 0) or 0),
        "faces_delta": int(after.get("faces", 0) or 0)
        - int(before.get("faces", 0) or 0),
        "edges_delta": int(after.get("edges", 0) or 0)
        - int(before.get("edges", 0) or 0),
        "vertices_delta": int(after.get("vertices", 0) or 0)
        - int(before.get("vertices", 0) or 0),
    }
    before_box = before.get("bound_box") if isinstance(before.get("bound_box"), dict) else {}
    after_box = after.get("bound_box") if isinstance(after.get("bound_box"), dict) else {}
    box_delta = {}
    for key in ("xmin", "ymin", "zmin", "xmax", "ymax", "zmax", "xlength", "ylength", "zlength"):
        if key in before_box and key in after_box:
            box_delta[f"{key}_delta"] = float(after_box.get(key, 0.0) or 0.0) - float(before_box.get(key, 0.0) or 0.0)
    if box_delta:
        delta["bound_box_delta"] = box_delta
    return delta


def partdesign_feature_effect(
    operation: str,
    body_shape_before: dict[str, Any],
    body_shape_after: dict[str, Any],
    feature_shape: dict[str, Any],
) -> dict[str, Any]:
    delta = shape_delta(body_shape_before, body_shape_after)
    feature_has_shape = (
        bool(feature_shape.get("available"))
        and (
            int(feature_shape.get("solids", 0) or 0) > 0
            or int(feature_shape.get("faces", 0) or 0) > 0
            or abs(float(feature_shape.get("volume", 0.0) or 0.0)) > 1e-9
        )
    )
    volume_delta = float(delta.get("volume_delta", 0.0) or 0.0)
    topology_changed = any(
        int(delta.get(key, 0) or 0) != 0
        for key in ("solids_delta", "faces_delta", "edges_delta", "vertices_delta")
    )
    bound_box_changed = any(
        abs(float(value or 0.0)) > 1e-9
        for value in (delta.get("bound_box_delta") or {}).values()
    )
    if operation == "pad":
        expected_direction = volume_delta > 1e-9
    elif operation in {"pocket", "hole", "groove"}:
        expected_direction = volume_delta < -1e-9
    else:
        expected_direction = abs(volume_delta) > 1e-9
    return {
        "ok": bool(feature_has_shape and (expected_direction or topology_changed or bound_box_changed)),
        "operation": operation,
        "feature_has_shape": bool(feature_has_shape),
        "expected_volume_direction": bool(expected_direction),
        "topology_changed": bool(topology_changed),
        "bound_box_changed": bool(bound_box_changed),
        "body_shape_delta": delta,
    }


def finalize_partdesign_feature_effect(
    doc: Any,
    body: Any,
    feature: Any,
    operation: str,
    body_shape_before: dict[str, Any],
) -> dict[str, Any]:
    body_shape_after = shape_summary(body)
    feature_shape = shape_summary(feature)
    feature_effect = partdesign_feature_effect(
        operation,
        body_shape_before,
        body_shape_after,
        feature_shape,
    )
    rolled_back_feature = False
    body_shape_after_rollback = None
    if not feature_effect.get("ok"):
        feature_name = getattr(feature, "Name", None)
        if feature_name:
            doc.removeObject(feature_name)
            doc.recompute()
            rolled_back_feature = True
            body_shape_after_rollback = shape_summary(body)
    return {
        "body_shape_before": body_shape_before,
        "body_shape_after": body_shape_after,
        "body_shape_delta": feature_effect["body_shape_delta"],
        "feature_shape": feature_shape,
        "feature_effect": feature_effect,
        "rolled_back_feature": rolled_back_feature,
        "body_shape_after_rollback": body_shape_after_rollback,
    }


def spreadsheet_summary(service: Any, sheet_name: str | None = None, max_columns: int = 8, max_rows: int = 20) -> dict[str, Any]:
    sheet = service._get_spreadsheet(sheet_name)
    sheets = service._spreadsheet_objects()
    if sheet is None:
        return {
            "found": False,
            "requested": sheet_name,
            "sheet_count": len(sheets),
            "sheets": [service._object_summary(item) for item in sheets],
        }

    safe_columns = max(1, min(int(max_columns), 26))
    safe_rows = max(1, min(int(max_rows), 200))
    cells = []
    for column_index in range(1, safe_columns + 1):
        for row in range(1, safe_rows + 1):
            cell = service._cell_name(column_index, row)
            try:
                contents = sheet.getContents(cell)
            except Exception:
                contents = ""
            if contents in ("", None):
                continue
            try:
                value = sheet.get(cell)
            except Exception as exc:
                value = f"<error: {exc}>"
            cells.append(
                {
                    "cell": cell,
                    "contents": service._short_value(contents),
                    "value": service._short_value(value),
                }
            )
    return {
        "found": True,
        "sheet": service._object_summary(sheet),
        "scanned_columns": safe_columns,
        "scanned_rows": safe_rows,
        "non_empty_count": len(cells),
        "cells": cells,
    }


def draft_summary(service: Any) -> dict[str, Any]:
    objects = [service._draft_object_summary(obj) for obj in service._draft_objects()]
    return {"object_count": len(objects), "objects": objects}


def partdesign_summary(service: Any, body_name: str | None = None) -> dict[str, Any]:
    bodies = service._partdesign_bodies()
    body = service._get_partdesign_body(body_name)
    return {
        "body_count": len(bodies),
        "bodies": [service._partdesign_body_summary(item) for item in bodies],
        "selected_body": service._partdesign_body_summary(body) if body else None,
    }


def techdraw_summary(service: Any, page_name: str | None = None) -> dict[str, Any]:
    pages = service._techdraw_pages()
    page = service._get_techdraw_page(page_name)
    return {
        "page_count": len(pages),
        "pages": [service._techdraw_page_summary(item) for item in pages],
        "selected_page": service._techdraw_page_summary(page) if page else None,
    }


def fem_summary(service: Any, analysis_name: str | None = None) -> dict[str, Any]:
    analyses = service._fem_analyses()
    analysis = service._get_fem_analysis(analysis_name)
    return {
        "analysis_count": len(analyses),
        "analyses": [service._fem_analysis_summary(item) for item in analyses],
        "selected_analysis": service._fem_analysis_summary(analysis) if analysis else None,
    }


def cam_summary(service: Any, job_name: str | None = None) -> dict[str, Any]:
    jobs = service._cam_jobs()
    job = service._get_cam_job(job_name)
    return {
        "job_count": len(jobs),
        "jobs": [service._cam_job_summary(item) for item in jobs],
        "selected_job": service._cam_job_summary(job) if job else None,
    }


def bim_summary(service: Any) -> dict[str, Any]:
    objects = [service._bim_object_summary(obj) for obj in service._bim_objects()]
    return {"object_count": len(objects), "objects": objects}


def assembly_summary(service: Any) -> dict[str, Any]:
    doc = service._active_document()
    assemblies = [service._assembly_summary(obj) for obj in service._assembly_objects()]
    return {
        "document": getattr(doc, "Name", None) if doc else None,
        "assembly_count": len(assemblies),
        "assemblies": assemblies,
    }


def inspection_summary(service: Any) -> dict[str, Any]:
    features = [service._inspection_feature_summary(obj) for obj in service._inspection_features()]
    candidates = [service._document_object_summary(obj) for obj in service._inspection_candidates()]
    return {"feature_count": len(features), "features": features, "candidate_count": len(candidates), "candidates": candidates}


def openscad_summary(service: Any) -> dict[str, Any]:
    objects = [service._openscad_object_summary(obj) for obj in service._active_document().Objects] if service._active_document() else []
    return {"object_count": len(objects), "objects": objects}


def surface_summary(service: Any) -> dict[str, Any]:
    objects = [service._surface_object_summary(obj) for obj in service._surface_objects()]
    return {"object_count": len(objects), "objects": objects}


def reverseengineering_summary(service: Any) -> dict[str, Any]:
    doc = service._active_document()
    if doc is None:
        return {"candidate_count": 0, "output_count": 0, "candidates": [], "outputs": []}
    candidates = [service._reverseengineering_object_summary(obj) for obj in doc.Objects if service._is_reverseengineering_candidate(obj)]
    outputs = [service._reverseengineering_object_summary(obj) for obj in doc.Objects if service._is_reverseengineering_output(obj)]
    return {"candidate_count": len(candidates), "output_count": len(outputs), "candidates": candidates, "outputs": outputs}


def robot_summary(service: Any) -> dict[str, Any]:
    doc = service._active_document()
    objects = [service._robot_object_summary(obj) for obj in doc.Objects] if doc else []
    robot_like = [obj for obj in objects if obj.get("robot_role")]
    return {"object_count": len(objects), "robot_object_count": len(robot_like), "objects": objects}


def meshpart_summary(service: Any) -> dict[str, Any]:
    doc = service._active_document()
    if doc is None:
        return {
            "document": None,
            "part_candidate_count": 0,
            "mesh_count": 0,
            "part_candidates": [],
            "meshes": [],
        }
    part_candidates = [
        service._part_object_summary(obj)
        for obj in doc.Objects
        if service._is_meshpart_part_candidate(obj)
    ]
    meshes = [
        service._mesh_object_summary(obj)
        for obj in doc.Objects
        if service._is_meshpart_mesh_output(obj)
    ]
    return {
        "document": doc.Name,
        "part_candidate_count": len(part_candidates),
        "mesh_count": len(meshes),
        "part_candidates": part_candidates[:80],
        "meshes": meshes[:80],
    }


def part_summary(service: Any) -> dict[str, Any]:
    objects = [service._part_object_summary(obj) for obj in service._part_objects()]
    return {"object_count": len(objects), "objects": objects}


def mesh_summary(service: Any) -> dict[str, Any]:
    objects = [service._mesh_object_summary(obj) for obj in service._mesh_objects()]
    return {"object_count": len(objects), "objects": objects}


def points_summary(service: Any) -> dict[str, Any]:
    objects = [service._points_object_summary(obj) for obj in service._points_objects()]
    return {"object_count": len(objects), "objects": objects}


def material_summary(service: Any) -> dict[str, Any]:
    objects = [service._material_object_summary(obj) for obj in service._material_capable_objects()]
    return {"object_count": len(objects), "objects": objects}
