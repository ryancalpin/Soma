"""Read PACS slice/phase counters from frames using EasyOCR.

Strategy (counter-ROI locking):
1. Counters live in the UI margins, *outside* the image ROI, in a fixed screen
   location. We OCR a sample of frames over the full margin region, keep only text
   boxes that parse as counters, and pick the box position that recurs most often.
2. For the full run we OCR just that small locked box per frame — fast and robust.

EasyOCR downloads model weights on first use. To honour the offline/PHI promise the
weights should be pre-placed in ``config.MODELS_DIR``; we point EasyOCR there.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .. import config
from ..models import ROISpec
from .counters import CounterReading, parse_counter

_reader = None


def _get_reader():
    """Lazily construct the EasyOCR reader (English, CPU)."""
    global _reader
    if _reader is None:
        import easyocr  # imported lazily; heavy dependency

        config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        _reader = easyocr.Reader(
            ["en"],
            gpu=False,
            model_storage_directory=str(config.MODELS_DIR),
            download_enabled=True,
        )
    return _reader


@dataclass
class CounterLock:
    """A locked counter box (in full-frame pixel coords)."""

    box: ROISpec
    fmt: str


def _preprocess(img: np.ndarray) -> np.ndarray:
    """Upscale + grayscale to help OCR on small antialiased UI text."""
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    return img


def _read_text(img: np.ndarray) -> list[tuple[tuple[int, int, int, int], str]]:
    """Return list of (bbox_xywh, text) detections in the given image's coords."""
    reader = _get_reader()
    results = reader.readtext(_preprocess(img))
    out = []
    for bbox, text, conf in results:
        xs = [p[0] / 2.0 for p in bbox]  # undo 2x upscale
        ys = [p[1] / 2.0 for p in bbox]
        x, y = int(min(xs)), int(min(ys))
        w, h = int(max(xs) - x), int(max(ys) - y)
        out.append(((x, y, w, h), text))
    return out


def _mask_image_region(frame: np.ndarray, image_roi: ROISpec) -> np.ndarray:
    """Black out the anatomy so OCR only sees UI margins."""
    f = frame.copy()
    f[image_roi.y : image_roi.y + image_roi.height,
      image_roi.x : image_roi.x + image_roi.width] = 0
    return f


def lock_counter(frames: list[Path], image_roi: ROISpec, sample: int) -> Optional[CounterLock]:
    """Find a stable on-screen counter box by sampling frames."""
    if len(frames) <= sample:
        paths = frames
    else:
        idx = np.linspace(0, len(frames) - 1, sample).astype(int)
        paths = [frames[i] for i in idx]

    # Accumulate counter detections by approximate position (grid-binned).
    votes: dict[tuple[int, int], dict] = {}
    for p in paths:
        frame = cv2.imread(str(p))
        if frame is None:
            continue
        masked = _mask_image_region(frame, image_roi)
        for (x, y, w, h), text in _read_text(masked):
            reading = parse_counter(text)
            if not reading.valid or reading.total is None:
                continue
            key = (x // 20, y // 20)  # bin to tolerate jitter
            slot = votes.setdefault(key, {"count": 0, "box": (x, y, w, h), "fmt": reading.fmt})
            slot["count"] += 1

    if not votes:
        return None
    best = max(votes.values(), key=lambda s: s["count"])
    x, y, w, h = best["box"]
    # Pad the locked box a little to be safe.
    pad = 6
    box = ROISpec(x=max(0, x - pad), y=max(0, y - pad), width=w + 2 * pad, height=h + 2 * pad)
    return CounterLock(box=box, fmt=best["fmt"] or "unknown")


def read_counters(frames: list[Path], lock: CounterLock) -> list[CounterReading]:
    """Read the counter from the locked box for every frame."""
    readings: list[CounterReading] = []
    b = lock.box
    for p in frames:
        frame = cv2.imread(str(p))
        if frame is None:
            readings.append(CounterReading())
            continue
        crop = frame[b.y : b.y + b.height, b.x : b.x + b.width]
        best = CounterReading()
        for _, text in _read_text(crop):
            r = parse_counter(text)
            if r.valid:
                best = r
                break
        readings.append(best)
    return readings
