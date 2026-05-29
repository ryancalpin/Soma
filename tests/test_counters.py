from soma.processing.counters import parse_counter


def test_image_slash_total():
    r = parse_counter("Im: 45/120")
    assert r.slice == 45 and r.total == 120 and r.valid


def test_image_of_total():
    r = parse_counter("Image 45 of 120")
    assert r.slice == 45 and r.total == 120


def test_slice_slash():
    r = parse_counter("Slice 45/200")
    assert r.slice == 45 and r.total == 200


def test_bare_slash():
    r = parse_counter("45/120")
    assert r.slice == 45 and r.total == 120


def test_series_slice_total():
    r = parse_counter("1:45/120")
    assert r.series == 1 and r.slice == 45 and r.total == 120


def test_phase():
    r = parse_counter("Phase 7/20")
    assert r.phase == 7 and r.phase_total == 20


def test_series_only():
    r = parse_counter("Se: 3")
    assert r.series == 3


def test_rejects_current_gt_total():
    # A misread like 200/120 must be rejected, not accepted as a slice.
    r = parse_counter("200/120")
    assert not (r.slice == 200 and r.total == 120)


def test_empty():
    assert not parse_counter("").valid
    assert not parse_counter("no numbers here").valid
