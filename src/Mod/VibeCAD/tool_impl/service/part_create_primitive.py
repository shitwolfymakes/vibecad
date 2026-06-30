# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``part.create_primitive``."""

from __future__ import annotations

from VibeCADTransactions import run_freecad_transaction
from . import domain_runtime


TOOL_SPEC = {'description': 'Create a native Part workbench primitive with dimensions and '
                'placement, equivalent to using Part primitive tools with explicit '
                'values.',
 'name': 'part.create_primitive',
 'parameters': {'properties': {'height': {'type': 'number'},
                               'label': {'type': 'string'},
                               'length': {'type': 'number'},
                               'primitive_type': {'enum': ['box', 'cylinder', 'sphere'],
                                                  'type': 'string'},
                               'radius': {'type': 'number'},
                               'width': {'type': 'number'},
                               'x': {'type': 'number'},
                               'y': {'type': 'number'},
                               'z': {'type': 'number'}},
                'required': ['primitive_type'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartWorkbench'}


def run(
    service,
    primitive_type: str,
    label: str = "VibeCAD Part Primitive",
    length: float = 10.0,
    width: float = 10.0,
    height: float = 10.0,
    radius: float = 5.0,
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
) -> dict[str, Any]:
    primitive = primitive_type.lower().strip()
    object_types = {
        "box": "Part::Box",
        "cylinder": "Part::Cylinder",
        "sphere": "Part::Sphere",
    }
    if primitive not in object_types:
        return {
            "ok": False,
            "error": f"Unsupported Part primitive: {primitive_type}",
            "allowed_primitives": sorted(object_types),
            "active_workbench": "PartWorkbench",
        }

    def _create() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument or App.newDocument()
        name = "VibeCAD_" + primitive.title()
        obj = doc.addObject(object_types[primitive], name)
        obj.Label = label
        if primitive == "box":
            obj.Length = float(length)
            obj.Width = float(width)
            obj.Height = float(height)
        elif primitive == "cylinder":
            obj.Radius = float(radius)
            obj.Height = float(height)
        elif primitive == "sphere":
            obj.Radius = float(radius)
        try:
            obj.Placement.Base = App.Vector(float(x), float(y), float(z))
        except Exception:
            pass
        doc.recompute()
        return {
            "document": doc.Name,
            "object": obj.Name,
            "label": obj.Label,
            "type": obj.TypeId,
            "primitive_type": primitive,
            "placement": [float(x), float(y), float(z)],
        }

    transaction = run_freecad_transaction(
        f"Create Part {primitive}: {label}",
        _create,
    )
    return {
        "ok": bool(transaction.get("ok")),
        "primitive_type": primitive,
        "transaction": transaction,
        "part": domain_runtime.part_summary(service),
    }
