"""Upload + ROI/hint submission endpoints."""

from __future__ import annotations

import asyncio
import shutil

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import config
from ..jobs.pipeline import run_pipeline
from ..jobs.registry import registry
from ..models import Hints, Modality, ROISpec

router = APIRouter(prefix="/api")


@router.post("/jobs")
async def create_job(
    file: UploadFile = File(...),
    modality: Modality = Form(Modality.AUTO),
) -> dict:
    """Accept a screen recording and start the pipeline (up to the crop pause)."""
    config.ensure_dirs()
    # We need a job id to name the working dir; create the job first, then save the file.
    tmp = config.JOBS_DIR / "_incoming"
    tmp.mkdir(parents=True, exist_ok=True)
    suffix = "".join(c for c in (file.filename or "video") if c in "._-" or c.isalnum())
    staged = tmp / suffix
    with staged.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    job = registry.create(staged, modality)
    dest = config.job_dir(job.job_id) / staged.name
    shutil.move(str(staged), str(dest))
    job.video_path = dest

    job.task = asyncio.create_task(run_pipeline(job))
    return {"job_id": job.job_id}


@router.post("/jobs/{job_id}/roi")
async def submit_roi(job_id: str, roi: ROISpec) -> dict:
    """Submit the confirmed/edited crop, releasing the paused pipeline."""
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    job.roi = roi
    job.roi_event.set()
    return {"ok": True}


@router.post("/jobs/{job_id}/hints")
async def submit_hints(job_id: str, hints: Hints) -> dict:
    """Provide manual slice/timepoint counts (used when OCR fails)."""
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    # Re-run the tail of the pipeline with hints if the job already finished/erred.
    job._hints = hints  # type: ignore[attr-defined]
    return {"ok": True}
