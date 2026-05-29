"""In-memory job store with an async event queue per job for SSE progress.

Single-user local app — no Celery/Redis. Jobs and their working files live under
``data/jobs/<id>/`` and can be purged for PHI hygiene.
"""

from __future__ import annotations

import asyncio
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .. import config
from ..models import JobStatus, Modality, ROISpec, Stage


@dataclass
class Job:
    job_id: str
    video_path: Path
    modality_hint: Modality
    status: JobStatus
    roi: Optional[ROISpec] = None
    # set when the pipeline pauses for the user to confirm/correct the crop
    roi_event: asyncio.Event = field(default_factory=asyncio.Event)
    queue: "asyncio.Queue[JobStatus]" = field(default_factory=asyncio.Queue)
    task: Optional[asyncio.Task] = None


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self, video_path: Path, modality_hint: Modality) -> Job:
        job_id = uuid.uuid4().hex[:12]
        status = JobStatus(job_id=job_id, stage=Stage.QUEUED, message="queued")
        job = Job(job_id=job_id, video_path=video_path, modality_hint=modality_hint, status=status)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def publish(self, job: Job, status: JobStatus) -> None:
        """Update a job's status and push it to its SSE queue."""
        job.status = status
        job.queue.put_nowait(status)

    def delete(self, job_id: str) -> bool:
        job = self._jobs.pop(job_id, None)
        if job is None:
            return False
        if job.task and not job.task.done():
            job.task.cancel()
        shutil.rmtree(config.job_dir(job_id), ignore_errors=True)
        return True


registry = JobRegistry()
