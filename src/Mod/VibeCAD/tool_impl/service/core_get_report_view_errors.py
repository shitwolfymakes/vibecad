# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``core.get_report_view_errors``."""

from __future__ import annotations
from VibeCADTransactions import report_view_error_summary


TOOL_SPEC = {'description': 'Return recent FreeCAD report-view error, exception, and traceback '
                'lines when the GUI report view is available.',
 'name': 'core.get_report_view_errors',
 'safety': 'READ'}


def run(service, **kwargs):
    return report_view_error_summary()
