"""Job status, SSE progress, and deletion endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..jobs.registry import registry
from ..models import Stage

router = APIRouter(prefix="/api")


@router.get("/jobs/{job_id}")
async def get_status(job_id: str) -> dict:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job.status.model_dump()


@router.get("/jobs/{job_id}/events")
async def stream_events(job_id: str):
    """Server-sent events stream of JobStatus updates until DONE/ERROR."""
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")

    async def gen():
        # Emit the current status first so late subscribers are caught up.
        yield {"event": "status", "data": job.status.model_dump_json()}
        while True:
            try:
                status = await asyncio.wait_for(job.queue.get(), timeout=30)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            yield {"event": "status", "data": status.model_dump_json()}
            if status.stage in (Stage.DONE, Stage.ERROR):
                break

    return EventSourceResponse(gen())


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> dict:
    if not registry.delete(job_id):
        raise HTTPException(404, "job not found")
    return {"ok": True}
