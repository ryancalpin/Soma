"""Turn frames + counter readings into an ordered (slice, timepoint) grid.

Handles:
- **Dedup**: a clinician pausing on a slice yields many identical frames.
- **Non-monotonic scrolling**: ordering is by OCR slice index, not frame order, so
  scrolling back and forth just produces multiple samples of the same slice.
- **4D detection**: when the slice index sweeps to ``total`` and resets toward 1, a
  new timepoint has begun.
- **Fallback**: when no counter was read, assume a monotonic single sweep and order
  by frame index, optionally guided by a user-provided slice count hint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import imagehash
from PIL import Image

from ..models import CompletenessReport, Hints, Modality
from .counters import CounterReading


@dataclass
class GridResult:
    # frame_grid[t][z] -> frame Path (or None if missing)
    frame_grid: list[list[Optional[Path]]]
    n_slices: int
    n_timepoints: int
    modality: Modality
    completeness: CompletenessReport = field(default_factory=CompletenessReport)


def _phash(path: Path) -> imagehash.ImageHash:
    with Image.open(path) as im:
        return imagehash.phash(im.convert("L"))


def classify(readings: list[CounterReading], hint: Modality) -> Modality:
    """Decide CT/MRI vs cine when modality is AUTO."""
    if hint != Modality.AUTO:
        return hint
    slice_vals = [r.slice for r in readings if r.slice is not None]
    distinct = len(set(slice_vals))
    # A real scroll-through sweeps many distinct slice indices.
    if distinct >= 5:
        return Modality.CT_MRI
    return Modality.CINE


def _dedup_consecutive(frames: list[Path], threshold: int) -> list[int]:
    """Return indices of frames to keep, dropping near-identical neighbours."""
    keep = []
    last_hash = None
    for i, p in enumerate(frames):
        h = _phash(p)
        if last_hash is None or (h - last_hash) > threshold:
            keep.append(i)
            last_hash = h
    return keep


def build_grid(
    frames: list[Path],
    readings: list[CounterReading],
    modality: Modality,
    hints: Hints,
    dedup_threshold: int,
) -> GridResult:
    """Assemble the ordered frame grid."""
    if modality == Modality.CINE:
        return _build_cine(frames, dedup_threshold)
    return _build_volume(frames, readings, hints, dedup_threshold)


def _build_cine(frames: list[Path], dedup_threshold: int) -> GridResult:
    """Echo/cath: keep temporal order, one row of timepoints (no spatial axis)."""
    keep = _dedup_consecutive(frames, dedup_threshold) or list(range(len(frames)))
    row = [frames[i] for i in keep]
    return GridResult(
        frame_grid=[row],
        n_slices=1,
        n_timepoints=len(row),
        modality=Modality.CINE,
        completeness=CompletenessReport(
            expected_slices=1, present_slices=1, timepoints=len(row)
        ),
    )


def _build_volume(
    frames: list[Path],
    readings: list[CounterReading],
    hints: Hints,
    dedup_threshold: int,
) -> GridResult:
    have_counter = any(r.slice is not None for r in readings)
    if have_counter:
        return _build_volume_from_counters(frames, readings)
    return _build_volume_fallback(frames, hints, dedup_threshold)


def _build_volume_from_counters(
    frames: list[Path], readings: list[CounterReading]
) -> GridResult:
    """Use OCR slice indices to place each frame; detect 4D via index resets."""
    total = _infer_total(readings)
    # Walk frames; a drop in slice index (after having advanced) starts a new timepoint.
    timepoint = 0
    prev_slice = None
    # grid[t][z] -> best frame for that (slice,timepoint)
    grid: list[dict[int, Path]] = [dict()]
    for path, r in zip(frames, readings):
        if r.slice is None:
            continue
        s = r.slice
        if prev_slice is not None and s < prev_slice - 1:
            # Reset toward the start -> new timepoint.
            timepoint += 1
            grid.append(dict())
        prev_slice = s
        if 1 <= s <= total:
            grid[timepoint].setdefault(s, path)  # first confident sample wins

    n_t = len(grid)
    present = sorted({s for tp in grid for s in tp})
    missing = [s for s in range(1, total + 1) if s not in set(present)]

    frame_grid: list[list[Optional[Path]]] = []
    for tp in grid:
        row: list[Optional[Path]] = [tp.get(s) for s in range(1, total + 1)]
        frame_grid.append(row)

    return GridResult(
        frame_grid=frame_grid,
        n_slices=total,
        n_timepoints=n_t,
        modality=Modality.CT_MRI,
        completeness=CompletenessReport(
            expected_slices=total,
            present_slices=len(present),
            missing_slices=missing,
            timepoints=n_t,
        ),
    )


def _build_volume_fallback(
    frames: list[Path], hints: Hints, dedup_threshold: int
) -> GridResult:
    """No counter: dedup, assume a single monotonic sweep ordered by frame index."""
    keep = _dedup_consecutive(frames, dedup_threshold) or list(range(len(frames)))
    kept = [frames[i] for i in keep]

    if hints.slices and hints.timepoints:
        n_s, n_t = hints.slices, hints.timepoints
    elif hints.slices:
        n_s = hints.slices
        n_t = max(1, len(kept) // n_s)
    else:
        n_s, n_t = len(kept), 1

    frame_grid: list[list[Optional[Path]]] = []
    for t in range(n_t):
        row: list[Optional[Path]] = []
        for z in range(n_s):
            i = t * n_s + z
            row.append(kept[i] if i < len(kept) else None)
        frame_grid.append(row)

    return GridResult(
        frame_grid=frame_grid,
        n_slices=n_s,
        n_timepoints=n_t,
        modality=Modality.CT_MRI,
        completeness=CompletenessReport(
            expected_slices=n_s, present_slices=min(n_s, len(kept)), timepoints=n_t
        ),
    )


def _infer_total(readings: list[CounterReading]) -> int:
    """Best estimate of slices-per-volume from the readings."""
    totals = [r.total for r in readings if r.total]
    if totals:
        # The modal reported total is the most reliable.
        return max(set(totals), key=totals.count)
    slices = [r.slice for r in readings if r.slice]
    return max(slices) if slices else 1
