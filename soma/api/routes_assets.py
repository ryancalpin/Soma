"""Serve generated artefacts: first frame, NIfTI volume, metadata, cine frames."""

from __future__ import annotations

import cv2
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

from .. import config
from ..jobs.registry import registry

router = APIRouter(prefix="/api")


@router.get("/jobs/{job_id}/first-frame")
async def first_frame(job_id: str) -> Response:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    frames = sorted((config.job_dir(job_id) / "frames").glob("frame_*.png"))
    if not frames:
        raise HTTPException(404, "frames not ready")
    data = frames[0].read_bytes()
    return Response(content=data, media_type="image/png")


@router.get("/jobs/{job_id}/frames-count")
async def frames_count(job_id: str) -> dict:
    """Number of extracted frames — used by the crop scrubber."""
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    frames = sorted((config.job_dir(job_id) / "frames").glob("frame_*.png"))
    return {"count": len(frames)}


@router.get("/jobs/{job_id}/frame/{frame}")
async def raw_frame(job_id: str, frame: int) -> Response:
    """A specific uncropped frame, so the user can pick a clearer frame to crop on."""
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    frames = sorted((config.job_dir(job_id) / "frames").glob("frame_*.png"))
    if not (0 <= frame < len(frames)):
        raise HTTPException(404, "frame out of range")
    return Response(content=frames[frame].read_bytes(), media_type="image/png")


@router.get("/jobs/{job_id}/volume.nii.gz")
async def volume(job_id: str) -> FileResponse:
    path = config.job_dir(job_id) / "volume.nii.gz"
    if not path.exists():
        raise HTTPException(404, "volume not ready")
    return FileResponse(str(path), media_type="application/gzip", filename="volume.nii.gz")


@router.get("/jobs/{job_id}/meta")
async def meta(job_id: str) -> Response:
    path = config.job_dir(job_id) / "volume.json"
    if not path.exists():
        raise HTTPException(404, "meta not ready")
    return Response(content=path.read_text(), media_type="application/json")


@router.get("/jobs/{job_id}/cine/{frame}")
async def cine_frame(job_id: str, frame: int) -> Response:
    """Return a single cine frame (cropped to ROI) as PNG, for the canvas player."""
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    frames = sorted((config.job_dir(job_id) / "frames").glob("frame_*.png"))
    if not (0 <= frame < len(frames)):
        raise HTTPException(404, "frame out of range")
    img = cv2.imread(str(frames[frame]))
    roi = job.roi or job.status.suggested_roi
    if roi is not None:
        img = img[roi.y : roi.y + roi.height, roi.x : roi.x + roi.width]
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise HTTPException(500, "encode failed")
    return Response(content=buf.tobytes(), media_type="image/png")
