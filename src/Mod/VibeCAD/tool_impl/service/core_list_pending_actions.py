# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``core.list_pending_actions``."""

from __future__ import annotations


TOOL_SPEC = {'description': 'Return VibeCAD actions waiting for user approval.',
 'name': 'core.list_pending_actions',
 'safety': 'READ'}


def run(service, **kwargs):
    return service.approvals.pending()
