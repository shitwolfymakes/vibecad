# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``part.apply_fillet``."""

from __future__ import annotations

from VibeCADTransactions import run_freecad_transaction
from . import domain_runtime


TOOL_SPEC = {'description': 'Create a new Part feature with rounded edges from an existing object.',
 'name': 'part.apply_fillet',
 'parameters': {'properties': {'edge_indices': {'items': {'type': 'integer'},
                                                'type': 'array'},
                               'label': {'type': 'string'},
                               'object_name': {'type': 'string'},
                               'radius': {'type': 'number'}},
                'required': ['object_name'],
                'type': 'object'},
 'safety': 'SAFE_WRITE',
 'workbench': 'PartWorkbench'}


def run(
    service,
    object_name: str,
    label: str = "VibeCAD Fillet",
    radius: float = 1.0,
    edge_indices: list[int] | None = None,
) -> dict[str, Any]:
    source = service._get_document_object(object_name)
    if source is None:
        return {"ok": False, "error": f"Object not found: {object_name}"}
    if float(radius) <= 0:
        return {"ok": False, "error": "radius must be positive"}

    def _fillet() -> dict[str, Any]:
        import FreeCAD as App

        doc = App.ActiveDocument
        if doc is None:
            raise RuntimeError("No active document.")
        target = service._get_document_object(object_name)
        if target is None:
            raise RuntimeError(f"Object not found: {object_name}")
        shape = getattr(target, "Shape", None)
        edges = list(getattr(shape, "Edges", []) or [])
        if not edges:
            raise RuntimeError(f"Object has no filletable edges: {object_name}")
        indices = edge_indices if edge_indices is not None else list(range(1, min(len(edges), 12) + 1))
        selected_edges = []
        for index in indices:
            edge_index = int(index)
            if 1 <= edge_index <= len(edges):
                selected_edges.append(edges[edge_index - 1])
        if not selected_edges:
            raise RuntimeError("No valid edge indices selected for fillet.")
        feature = doc.addObject("Part::Feature", "VibeCAD_Fillet")
        feature.Label = label
        feature.Shape = shape.makeFillet(float(radius), selected_edges)
        doc.recompute()
        return {
            "object": feature.Name,
            "label": feature.Label,
            "type": feature.TypeId,
            "source": target.Name,
            "radius": float(radius),
            "edge_count": len(selected_edges),
        }

    transaction = run_freecad_transaction(
        f"Apply Part fillet to {object_name}",
        _fillet,
    )
    return {"ok": bool(transaction.get("ok")), "transaction": transaction, "part": domain_runtime.part_summary(service)}
