# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``core.reject_action``."""

from __future__ import annotations


TOOL_SPEC = {'description': 'Reject a previously proposed VibeCAD action by id.',
 'name': 'core.reject_action',
 'parameters': {'properties': {'action_id': {'type': 'string'}},
                'required': ['action_id'],
                'type': 'object'},
 'safety': 'READ'}


def run(service, **kwargs):
    action_id = kwargs["action_id"]
    try:
        return service.approvals.reject(action_id)
    except KeyError:
        return {"id": action_id, "status": "missing"}
