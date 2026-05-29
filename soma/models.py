"""Pydantic models shared across the API and pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Stage(str, Enum):
    """Pipeline stages, surfaced to the UI for progress reporting."""

    QUEUED = "queued"
    PROBE = "probe"
    EXTRACT = "extract"
    ROI = "roi"
    AWAIT_ROI = "await_roi"  # paused for the user to confirm/correct the crop
    OCR = "ocr"
    ORDER = "order"
    ASSEMBLE = "assemble"
    WRITE = "write"
    DONE = "done"
    ERROR = "error"


class Modality(str, Enum):
    """How a recording should be interpreted."""

    AUTO = "auto"
    CT_MRI = "ct_mri"  # scroll-through -> true 3D / 4D volume
    CINE = "cine"  # echo / cath -> single-view 2D + time loop


class OutputKind(str, Enum):
    """Shape of the reconstructed output."""

    VOLUME_3D = "volume_3d"
    VOLUME_4D = "volume_4d"
    CINE_2D_TIME = "cine_2d_time"


class ROISpec(BaseModel):
    """A rectangle (pixels) marking the image region within a frame."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class Hints(BaseModel):
    """Optional manual structure hints used when OCR cannot recover the grid."""

    slices: Optional[int] = Field(default=None, gt=0)
    timepoints: Optional[int] = Field(default=None, gt=0)


class OCRReport(BaseModel):
    frames_total: int = 0
    frames_confident: int = 0
    counter_found: bool = False
    detected_format: Optional[str] = None


class CompletenessReport(BaseModel):
    expected_slices: int = 0
    present_slices: int = 0
    missing_slices: list[int] = Field(default_factory=list)
    timepoints: int = 1


class VolumeMeta(BaseModel):
    """Description of the reconstructed output, written as volume.json."""

    output_kind: OutputKind
    modality: Modality
    shape: list[int]  # [Z,Y,X] or [T,Z,Y,X] or [T,Y,X]
    is_rgb: bool = False
    z_aspect: float = 1.0
    note: str = ""
    ocr: OCRReport = Field(default_factory=OCRReport)
    completeness: CompletenessReport = Field(default_factory=CompletenessReport)


class JobStatus(BaseModel):
    job_id: str
    stage: Stage
    progress: float = 0.0  # 0..1 within the overall pipeline
    message: str = ""
    error: Optional[str] = None
    suggested_roi: Optional[ROISpec] = None
    meta: Optional[VolumeMeta] = None
