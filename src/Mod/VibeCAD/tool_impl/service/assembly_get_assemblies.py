# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``assembly.get_assemblies``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return Assembly workbench assemblies, child counts, joint groups, and '
                'component summaries.',
 'name': 'assembly.get_assemblies',
 'safety': 'READ',
 'workbench': 'AssemblyWorkbench'}


def run(service, **kwargs):
    assemblies = [service._assembly_summary(obj) for obj in service._assembly_objects()]
    return {"assembly_count": len(assemblies), "assemblies": assemblies}
