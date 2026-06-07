# Soma

Turn **screen recordings** of medical imaging studies (CT, MRI, echo, heart cath) into
**interactive 3D / 4D viewers** you can scroll through — re-slice anatomy in any plane and,
for 4D data, scrub through time.

Everything runs **locally and offline**. The server binds to `127.0.0.1` only, so patient
data never leaves your machine.

> ⚠️ **Not for primary diagnosis.** Reconstructions come from lossy screen recordings with
> no DICOM metadata, so image fidelity is approximate and spatial measurements are not
> metrically accurate. Single-viewpoint modalities (echo, cath) become a 2D + time cine
> loop — they cannot be turned into a rotatable 3D volume from one recording.

## How it works

1. **Upload** a screen recording (MP4/MOV/WebM) of you scrolling through a study in your
   PACS/viewer.
2. The app **extracts frames**, **auto-detects the image region** (you can correct the crop),
   and **reads the on-screen slice counters with OCR** (e.g. `Im: 45/120`) to recover the
   slice/timepoint structure — no DICOM metadata required.
3. Frames are **stacked into a volume** and written as **NIfTI**.
4. **CT/MRI** open in a multi-planar viewer (axial/coronal/sagittal + 3D render, plus a time
   scrubber for 4D). **Echo/cath** open in a 2D + time cine player.

## Architecture

| Layer | Stack |
|---|---|
| Backend | FastAPI + Uvicorn, `imageio-ffmpeg` (frame extraction), OpenCV/NumPy (ROI + assembly), **RapidOCR** (ONNX slice-counter reading, models bundled — fully offline), **nibabel** (NIfTI), SSE progress |
| Frontend | Vite + React + TypeScript, **NiiVue** (MPR/3D/4D viewer), canvas cine player |

```
soma/processing/  frames · roi · ocr · counters · ordering · volume · nifti_writer
soma/jobs/        registry · pipeline (orchestrator)
soma/api/         upload · jobs (status/SSE) · assets
frontend/src/     Uploader · CropEditor · ProgressView · NiiVueViewer · CinePlayer
```

## Run it portably (no install — USB stick)

For a locked-down work computer where you can't install Python/Node, use a **portable
bundle**: a folder containing a self-contained Python, all dependencies, the app, and a
double-click launcher. Copy it to a USB stick and run it — no admin rights, fully offline.

1. **Get a bundle** for your OS:
   - Download the `Soma-windows-x64.zip` / `Soma-macos-arm64.tar.gz` / `Soma-macos-x64.tar.gz`
     artifact from the **Build portable bundles** GitHub Action (or a tagged Release).
   - Or build one yourself on a machine you *can* install on:
     ```bash
     cd frontend && npm ci && npm run build && cd ..
     python build/make_portable.py --target macos-arm64   # or windows-x64, macos-x64
     ```
2. **Unzip onto the USB stick.**
3. **Run:**
   - Windows: double-click `Soma.bat`
   - macOS: double-click `Soma.command` (first time: right-click → Open to clear Gatekeeper)

   A console window opens and your browser launches at `http://127.0.0.1:8000`. Recordings
   and reconstructions are stored in the `data/` folder next to the launcher (on the stick),
   so deleting that folder wipes all patient data.

The Windows and macOS bundles are produced automatically by
`.github/workflows/build-portable.yml` (manually via *Run workflow*, or on a `v*` tag).

## Install & run (developers)

```bash
# Backend (Python 3.10+)
pip install -e .

# Frontend (Node 18+) — builds into soma/static/
cd frontend && npm install && npm run build && cd ..

# Launch (opens the browser at http://127.0.0.1:8000)
python run.py
```

OCR runs fully offline — RapidOCR's ONNX models ship inside the package, so there is no
first-run download.

### Development

Run the API and the Vite dev server (with proxy) separately:

```bash
uvicorn soma.main:app --reload      # terminal 1
cd frontend && npm run dev          # terminal 2  (http://localhost:5173)
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Covers counter parsing, frame→(slice,timepoint) ordering (incl. 4D reset detection and
non-monotonic scrolling), and ROI detection on synthetic frames.

## Limitations / roadmap

- **OCR reliability** varies by PACS vendor; when no counter is found the app falls back to
  content-based ordering and you can supply a manual slice count.
- **Unknown spacing** — slice thickness/pixel size are assumed; an adjustable Z-aspect is
  exposed in the viewer.
- **Incomplete scrolls** leave gaps; missing slices are interpolated from neighbours and
  flagged, never fabricated.
