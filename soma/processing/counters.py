"""Parse PACS on-screen slice/series/phase counters from OCR text.

Different vendors render counters differently; we match the common formats and
extract a structured reading. Examples handled:

    "Im: 45/120"        -> slice 45 of 120
    "Image 45 of 120"   -> slice 45 of 120
    "Slice 45/200"      -> slice 45 of 200
    "45/120"            -> slice 45 of 120
    "Se: 3"             -> series 3
    "Series 3"          -> series 3
    "Phase 7/20"        -> phase/time 7 of 20
    "1:45/120"          -> series 1, slice 45 of 120
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Ordered most-specific first. Each pattern yields named groups we interpret below.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("series:slice/total", re.compile(r"\b(\d+)\s*:\s*(\d+)\s*/\s*(\d+)\b")),
    ("phase k/total", re.compile(r"(?:phase|ph|frame|time)\s*[:#]?\s*(\d+)\s*/\s*(\d+)", re.I)),
    ("image k/total", re.compile(r"(?:im(?:age)?|sl(?:ice)?)\s*[:#]?\s*(\d+)\s*/\s*(\d+)", re.I)),
    ("k of total", re.compile(r"\b(\d+)\s*of\s*(\d+)\b", re.I)),
    ("k/total", re.compile(r"\b(\d+)\s*/\s*(\d+)\b")),
    ("series", re.compile(r"(?:se(?:ries)?)\s*[:#]?\s*(\d+)", re.I)),
]


@dataclass
class CounterReading:
    slice: Optional[int] = None
    total: Optional[int] = None
    series: Optional[int] = None
    phase: Optional[int] = None
    phase_total: Optional[int] = None
    fmt: Optional[str] = None

    @property
    def valid(self) -> bool:
        if self.slice is not None and self.total is not None:
            return 1 <= self.slice <= self.total
        return self.slice is not None or self.phase is not None


def parse_counter(text: str) -> CounterReading:
    """Parse a single OCR text string into a CounterReading.

    Rejects readings where current > total (a strong sign of a misread)."""
    if not text:
        return CounterReading()
    t = text.strip()

    for name, pat in _PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        if name == "series:slice/total":
            r = CounterReading(series=g[0], slice=g[1], total=g[2], fmt=name)
        elif name == "phase k/total":
            r = CounterReading(phase=g[0], phase_total=g[1], fmt=name)
        elif name in ("image k/total", "k of total", "k/total"):
            r = CounterReading(slice=g[0], total=g[1], fmt=name)
        elif name == "series":
            r = CounterReading(series=g[0], fmt=name)
        else:  # pragma: no cover - defensive
            continue

        # Sanity check current<=total to drop OCR noise.
        if r.total is not None and r.slice is not None and r.slice > r.total:
            continue
        if r.phase_total is not None and r.phase is not None and r.phase > r.phase_total:
            continue
        return r

    return CounterReading()
