# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``robot.get_objects``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return Robot workbench robot objects, trajectories, and bounded '
                'waypoint summaries from the active document.',
 'name': 'robot.get_objects',
 'safety': 'READ',
 'workbench': 'RobotWorkbench'}


def run(service, **kwargs):
    doc = service._active_document()
    objects = [service._robot_object_summary(obj) for obj in doc.Objects] if doc else []
    robot_like = [obj for obj in objects if obj.get("robot_role")]
    return {"object_count": len(objects), "robot_object_count": len(robot_like), "objects": objects}
