"""Automatic detection of the image region within recorded frames.

A PACS screen recording is mostly static UI (toolbars, patient banner) surrounding
a medical image that changes a lot as the user scrolls. We combine two cues:

1. **Temporal variance** — the scrolling image area changes frame-to-frame; chrome
   does not. The high-variance region is the image.
2. **Dark rectangle** — medical images sit on a near-black background. The largest
   stable dark rectangle is a strong second vote.

The intersection of the two votes is returned as the suggested ROI. The user can
always override it with a manual crop in the UI.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..models import ROISpec


def _sample_paths(frames: list[Path], n: int) -> list[Path]:
    if len(frames) <= n:
        return frames
    idx = np.linspace(0, len(frames) - 1, n).astype(int)
    return [frames[i] for i in idx]


def _largest_rect_from_mask(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """Bounding box of the largest connected component in a binary mask."""
    mask = (mask > 0).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return None
    # Skip background label 0; pick the component with the largest area.
    areas = stats[1:, cv2.CC_STAT_AREA]
    best = 1 + int(np.argmax(areas))
    x = int(stats[best, cv2.CC_STAT_LEFT])
    y = int(stats[best, cv2.CC_STAT_TOP])
    w = int(stats[best, cv2.CC_STAT_WIDTH])
    h = int(stats[best, cv2.CC_STAT_HEIGHT])
    return x, y, w, h


def _dark_rect_with_motion(
    dark_mask: np.ndarray, var_mask: np.ndarray
) -> tuple[int, int, int, int] | None:
    """Pick the dark connected component that contains the most motion.

    The image panel is both dark (black background) and the only region with strong
    temporal variance, so scoring dark components by the variance they enclose finds
    the full panel bounding box (not just the sub-area the content moved through)."""
    dark = (dark_mask > 0).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    if n <= 1:
        return None
    var = (var_mask > 0).astype(np.uint8)
    best_label, best_score = None, -1
    for lbl in range(1, n):
        score = int(var[labels == lbl].sum())
        if score > best_score:
            best_score, best_label = score, lbl
    if best_label is None or best_score <= 0:
        return None
    x = int(stats[best_label, cv2.CC_STAT_LEFT])
    y = int(stats[best_label, cv2.CC_STAT_TOP])
    w = int(stats[best_label, cv2.CC_STAT_WIDTH])
    h = int(stats[best_label, cv2.CC_STAT_HEIGHT])
    return x, y, w, h


def detect_roi(frames: list[Path], sample: int = 40) -> ROISpec:
    """Return a suggested image ROI for the recording."""
    paths = _sample_paths(frames, sample)
    grays = []
    for p in paths:
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            grays.append(img)
    if not grays:
        raise ValueError("no readable frames for ROI detection")

    # Resize all to the first frame's shape just in case.
    h0, w0 = grays[0].shape
    stack = np.stack([cv2.resize(g, (w0, h0)) for g in grays]).astype(np.float32)

    # Cue 1: temporal variance map.
    var = stack.var(axis=0)
    var_norm = cv2.normalize(var, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, var_mask = cv2.threshold(var_norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    var_mask = cv2.morphologyEx(
        var_mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)
    )

    # Cue 2: dark region (mean brightness low across time).
    mean = stack.mean(axis=0).astype(np.uint8)
    dark_mask = (mean < 60).astype(np.uint8) * 255
    dark_mask = cv2.morphologyEx(
        dark_mask, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8)
    )

    var_rect = _largest_rect_from_mask(var_mask)
    # Prefer the dark panel that encloses the motion (full image bounding box);
    # fall back to the variance region alone; then the full frame.
    dark_rect = _dark_rect_with_motion(dark_mask, var_mask)
    rect = dark_rect or var_rect
    if rect is None or rect[2] * rect[3] < 0.04 * w0 * h0:
        rect = (0, 0, w0, h0)

    x, y, w, h = rect
    return ROISpec(x=x, y=y, width=w, height=h)
