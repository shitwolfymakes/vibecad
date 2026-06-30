# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``core.clear_local_session``."""

from __future__ import annotations


TOOL_SPEC = {'description': 'Clear local VibeCAD pending actions, action history, and attached '
                'viewport screenshot metadata.',
 'name': 'core.clear_local_session',
 'safety': 'WRITE'}


def run(service, **kwargs):
    screenshot = service._last_view_screenshot
    service._last_view_screenshot = None
    service._conversation_cache = []
    service._conversation_cache_key = None
    service._tool_shape_feedback = []
    path = service._conversation_path()
    service._conversation_cache_key = str(path)
    service._write_conversation(path, [])
    return {
        "ok": True,
        "screenshot_cleared": bool(screenshot),
        "conversation_cleared": True,
        "conversation_path": str(path),
        "tool_shape_feedback_cleared": True,
    }
