import { useEffect, useRef, useState } from "react";
import type { VolumeMeta } from "../api";
import { cineFrameUrl } from "../api";

interface Props {
  jobId: string;
  meta: VolumeMeta;
}

// 2D + time cine player for echo / cath (single viewpoint). Preserves RGB color
// (Doppler / angiography). Pre-loads frames into <img> objects, then plays them.
export function CinePlayer({ jobId, meta }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgsRef = useRef<HTMLImageElement[]>([]);
  const [nFrames] = useState(meta.shape[0]);
  const [loaded, setLoaded] = useState(0);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [fps, setFps] = useState(15);

  // Preload all cine frames; track progress.
  useEffect(() => {
    let done = 0;
    const imgs: HTMLImageElement[] = [];
    for (let i = 0; i < nFrames; i++) {
      const im = new Image();
      im.onload = () => setLoaded(++done);
      im.src = cineFrameUrl(jobId, i);
      imgs.push(im);
    }
    imgsRef.current = imgs;
  }, [jobId, nFrames]);

  useEffect(() => {
    const c = canvasRef.current;
    const im = imgsRef.current[frame];
    if (!c || !im) return;
    const draw = () => {
      c.width = im.naturalWidth || c.width;
      c.height = im.naturalHeight || c.height;
      c.getContext("2d")?.drawImage(im, 0, 0);
    };
    if (im.complete) draw();
    else im.onload = draw;
  }, [frame]);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setFrame((f) => (f + 1) % nFrames), 1000 / fps);
    return () => clearInterval(id);
  }, [playing, fps, nFrames]);

  const ready = loaded >= nFrames;

  return (
    <div className="viewer">
      <div className="viewer-grid cine-grid">
        <div className="canvas-wrap">
          {!ready && (
            <div className="canvas-loading">Loading frames… {loaded}/{nFrames}</div>
          )}
          <canvas ref={canvasRef} className="cine-canvas" />
        </div>
        <aside className="controls">
          <section>
            <h3>Playback</h3>
            <div className="time-row">
              <button className="play" onClick={() => setPlaying((p) => !p)}>
                {playing ? "❚❚" : "▶"}
              </button>
              <input type="range" min={0} max={nFrames - 1} value={frame}
                onChange={(e) => { setPlaying(false); setFrame(Number(e.target.value)); }} />
              <em>{frame + 1}/{nFrames}</em>
            </div>
            <label className="slider-row small">
              <span>Speed</span>
              <input type="range" min={1} max={60} value={fps}
                onChange={(e) => setFps(Number(e.target.value))} />
              <em>{fps} fps</em>
            </label>
            <div className="seg">
              {[8, 15, 24, 30].map((s) => (
                <button key={s} className={s === fps ? "active" : ""} onClick={() => setFps(s)}>
                  {s}
                </button>
              ))}
            </div>
          </section>
          <p className="warn">{meta.note}</p>
        </aside>
      </div>
    </div>
  );
}
