import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from soma.processing.roi import detect_roi


def _make_frames(tmp_path, n=20):
    """Synthesize frames: a dark image panel (changing) inside a light UI border."""
    H, W = 300, 400
    # Image panel occupies x:100..300, y:60..260 (200x200) on near-black bg.
    px, py, pw, ph = 100, 60, 200, 200
    paths = []
    for i in range(n):
        frame = np.full((H, W, 3), 200, np.uint8)  # light UI chrome
        panel = np.zeros((ph, pw, 3), np.uint8)  # dark image background
        # A moving bright blob so the panel has high temporal variance.
        cx = 20 + (i * 7) % (pw - 40)
        cy = 20 + (i * 5) % (ph - 40)
        cv2.circle(panel, (cx, cy), 18, (255, 255, 255), -1)
        frame[py : py + ph, px : px + pw] = panel
        p = tmp_path / f"frame_{i:04d}.png"
        cv2.imwrite(str(p), frame)
        paths.append(p)
    return paths, (px, py, pw, ph)


def test_detect_roi_finds_dark_panel(tmp_path):
    frames, (px, py, pw, ph) = _make_frames(tmp_path)
    roi = detect_roi(frames, sample=20)
    # Detected ROI should overlap heavily with the true panel.
    ix = max(roi.x, px)
    iy = max(roi.y, py)
    ax = min(roi.x + roi.width, px + pw)
    ay = min(roi.y + roi.height, py + ph)
    inter = max(0, ax - ix) * max(0, ay - iy)
    union = roi.width * roi.height + pw * ph - inter
    iou = inter / union
    assert iou > 0.5, f"IoU too low: {iou:.2f} roi={roi}"
