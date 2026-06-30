# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``points.get_objects``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return Points workbench point-cloud objects with point counts, '
                'bounds, and small coordinate samples.',
 'name': 'points.get_objects',
 'safety': 'READ',
 'workbench': 'PointsWorkbench'}


def run(service, **kwargs):
    objects = [service._points_object_summary(obj) for obj in service._points_objects()]
    return {"object_count": len(objects), "objects": objects}
