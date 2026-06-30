# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``part.apply_thickness``."""

from __future__ import annotations

from VibeCADTransactions import run_freecad_transaction
from . import domain_runtime


TOOL_SPEC = {'description': 'Create a native Part Thickness feature from an existing object by '
                'removing selected faces and applying wall thickness.',
 'name': 'part.apply_thickness',
 'parameters': {'properties': {'face_names': {'items': {'type': 'string'},
                                              'type': 'array'},
                               'inward': {'type': 'boolean'},
                               'join': {'type': 'integer'},
                               'label': {'type': 'string'},
                               'mode': {'type': 'integer'},
                               'object_name': {'type': 'string'},
                               'wall_thickness': {'type': 'number'}},
                'required': ['object_name'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartWorkbench'}


def run(
    service,
    object_name: str,
    label: str = "VibeCAD Thickness",
    wall_thickness: float = 1.5,
    face_names: list[str] | None = None,
    inward: bool = True,
    mode: int = 0,
    join: int = 0,
) -> dict[str, Any]:
    source = service._get_document_object(object_name)
    if source is None:
        return {"ok": False, "error": f"Object not found: {object_name}"}
    if float(wall_thickness) <= 0:
        return {"ok": False, "error": "wall_thickness must be positive"}
    selected_faces = [str(item) for item in (face_names or ["Face6"])]
    if not selected_faces:
        return {"ok": False, "error": "At least one face name is required."}

    def _thickness() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active document.")
        target = service._get_document_object(object_name)
        if target is None:
            raise RuntimeError(f"Object not found: {object_name}")
        shape = getattr(target, "Shape", None)
        faces = list(getattr(shape, "Faces", []) or [])
        if not faces:
            raise RuntimeError(f"Object has no faces for thickness: {object_name}")
        for face_name in selected_faces:
            if not face_name.startswith("Face"):
                raise RuntimeError(f"Invalid face name: {face_name}")
            try:
                face_index = int(face_name[4:])
            except ValueError as exc:
                raise RuntimeError(f"Invalid face name: {face_name}") from exc
            if face_index < 1 or face_index > len(faces):
                raise RuntimeError(f"Face name out of range for {object_name}: {face_name}")
        feature = doc.addObject("Part::Thickness", "VibeCAD_Thickness")
        feature.Label = label
        feature.Faces = (target, selected_faces)
        feature.Value = -float(wall_thickness) if inward else float(wall_thickness)
        feature.Mode = int(mode)
        feature.Join = int(join)
        doc.recompute()
        return {
            "object": feature.Name,
            "label": feature.Label,
            "type": feature.TypeId,
            "source": target.Name,
            "face_names": selected_faces,
            "wall_thickness": float(wall_thickness),
            "inward": bool(inward),
            "mode": int(mode),
            "join": int(join),
            "mode_label": str(getattr(feature, "Mode", "")),
            "join_label": str(getattr(feature, "Join", "")),
            "face_count": len(getattr(getattr(feature, "Shape", None), "Faces", []) or []),
            "solid_count": len(getattr(getattr(feature, "Shape", None), "Solids", []) or []),
            "volume": float(getattr(getattr(feature, "Shape", None), "Volume", 0.0) or 0.0),
        }

    transaction = run_freecad_transaction(
        f"Apply Part thickness to {object_name}",
        _thickness,
    )
    return {"ok": bool(transaction.get("ok")), "transaction": transaction, "part": domain_runtime.part_summary(service)}
