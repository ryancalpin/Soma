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
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [fps, setFps] = useState(15);

  // Preload all cine frames.
  useEffect(() => {
    const imgs: HTMLImageElement[] = [];
    for (let i = 0; i < nFrames; i++) {
      const im = new Image();
      im.src = cineFrameUrl(jobId, i);
      imgs.push(im);
    }
    imgsRef.current = imgs;
  }, [jobId, nFrames]);

  // Draw the current frame.
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

  // Playback loop.
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setFrame((f) => (f + 1) % nFrames), 1000 / fps);
    return () => clearInterval(id);
  }, [playing, fps, nFrames]);

  return (
    <div className="viewer">
      <p className="warn">{meta.note}</p>
      <canvas ref={canvasRef} className="cine-canvas" />
      <div className="cine-controls">
        <button onClick={() => setPlaying((p) => !p)}>{playing ? "Pause" : "Play"}</button>
        <input
          type="range"
          min={0}
          max={nFrames - 1}
          value={frame}
          onChange={(e) => { setPlaying(false); setFrame(Number(e.target.value)); }}
        />
        <span>{frame + 1}/{nFrames}</span>
        <label className="field-inline">
          fps
          <input type="number" min={1} max={60} value={fps}
            onChange={(e) => setFps(Number(e.target.value))} />
        </label>
      </div>
    </div>
  );
}
