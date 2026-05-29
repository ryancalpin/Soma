from pathlib import Path

from soma.models import Hints, Modality
from soma.processing.counters import CounterReading
from soma.processing import ordering


def _paths(n):
    # The counter-based grid builder never reads file contents, only uses identity.
    return [Path(f"/tmp/frame_{i:04d}.png") for i in range(n)]


def _read(slice_, total):
    return CounterReading(slice=slice_, total=total, fmt="k/total")


def test_classify_ct_when_many_slices():
    readings = [_read(i, 10) for i in range(1, 11)]
    assert ordering.classify(readings, Modality.AUTO) == Modality.CT_MRI


def test_classify_cine_when_few_distinct():
    readings = [_read(1, 1) for _ in range(20)]
    assert ordering.classify(readings, Modality.AUTO) == Modality.CINE


def test_volume_from_counters_3d():
    n = 10
    frames = _paths(n)
    readings = [_read(i + 1, n) for i in range(n)]
    grid = ordering.build_grid(frames, readings, Modality.CT_MRI, Hints(), dedup_threshold=4)
    assert grid.n_timepoints == 1
    assert grid.n_slices == 10
    assert grid.frame_grid[0][0] == frames[0]
    assert grid.completeness.present_slices == 10
    assert grid.completeness.missing_slices == []


def test_volume_from_counters_4d_reset():
    # Two sweeps 1..5, 1..5 -> two timepoints.
    seq = list(range(1, 6)) + list(range(1, 6))
    frames = _paths(len(seq))
    readings = [_read(s, 5) for s in seq]
    grid = ordering.build_grid(frames, readings, Modality.CT_MRI, Hints(), dedup_threshold=4)
    assert grid.n_timepoints == 2
    assert grid.n_slices == 5


def test_volume_non_monotonic_ordered_by_index():
    # Scroll forward then back; indices still map to correct slice positions.
    seq = [1, 2, 3, 2, 3, 4, 5]
    frames = _paths(len(seq))
    readings = [_read(s, 5) for s in seq]
    grid = ordering.build_grid(frames, readings, Modality.CT_MRI, Hints(), dedup_threshold=4)
    # No spurious extra timepoint from the single step-back (3->2 is within 1).
    assert grid.n_timepoints == 1
    # Slice 1 keeps its first sample.
    assert grid.frame_grid[0][0] == frames[0]
