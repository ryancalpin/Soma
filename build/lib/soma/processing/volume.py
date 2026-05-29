"""Assemble an ordered frame grid into a numpy volume."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from ..models import Modality, OutputKind, ROISpec
from .ordering import GridResult


def _load_crop(path: Path, roi: ROISpec, size: tuple[int, int], rgb: bool) -> np.ndarray:
    """Load a frame, crop to ROI and resize to a common (w,h)."""
    flag = cv2.IMREAD_COLOR if rgb else cv2.IMREAD_GRAYSCALE
    img = cv2.imread(str(path), flag)
    if img is None:
        return np.zeros((size[1], size[0], 3) if rgb else (size[1], size[0]), np.uint8)
    crop = img[roi.y : roi.y + roi.height, roi.x : roi.x + roi.width]
    crop = cv2.resize(crop, size, interpolation=cv2.INTER_AREA)
    if rgb:
        crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    return crop


def assemble(
    grid: GridResult,
    roi: ROISpec,
    rgb: bool = False,
    in_plane: int = 256,
) -> tuple[np.ndarray, OutputKind]:
    """Build the numpy array and report its output kind.

    Returns array shaped:
      - [Z,Y,X]      for a single 3D volume
      - [T,Z,Y,X]    for a 4D series
      - [T,Y,X(,3)]  for a 2D+time cine
    Missing cells are filled with the nearest present slice (never fabricated detail).
    """
    # Choose a common in-plane size preserving aspect of the ROI.
    aspect = roi.height / roi.width if roi.width else 1.0
    w = in_plane
    h = max(1, int(round(in_plane * aspect)))
    size = (w, h)

    if grid.modality == Modality.CINE:
        row = grid.frame_grid[0]
        slices = [_load_crop(p, roi, size, rgb) for p in row if p is not None]
        arr = np.stack(slices) if slices else np.zeros((1, h, w), np.uint8)
        return arr, OutputKind.CINE_2D_TIME

    # CT/MRI volume(s). Fill gaps per-timepoint by nearest present slice.
    volumes = []
    for row in grid.frame_grid:
        filled = _fill_row(row)
        slices = [_load_crop(p, roi, size, rgb) for p in filled]
        volumes.append(np.stack(slices))
    vol4d = np.stack(volumes)  # [T,Z,Y,X(,3)]

    if grid.n_timepoints <= 1:
        return vol4d[0], OutputKind.VOLUME_3D
    return vol4d, OutputKind.VOLUME_4D


def _fill_row(row: list[Optional[Path]]) -> list[Path]:
    """Replace None cells with the nearest non-None neighbour."""
    n = len(row)
    present_idx = [i for i, p in enumerate(row) if p is not None]
    if not present_idx:
        raise ValueError("a timepoint has no usable frames")
    out: list[Path] = []
    for i in range(n):
        if row[i] is not None:
            out.append(row[i])  # type: ignore[arg-type]
        else:
            j = min(present_idx, key=lambda k: abs(k - i))
            out.append(row[j])  # type: ignore[arg-type]
    return out
