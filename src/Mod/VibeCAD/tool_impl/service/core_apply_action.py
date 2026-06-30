# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``core.apply_action``."""

from __future__ import annotations


TOOL_SPEC = {'description': 'Apply a previously proposed VibeCAD action by id.',
 'name': 'core.apply_action',
 'parameters': {'properties': {'action_id': {'type': 'string'}},
                'required': ['action_id'],
                'type': 'object'},
 'safety': 'WRITE'}


def run(service, **kwargs):
    action_id = kwargs["action_id"]
    try:
        return service.approvals.apply(action_id)
    except KeyError:
        return {"id": action_id, "status": "missing"}
