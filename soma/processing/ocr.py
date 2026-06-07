"""Read PACS slice/phase counters from frames using RapidOCR (ONNX runtime).

RapidOCR bundles its detection/recognition models inside the package, so there is
no first-run download — the portable USB build works fully offline.

Strategy (counter-ROI locking):
1. Counters live in the UI margins, *outside* the image ROI, in a fixed screen
   location. We OCR a sample of frames over the margins, keep only text that parses
   as a counter, and pick the position that recurs most often.
2. For the full run we OCR just that small locked box per frame.

The OCR engine often splits a counter like "Im: 45/120" into fragments
("Im:", "45/", "/120"), so we join detections in reading order before parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from ..models import ROISpec
from .counters import CounterReading, parse_counter

_engine = None


def _get_engine():
    """Lazily construct the RapidOCR engine (CPU, models bundled in the wheel)."""
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


@dataclass
class CounterLock:
    """A locked counter box (in full-frame pixel coords)."""

    box: ROISpec
    fmt: str


@dataclass
class _Det:
    x: int
    y: int
    w: int
    h: int
    text: str


def _preprocess(img: np.ndarray, upscale: float) -> tuple[np.ndarray, float]:
    """Optionally upscale small UI text to help OCR. Returns (image, scale)."""
    if upscale == 1.0:
        return img, 1.0
    up = cv2.resize(img, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    return up, upscale


def _detect(img: np.ndarray, upscale: float = 2.0) -> list[_Det]:
    """Run OCR and return detections in full-frame (input) pixel coords.

    The locking pass scans whole screens, so it runs at native resolution
    (``upscale=1``) for speed; the per-frame read pass works on a tiny crop where
    a 2x upscale is cheap and improves recognition of small counters.
    """
    if img.size == 0:
        return []
    up, scale = _preprocess(img, upscale)
    result, _ = _get_engine()(up)
    dets: list[_Det] = []
    for box, text, _conf in result or []:
        xs = [p[0] / scale for p in box]
        ys = [p[1] / scale for p in box]
        x, y = int(min(xs)), int(min(ys))
        w, h = int(max(xs) - x), int(max(ys) - y)
        dets.append(_Det(x, y, w, h, text))
    return dets


def _normalize(text: str) -> str:
    """Collapse whitespace and repeated slashes so split fragments re-parse."""
    t = re.sub(r"\s+", "", text)
    t = re.sub(r"/{2,}", "/", t)
    return t


def _find_counter(dets: list[_Det]) -> Optional[tuple[CounterReading, ROISpec]]:
    """Find a counter among detections, joining up to 3 fragments on a line.

    Returns the reading and the union bounding box of the contributing fragments.
    """
    # Group into reading order: bucket by line (~y), then sort by x.
    ordered = sorted(dets, key=lambda d: (round(d.y / 15), d.x))
    n = len(ordered)
    for i in range(n):
        for span in (1, 2, 3):
            group = ordered[i : i + span]
            if len(group) < span:
                break
            joined = _normalize("".join(g.text for g in group))
            reading = parse_counter(joined)
            if reading.valid and reading.total is not None:
                x = min(g.x for g in group)
                y = min(g.y for g in group)
                x2 = max(g.x + g.w for g in group)
                y2 = max(g.y + g.h for g in group)
                return reading, ROISpec(x=x, y=y, width=x2 - x, height=y2 - y)
    return None


def _mask_image_region(frame: np.ndarray, image_roi: ROISpec) -> np.ndarray:
    """Black out the anatomy so OCR only sees UI margins."""
    f = frame.copy()
    f[image_roi.y : image_roi.y + image_roi.height,
      image_roi.x : image_roi.x + image_roi.width] = 0
    return f


def _sample(frames: list[Path], n: int) -> list[Path]:
    if len(frames) <= n:
        return frames
    idx = np.linspace(0, len(frames) - 1, n).astype(int)
    return [frames[i] for i in idx]


def lock_counter(frames: list[Path], image_roi: ROISpec, sample: int) -> Optional[CounterLock]:
    """Find a stable on-screen counter box by sampling frames."""
    votes: dict[tuple[int, int], dict] = {}
    for p in _sample(frames, sample):
        frame = cv2.imread(str(p))
        if frame is None:
            continue
        masked = _mask_image_region(frame, image_roi)
        found = _find_counter(_detect(masked, upscale=1.0))  # whole screen: native res
        if not found:
            continue
        reading, box = found
        key = (box.x // 20, box.y // 20)  # bin to tolerate jitter
        slot = votes.setdefault(key, {"count": 0, "box": box, "fmt": reading.fmt})
        slot["count"] += 1
        # Grow the box to the union seen at this position, so a widening index
        # (e.g. "1/200" -> "199/200") is never clipped on later frames.
        u = slot["box"]
        ux, uy = min(u.x, box.x), min(u.y, box.y)
        ux2 = max(u.x + u.width, box.x + box.width)
        uy2 = max(u.y + u.height, box.y + box.height)
        slot["box"] = ROISpec(x=ux, y=uy, width=ux2 - ux, height=uy2 - uy)

    if not votes:
        return None
    best = max(votes.values(), key=lambda s: s["count"])
    box = best["box"]
    pad = 10  # small safety margin around the unioned box
    padded = ROISpec(
        x=max(0, box.x - pad),
        y=max(0, box.y - pad),
        width=box.width + 2 * pad,
        height=box.height + 2 * pad,
    )
    return CounterLock(box=padded, fmt=best["fmt"] or "unknown")


def _recognize(crop: np.ndarray) -> str:
    """Recognition-only OCR of a known text region (no detection) — ~100x faster.

    The locked box already isolates the counter, so we skip the heavy text-detection
    model and only run recognition on the (upscaled) crop, reading it as one line.
    """
    if crop.size == 0:
        return ""
    up, _ = _preprocess(crop, 2.0)
    result, _ = _get_engine()(up, use_det=False, use_cls=False, use_rec=True)
    if not result:
        return ""
    return " ".join(r[0] for r in result)


def read_counters(frames: list[Path], lock: CounterLock) -> list[CounterReading]:
    """Read the counter from the locked box for every frame (recognition-only)."""
    readings: list[CounterReading] = []
    b = lock.box
    for p in frames:
        frame = cv2.imread(str(p))
        if frame is None:
            readings.append(CounterReading())
            continue
        crop = frame[b.y : b.y + b.height, b.x : b.x + b.width]
        text = _recognize(crop)
        reading = parse_counter(text)
        if not reading.valid:
            reading = parse_counter(_normalize(text))
        readings.append(reading)
    return readings
