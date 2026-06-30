# SPDX-License-Identifier: LGPL-2.1-or-later

"""Service tool definition for ``cam.get_jobs``."""

from __future__ import annotations

TOOL_SPEC = {'description': 'Return CAM jobs, model groups, operation groups, and tool controller '
                'groups from the active document.',
 'name': 'cam.get_jobs',
 'parameters': {'properties': {'job_name': {'description': 'CAM job object name or '
                                                           'label. Defaults to the '
                                                           'first job.',
                                            'type': 'string'}},
                'type': 'object'},
 'safety': 'READ',
 'workbench': 'CAMWorkbench'}


def run(service, **kwargs):
    job_name = kwargs.get("job_name")
    jobs = service._cam_jobs()
    job = service._get_cam_job(job_name)
    return {
        "job_count": len(jobs),
        "jobs": [service._cam_job_summary(item) for item in jobs],
        "selected_job": service._cam_job_summary(job) if job else None,
    }
