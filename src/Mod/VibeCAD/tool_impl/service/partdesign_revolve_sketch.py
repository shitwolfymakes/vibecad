# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``partdesign.revolve_sketch``."""

from __future__ import annotations

from . import domain_runtime


TOOL_SPEC = {'contextual': True,
 'description': 'Create a native PartDesign Revolution from an existing sketch around '
                'a Body origin axis.',
 'name': 'partdesign.revolve_sketch',
 'parameters': {'properties': {'angle': {'type': 'number'},
                               'axis': {'enum': ['X_Axis', 'Y_Axis', 'Z_Axis'],
                                        'type': 'string'},
                               'label': {'type': 'string'},
                               'midplane': {'type': 'boolean'},
                               'reversed': {'type': 'boolean'},
                               'sketch_name': {'type': 'string'}},
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartDesignWorkbench'}
from VibeCADTransactions import run_freecad_transaction


def _axis_coordinate(axis: str) -> int | None:
    if axis == "X_Axis":
        return 1
    if axis == "Y_Axis":
        return 0
    return None


def _geometry_axis_interval(geometry, coordinate: int) -> tuple[float, float] | None:
    values: list[float] = []
    for attribute in ("StartPoint", "EndPoint", "Center"):
        point = getattr(geometry, attribute, None)
        if point is not None:
            values.append(float((point.x, point.y, point.z)[coordinate]))
    poles = getattr(geometry, "Poles", None)
    if poles:
        for point in poles:
            values.append(float((point.x, point.y, point.z)[coordinate]))
    radius = getattr(geometry, "Radius", None)
    center = getattr(geometry, "Center", None)
    if radius is not None and center is not None:
        center_value = float((center.x, center.y, center.z)[coordinate])
        values.extend([center_value - float(radius), center_value + float(radius)])
    major_radius = getattr(geometry, "MajorRadius", None)
    minor_radius = getattr(geometry, "MinorRadius", None)
    if center is not None and (major_radius is not None or minor_radius is not None):
        extent = max(float(major_radius or 0.0), float(minor_radius or 0.0))
        center_value = float((center.x, center.y, center.z)[coordinate])
        values.extend([center_value - extent, center_value + extent])
    if not values:
        return None
    return min(values), max(values)


def _revolution_profile_preflight(service, sketch, axis: str) -> dict[str, object]:
    profile_status = service._sketch_profile_status(sketch)
    result: dict[str, object] = {
        "ok": bool(profile_status.get("ready_for_pad")),
        "axis": axis,
        "profile_status": profile_status,
        "axis_crosses_profile": False,
        "checked": False,
        "reason": profile_status.get("reason"),
    }
    if not profile_status.get("ready_for_pad"):
        result["reason"] = "Sketch is not ready for PartDesign Revolution; it must be closed and fully constrained."
        return result
    coordinate = _axis_coordinate(axis)
    if coordinate is None:
        result["ok"] = True
        result["checked"] = False
        result["reason"] = "Axis is not an in-sketch X/Y axis; native FreeCAD validation will be used."
        return result
    intervals = []
    geometry = list(getattr(sketch, "Geometry", []) or [])
    for index, item in enumerate(geometry):
        try:
            if bool(sketch.getConstruction(index)):
                continue
        except Exception:
            pass
        interval = _geometry_axis_interval(item, coordinate)
        if interval is not None:
            intervals.append(
                {
                    "geometry_index": index,
                    "geometry_type": item.__class__.__name__,
                    "min": interval[0],
                    "max": interval[1],
                }
            )
    result["checked"] = True
    result["axis_coordinate"] = "Y" if coordinate == 1 else "X"
    result["geometry_intervals"] = intervals
    tolerance = 1e-7
    crossing = [
        item for item in intervals
        if float(item["min"]) < -tolerance and float(item["max"]) > tolerance
    ]
    if crossing:
        result["ok"] = False
        result["axis_crosses_profile"] = True
        result["crossing_geometry"] = crossing
        result["reason"] = (
            "Sketch profile crosses the requested in-plane revolution axis; "
            "FreeCAD PartDesign Revolution requires the profile to stay on one "
            "side of the axis or only touch it at the boundary."
        )
    else:
        result["ok"] = True
        result["reason"] = "Sketch profile is closed, fully constrained, and does not cross the requested in-plane revolution axis."
    return result


def _set_revolve_midplane(feature, midplane: bool) -> bool:
    requested = bool(midplane)
    if hasattr(feature, "Midplane"):
        feature.Midplane = requested
        return bool(getattr(feature, "Midplane", requested))
    return requested


def run(
    service,
    sketch_name: str | None = None,
    label: str = "VibeCAD Revolution",
    angle: float = 360.0,
    axis: str = "X_Axis",
    reversed: bool = False,
    midplane: bool = False,
) -> dict[str, Any]:
    sketch = service._get_sketch(sketch_name)
    if sketch is None:
        return {"ok": False, "error": "Sketch not found.", "requested": sketch_name}
    if float(angle) <= 0 or float(angle) > 360:
        return {"ok": False, "error": "Revolution angle must be greater than 0 and no more than 360 degrees."}
    requested_axis = str(axis or "X_Axis")
    if requested_axis not in {"X_Axis", "Y_Axis", "Z_Axis"}:
        return {"ok": False, "error": "axis must be X_Axis, Y_Axis, or Z_Axis."}
    preflight = _revolution_profile_preflight(service, sketch, requested_axis)
    if not preflight.get("ok"):
        return {
            "ok": False,
            "error": str(preflight.get("reason") or "Sketch is not valid for PartDesign Revolution."),
            "recoverable": True,
            "active_sketch": getattr(sketch, "Name", None),
            "revolution_preflight": preflight,
            "profile_status": preflight.get("profile_status"),
            "next_actions": [
                {
                    "tool": "sketcher.validate_profile_deep",
                    "arguments": {"sketch_name": getattr(sketch, "Name", None)},
                    "why": "Inspect open endpoints, self-intersections, and profile topology before retrying the revolution.",
                },
                {
                    "tool": "sketcher.list_geometry",
                    "arguments": {"sketch_name": getattr(sketch, "Name", None)},
                    "why": "Inspect geometry coordinates relative to the requested revolution axis.",
                },
                {
                    "tool": "sketcher.move_point",
                    "why": "Move or resize the profile so it stays on one side of the requested revolution axis.",
                },
                {
                    "tool": "partdesign.pad_sketch",
                    "arguments": {"sketch_name": getattr(sketch, "Name", None)},
                    "why": "Use a different native PartDesign feature if revolution is not valid for the chosen profile.",
                },
            ],
        }

    def _revolve() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active document.")
        target_sketch = service._get_sketch(sketch.Name)
        if target_sketch is None:
            raise RuntimeError(f"Sketch not found: {sketch.Name}")
        body = service._partdesign_body_for_feature(target_sketch)
        if body is None:
            raise RuntimeError("No PartDesign Body found for revolution.")
        axis_feature = service._partdesign_origin_feature(body, requested_axis)
        if axis_feature is None:
            raise RuntimeError(f"Body origin axis not found: {requested_axis}")
        revolution = body.newObject("PartDesign::Revolution", "VibeCAD_Revolution")
        revolution.Label = label or "VibeCAD Revolution"
        revolution.Profile = target_sketch
        revolution.ReferenceAxis = (axis_feature, [""])
        revolution.Angle = float(angle)
        revolution.Reversed = bool(reversed)
        actual_midplane = _set_revolve_midplane(revolution, bool(midplane))
        body.Tip = revolution
        doc.recompute()
        return {
            "document": doc.Name,
            "body": body.Name,
            "sketch": target_sketch.Name,
            "feature": revolution.Name,
            "label": getattr(revolution, "Label", revolution.Name),
            "type": getattr(revolution, "TypeId", ""),
            "angle": float(revolution.Angle),
            "axis": requested_axis,
            "reversed": bool(getattr(revolution, "Reversed", False)),
            "midplane": actual_midplane,
            "revolution_preflight": preflight,
            "face_count": len(getattr(getattr(revolution, "Shape", None), "Faces", []) or []),
            "volume": float(getattr(getattr(revolution, "Shape", None), "Volume", 0.0) or 0.0),
        }

    transaction = run_freecad_transaction(
        f"Create PartDesign revolution from sketch: {getattr(sketch, 'Label', sketch.Name)}",
        _revolve,
    )
    response = {
        "ok": bool(transaction.get("ok")),
        "transaction": transaction,
        "partdesign": domain_runtime.partdesign_summary(service),
    }
    if not response["ok"]:
        body = service._partdesign_body_for_feature(sketch)
        response["error"] = transaction.get("error") or "PartDesign revolution failed."
        response["recoverable"] = True
        response["failure_context"] = {
            "sketch": service._object_summary(sketch),
            "profile_status": service._sketch_profile_status(sketch),
            "axis": requested_axis,
            "angle": float(angle),
            "revolution_preflight": preflight,
            "body": service._partdesign_body_summary(body) if body is not None else None,
            "document_delta": transaction.get("document_delta"),
            "report_view_errors": transaction.get("report_view_errors"),
        }
        response["next_actions"] = [
            {
                "tool": "sketcher.validate_profile_deep",
                "arguments": {"sketch_name": sketch.Name},
                "why": "Inspect whether the revolution profile crosses or touches the chosen axis in a way that makes the native feature invalid.",
            },
            {
                "tool": "core.delete_object",
                "why": "If the failed revolution left invalid feature objects in the document delta, delete those invalid objects before continuing.",
            },
            {
                "tool": "partdesign.pad_sketch",
                "arguments": {"sketch_name": sketch.Name},
                "why": "If the profile is not valid for revolution, use another native PartDesign feature that matches the geometry intent.",
            },
        ]
    return response
