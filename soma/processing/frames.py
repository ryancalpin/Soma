"""Probe a recording and extract its frames using the pip-bundled ffmpeg binary.

We rely on ``imageio-ffmpeg`` so there is no system ffmpeg dependency — the whole
backend installs from pip alone.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg


@dataclass
class ProbeResult:
    width: int
    height: int
    fps: float
    duration: float
    n_frames_est: int


def _ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe(video_path: Path) -> ProbeResult:
    """Read basic stream info. Uses ffmpeg's stderr banner (no separate ffprobe)."""
    exe = _ffmpeg_exe()
    # `-` output forces ffmpeg to print stream info then error out cheaply.
    proc = subprocess.run(
        [exe, "-i", str(video_path)],
        capture_output=True,
        text=True,
    )
    text = proc.stderr
    width = height = 0
    fps = 0.0
    duration = 0.0

    import re

    m = re.search(r"(\d{2,5})x(\d{2,5})", text)
    if m:
        width, height = int(m.group(1)), int(m.group(2))
    m = re.search(r"([\d.]+)\s*fps", text)
    if m:
        fps = float(m.group(1))
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", text)
    if m:
        h, mnt, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        duration = h * 3600 + mnt * 60 + s

    n_frames_est = int(duration * fps) if duration and fps else 0
    return ProbeResult(width, height, fps or 0.0, duration, n_frames_est)


def extract_frames(
    video_path: Path,
    out_dir: Path,
    max_frames: int,
    fps: float | None = None,
) -> list[Path]:
    """Extract frames to ``out_dir`` as zero-padded PNGs.

    If the recording would exceed ``max_frames`` we decimate by selecting evenly
    spaced frames via ffmpeg's ``select`` filter so memory/disk stays bounded.

    Returns the sorted list of extracted frame paths.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    exe = _ffmpeg_exe()

    info = probe(video_path)
    n_est = info.n_frames_est or max_frames
    pattern = str(out_dir / "frame_%06d.png")

    cmd = [exe, "-y", "-i", str(video_path)]
    if n_est > max_frames and n_est > 0:
        # Keep every Nth frame so the total lands near max_frames.
        step = max(1, round(n_est / max_frames))
        cmd += ["-vf", f"select='not(mod(n\\,{step}))'", "-vsync", "vfr"]
    cmd += [pattern]

    subprocess.run(cmd, capture_output=True, text=True, check=True)
    frames = sorted(out_dir.glob("frame_*.png"))

    # Record extraction metadata for downstream stages / debugging.
    (out_dir.parent / "frames.json").write_text(
        json.dumps(
            {
                "count": len(frames),
                "source_fps": info.fps,
                "source_size": [info.width, info.height],
                "duration": info.duration,
            },
            indent=2,
        )
    )
    return frames
