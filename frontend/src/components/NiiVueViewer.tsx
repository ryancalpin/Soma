import { useEffect, useRef, useState } from "react";
import { Niivue } from "@niivue/niivue";
import type { VolumeMeta } from "../api";
import { volumeUrl } from "../api";

interface Props {
  jobId: string;
  meta: VolumeMeta;
}

const VIEWS = [
  { key: "axial", label: "Axial", type: 0 },
  { key: "coronal", label: "Coronal", type: 1 },
  { key: "sagittal", label: "Sagittal", type: 2 },
  { key: "multiplanar", label: "All planes", type: 3 },
  { key: "render", label: "3D", type: 4 },
] as const;

const COLORMAPS = ["gray", "bone", "hot", "viridis", "plasma", "cool", "inferno"];

// Drag-mode options map to NiiVue DRAG_MODE enum values.
const DRAG_MODES = [
  { key: "contrast", label: "Brightness / contrast", value: 1 },
  { key: "pan", label: "Pan & zoom", value: 3 },
  { key: "measure", label: "Measure", value: 2 },
  { key: "none", label: "Move crosshair", value: 0 },
] as const;

// Renders a reconstructed 3D/4D volume with multi-planar reconstruction, a 3D
// render mode, windowing, colormaps, per-plane slice sliders, and a 4D time scrubber.
export function NiiVueViewer({ jobId, meta }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nvRef = useRef<Niivue | null>(null);

  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<(typeof VIEWS)[number]["key"]>("multiplanar");
  const [colormap, setColormap] = useState("gray");
  const [dragMode, setDragMode] = useState<(typeof DRAG_MODES)[number]["key"]>("contrast");
  const [smooth, setSmooth] = useState(true);

  // Intensity windowing.
  const [range, setRange] = useState({ min: 0, max: 255 });
  const [level, setLevel] = useState(128);
  const [window, setWindow] = useState(255);

  // Slice positions (voxel indices) and dims [nx,ny,nz].
  const [dims, setDims] = useState<[number, number, number]>([1, 1, 1]);
  const [slice, setSlice] = useState<[number, number, number]>([0, 0, 0]);

  // 4D time.
  const [nFrames, setNFrames] = useState(1);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [fps, setFps] = useState(12);

  const is4D = meta.output_kind === "volume_4d";

  // ---- init ----
  useEffect(() => {
    if (!canvasRef.current) return;
    const nv = new Niivue({
      backColor: [0.05, 0.06, 0.09, 1],
      show3Dcrosshair: true,
      isColorbar: false,
      dragMode: 1,
    });
    nvRef.current = nv;
    nv.attachToCanvas(canvasRef.current);
    // Keep slice sliders in sync when the user scrolls / clicks in the canvas.
    nv.onLocationChange = () => syncFromScene();

    nv.loadVolumes([{ url: volumeUrl(jobId), colormap: "gray" }]).then(() => {
      const vol = nv.volumes[0] as any;
      const d = vol.dims as number[]; // [ndim, nx, ny, nz, nt]
      setDims([d[1], d[2], d[3]]);
      const lo = vol.global_min ?? vol.cal_min ?? 0;
      const hi = vol.global_max ?? vol.cal_max ?? 255;
      setRange({ min: lo, max: hi });
      setLevel((lo + hi) / 2);
      setWindow(hi - lo);
      setNFrames(vol.nFrame4D ?? 1);
      nv.setSliceType(3);
      syncFromScene();
      setLoading(false);
    });
    return () => {
      nvRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const syncFromScene = () => {
    const nv = nvRef.current;
    if (!nv || !nv.volumes[0]) return;
    const d = (nv.volumes[0] as any).dims as number[];
    const f = nv.scene.crosshairPos; // fractional [0..1]
    setSlice([
      Math.round(f[0] * (d[1] - 1)),
      Math.round(f[1] * (d[2] - 1)),
      Math.round(f[2] * (d[3] - 1)),
    ]);
  };

  // ---- control effects ----
  useEffect(() => {
    const nv = nvRef.current;
    if (!nv) return;
    nv.setSliceType(VIEWS.find((v) => v.key === view)!.type);
  }, [view]);

  useEffect(() => {
    const nv = nvRef.current;
    if (!nv || !nv.volumes[0]) return;
    nv.setColormap(nv.volumes[0].id, colormap);
  }, [colormap]);

  useEffect(() => {
    const nv = nvRef.current;
    if (!nv) return;
    nv.opts.dragMode = DRAG_MODES.find((d) => d.key === dragMode)!.value as any;
  }, [dragMode]);

  useEffect(() => {
    nvRef.current?.setInterpolation(!smooth);
  }, [smooth]);

  // Apply windowing (level/window -> cal_min/cal_max).
  useEffect(() => {
    const nv = nvRef.current;
    if (!nv || !nv.volumes[0]) return;
    const vol = nv.volumes[0] as any;
    vol.cal_min = level - window / 2;
    vol.cal_max = level + window / 2;
    nv.updateGLVolume();
  }, [level, window]);

  // 4D playback loop.
  useEffect(() => {
    if (!playing || nFrames <= 1) return;
    const id = setInterval(() => {
      setFrame((f) => {
        const nf = (f + 1) % nFrames;
        const nv = nvRef.current;
        if (nv?.volumes[0]) nv.setFrame4D(nv.volumes[0].id, nf);
        return nf;
      });
    }, 1000 / fps);
    return () => clearInterval(id);
  }, [playing, fps, nFrames]);

  const setSliceAxis = (axis: 0 | 1 | 2, idx: number) => {
    const nv = nvRef.current;
    if (!nv || !nv.volumes[0]) return;
    const next: [number, number, number] = [...slice] as any;
    next[axis] = idx;
    setSlice(next);
    const d = (nv.volumes[0] as any).dims as number[];
    nv.scene.crosshairPos = [
      (next[0] + 0.5) / d[1],
      (next[1] + 0.5) / d[2],
      (next[2] + 0.5) / d[3],
    ] as any;
    nv.drawScene();
  };

  const setFrameIdx = (f: number) => {
    setFrame(f);
    const nv = nvRef.current;
    if (nv?.volumes[0]) nv.setFrame4D(nv.volumes[0].id, f);
  };

  const reset = () => {
    const nv = nvRef.current;
    if (!nv) return;
    nv.setScale?.(1);
    setView("multiplanar");
    setLevel((range.min + range.max) / 2);
    setWindow(range.max - range.min);
    setColormap("gray");
  };

  const showSlider = (axis: 0 | 1 | 2) =>
    view === "multiplanar" ||
    (view === "sagittal" && axis === 0) ||
    (view === "coronal" && axis === 1) ||
    (view === "axial" && axis === 2);

  const axisLabels = ["Sagittal (X)", "Coronal (Y)", "Axial (Z)"] as const;

  return (
    <div className="viewer">
      <div className="viewer-grid">
        <div className="canvas-wrap">
          {loading && <div className="canvas-loading">Loading volume…</div>}
          <canvas ref={canvasRef} className="nv-canvas" />
          <div className="canvas-hint">
            Scroll to change slice · right-drag to adjust brightness/contrast
          </div>
        </div>

        <aside className="controls">
          <section>
            <h3>View</h3>
            <div className="seg">
              {VIEWS.map((v) => (
                <button
                  key={v.key}
                  className={v.key === view ? "active" : ""}
                  onClick={() => setView(v.key)}
                >
                  {v.label}
                </button>
              ))}
            </div>
          </section>

          {view !== "render" && (
            <section>
              <h3>Slice</h3>
              {([0, 1, 2] as const).map((axis) =>
                showSlider(axis) ? (
                  <label key={axis} className="slider-row">
                    <span>{axisLabels[axis]}</span>
                    <input
                      type="range"
                      min={0}
                      max={Math.max(0, dims[axis] - 1)}
                      value={slice[axis]}
                      onChange={(e) => setSliceAxis(axis, Number(e.target.value))}
                    />
                    <em>{slice[axis] + 1}/{dims[axis]}</em>
                  </label>
                ) : null
              )}
            </section>
          )}

          {is4D && nFrames > 1 && (
            <section>
              <h3>Time</h3>
              <div className="time-row">
                <button className="play" onClick={() => setPlaying((p) => !p)}>
                  {playing ? "❚❚" : "▶"}
                </button>
                <input
                  type="range"
                  min={0}
                  max={nFrames - 1}
                  value={frame}
                  onChange={(e) => { setPlaying(false); setFrameIdx(Number(e.target.value)); }}
                />
                <em>{frame + 1}/{nFrames}</em>
              </div>
              <label className="slider-row small">
                <span>Speed</span>
                <input type="range" min={1} max={30} value={fps}
                  onChange={(e) => setFps(Number(e.target.value))} />
                <em>{fps} fps</em>
              </label>
            </section>
          )}

          <section>
            <h3>Brightness & contrast</h3>
            <label className="slider-row small">
              <span>Brightness</span>
              <input type="range" min={range.min} max={range.max} step="any"
                value={level} onChange={(e) => setLevel(Number(e.target.value))} />
            </label>
            <label className="slider-row small">
              <span>Contrast</span>
              <input type="range" min={1} max={Math.max(2, range.max - range.min)} step="any"
                value={window} onChange={(e) => setWindow(Number(e.target.value))} />
            </label>
          </section>

          <section>
            <h3>Appearance</h3>
            <label className="field">
              Colormap
              <select value={colormap} onChange={(e) => setColormap(e.target.value)}>
                {COLORMAPS.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
            <label className="field">
              Mouse drag
              <select value={dragMode} onChange={(e) => setDragMode(e.target.value as any)}>
                {DRAG_MODES.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
              </select>
            </label>
            <label className="check">
              <input type="checkbox" checked={smooth}
                onChange={(e) => setSmooth(e.target.checked)} />
              Smooth interpolation
            </label>
          </section>

          <button className="ghost" onClick={reset}>Reset view</button>
        </aside>
      </div>
    </div>
  );
}
