import { useEffect, useRef, useState } from "react";
import { Niivue } from "@niivue/niivue";
import type { VolumeMeta } from "../api";
import { volumeUrl } from "../api";

interface Props {
  jobId: string;
  meta: VolumeMeta;
}

// NiiVue slice-type constants (numeric to avoid enum import churn).
const SLICE = { axial: 0, coronal: 1, sagittal: 2, multiplanar: 3, render: 4 } as const;

// Renders a reconstructed 3D/4D volume with multi-planar reconstruction, a 3D
// render mode, and (for 4D) a time scrubber — all provided by NiiVue.
export function NiiVueViewer({ jobId, meta }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nvRef = useRef<Niivue | null>(null);
  const [view, setView] = useState<keyof typeof SLICE>("multiplanar");
  const [nFrames, setNFrames] = useState(1);
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    if (!canvasRef.current) return;
    const nv = new Niivue({ backColor: [0, 0, 0, 1], show3Dcrosshair: true });
    nvRef.current = nv;
    nv.attachToCanvas(canvasRef.current);
    nv.loadVolumes([{ url: volumeUrl(jobId), colormap: "gray" }]).then(() => {
      nv.setSliceType(SLICE.multiplanar);
      const n = (nv.volumes[0] as { nFrame4D?: number })?.nFrame4D ?? 1;
      setNFrames(n);
    });
    return () => {
      nvRef.current = null;
    };
  }, [jobId]);

  useEffect(() => {
    nvRef.current?.setSliceType(SLICE[view]);
  }, [view]);

  const onFrame = (f: number) => {
    setFrame(f);
    const nv = nvRef.current;
    if (nv && nv.volumes[0]) nv.setFrame4D(nv.volumes[0].id, f);
  };

  const is4D = meta.output_kind === "volume_4d" && nFrames > 1;

  return (
    <div className="viewer">
      <div className="toolbar">
        {(["axial", "coronal", "sagittal", "multiplanar", "render"] as const).map((v) => (
          <button key={v} className={v === view ? "active" : ""} onClick={() => setView(v)}>
            {v}
          </button>
        ))}
      </div>
      <canvas ref={canvasRef} className="nv-canvas" />
      {is4D && (
        <div className="time-scrubber">
          <span>Time {frame + 1}/{nFrames}</span>
          <input
            type="range"
            min={0}
            max={nFrames - 1}
            value={frame}
            onChange={(e) => onFrame(Number(e.target.value))}
          />
        </div>
      )}
    </div>
  );
}
