"""Orchestrate the full reconstruction pipeline for a job.

Stages: probe -> extract -> auto-ROI -> (pause for user crop) -> OCR -> order ->
assemble -> write NIfTI. Progress is published to the job's SSE queue at each step.
The heavy CPU work runs in a thread so the event loop stays responsive.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .. import config
from ..models import (
    CompletenessReport,
    Hints,
    JobStatus,
    Modality,
    OCRReport,
    OutputKind,
    ROISpec,
    Stage,
    VolumeMeta,
)
from ..processing import frames as frames_mod
from ..processing import nifti_writer, ocr, ordering, roi as roi_mod, volume as volume_mod
from .registry import Job, registry

# Stage -> overall progress fraction (rough, monotonic).
_PROGRESS = {
    Stage.PROBE: 0.05,
    Stage.EXTRACT: 0.20,
    Stage.ROI: 0.30,
    Stage.AWAIT_ROI: 0.30,
    Stage.OCR: 0.60,
    Stage.ORDER: 0.75,
    Stage.ASSEMBLE: 0.88,
    Stage.WRITE: 0.97,
    Stage.DONE: 1.0,
}


def _emit(job: Job, stage: Stage, message: str, **extra) -> None:
    status = JobStatus(
        job_id=job.job_id,
        stage=stage,
        progress=_PROGRESS.get(stage, job.status.progress),
        message=message,
        suggested_roi=extra.get("suggested_roi", job.status.suggested_roi),
        meta=extra.get("meta", job.status.meta),
        error=extra.get("error"),
    )
    registry.publish(job, status)


async def run_pipeline(job: Job, hints: Hints | None = None) -> None:
    """Entry point launched as an asyncio task when a job is created."""
    hints = hints or Hints()
    jdir = config.job_dir(job.job_id)
    frames_dir = jdir / "frames"
    try:
        _emit(job, Stage.PROBE, "probing recording")
        # 1. Extract frames (blocking -> thread).
        _emit(job, Stage.EXTRACT, "extracting frames")
        frame_paths = await asyncio.to_thread(
            frames_mod.extract_frames, job.video_path, frames_dir, config.MAX_FRAMES
        )
        if not frame_paths:
            raise ValueError("no frames extracted from recording")

        # 2. Auto-detect ROI, then pause for the user to confirm/correct it.
        _emit(job, Stage.ROI, "detecting image region")
        suggested = await asyncio.to_thread(
            roi_mod.detect_roi, frame_paths, config.OCR_SAMPLE_FRAMES
        )
        job.status.suggested_roi = suggested
        _emit(job, Stage.AWAIT_ROI, "confirm crop region", suggested_roi=suggested)

        # Wait until the API receives the confirmed/edited ROI.
        await job.roi_event.wait()
        roi: ROISpec = job.roi or suggested

        await _finish_pipeline(job, frame_paths, roi, hints, jdir)
    except asyncio.CancelledError:  # pragma: no cover - job deleted mid-run
        raise
    except Exception as exc:  # surface any failure to the UI
        _emit(job, Stage.ERROR, "pipeline failed", error=str(exc))


async def _finish_pipeline(
    job: Job, frame_paths: list[Path], roi: ROISpec, hints: Hints, jdir: Path
) -> None:
    # 3. OCR counters.
    _emit(job, Stage.OCR, "reading slice counters")
    ocr_report = OCRReport(frames_total=len(frame_paths))
    readings = []
    try:
        lock = await asyncio.to_thread(
            ocr.lock_counter, frame_paths, roi, config.OCR_SAMPLE_FRAMES
        )
        if lock is not None:
            readings = await asyncio.to_thread(ocr.read_counters, frame_paths, lock)
            ocr_report.counter_found = True
            ocr_report.detected_format = lock.fmt
            ocr_report.frames_confident = sum(1 for r in readings if r.valid)
    except Exception:
        # OCR is best-effort; fall back to content-based ordering.
        readings = []

    # 4. Classify + order into a (slice, timepoint) grid.
    _emit(job, Stage.ORDER, "ordering frames")
    modality = ordering.classify(readings, job.modality_hint)
    if not readings:
        readings = [ordering.CounterReading() for _ in frame_paths]
    grid = await asyncio.to_thread(
        ordering.build_grid, frame_paths, readings, modality, hints, config.DEDUP_HASH_THRESHOLD
    )

    # 5. Assemble numpy volume. Keep RGB for cine (color Doppler/angiography).
    _emit(job, Stage.ASSEMBLE, "assembling volume")
    rgb = modality == Modality.CINE
    arr, output_kind = await asyncio.to_thread(volume_mod.assemble, grid, roi, rgb)

    # 6. Write NIfTI + metadata.
    _emit(job, Stage.WRITE, "writing volume")
    out_path = jdir / "volume.nii.gz"
    await asyncio.to_thread(nifti_writer.write_nifti, arr, out_path, output_kind)

    note = _note_for(output_kind)
    meta = VolumeMeta(
        output_kind=output_kind,
        modality=modality,
        shape=list(arr.shape),
        is_rgb=rgb,
        note=note,
        ocr=ocr_report,
        completeness=grid.completeness if grid.completeness else CompletenessReport(),
    )
    (jdir / "volume.json").write_text(meta.model_dump_json(indent=2))
    _emit(job, Stage.DONE, "done", meta=meta)


def _note_for(kind: OutputKind) -> str:
    if kind == OutputKind.CINE_2D_TIME:
        return (
            "Single-viewpoint cine loop (echo/cath). This is 2D + time, not a "
            "rotatable 3D volume — true 3D needs multiple view angles. "
            "Reconstructed from a lossy screen recording; not for primary diagnosis."
        )
    return (
        "Reconstructed from a lossy screen recording; spacing is assumed (no DICOM "
        "metadata) so measurements are not metrically accurate. Not for primary diagnosis."
    )
