"""Application configuration and shared paths."""

from __future__ import annotations

import os
from pathlib import Path

# Repository / package roots.
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent

# Where per-job working directories live. On the portable USB build the launcher
# points SOMA_DATA_DIR at a folder next to the app so recordings stay on the stick.
DATA_DIR = Path(os.environ.get("SOMA_DATA_DIR", PROJECT_ROOT / "data"))
JOBS_DIR = DATA_DIR / "jobs"

# Built frontend assets served by FastAPI.
STATIC_DIR = PACKAGE_DIR / "static"

# Server binding. Local-only by default — patient data must never leave the machine.
HOST = os.environ.get("SOMA_HOST", "127.0.0.1")
PORT = int(os.environ.get("SOMA_PORT", "8000"))

# Frame-extraction guardrails. Screen recordings can be long; cap total frames so a
# single upload cannot exhaust memory/disk. Frames beyond the cap are decimated evenly.
MAX_FRAMES = int(os.environ.get("SOMA_MAX_FRAMES", "4000"))

# During OCR auto-locking we only inspect a sample of frames to find the counter text
# location (it is stable across the recording).
OCR_SAMPLE_FRAMES = int(os.environ.get("SOMA_OCR_SAMPLE_FRAMES", "40"))

# Perceptual-hash distance below which two frames are considered duplicates.
DEDUP_HASH_THRESHOLD = int(os.environ.get("SOMA_DEDUP_THRESHOLD", "4"))


def ensure_dirs() -> None:
    """Create the data directories if they do not yet exist."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def job_dir(job_id: str) -> Path:
    """Return (and create) the working directory for a job."""
    d = JOBS_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d
