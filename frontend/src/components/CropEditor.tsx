import { useEffect, useRef, useState } from "react";
import type { ROISpec } from "../api";
import { framesCount, rawFrameUrl } from "../api";

interface Props {
  jobId: string;
  suggested: ROISpec | null;
  onConfirm: (roi: ROISpec) => void;
}

// Lets the user confirm the auto-detected image region, scrub to a clearer frame,
// and drag a new rectangle. A live cropped preview shows exactly what will be kept.
export function CropEditor({ jobId, suggested, onConfirm }: Props) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [natural, setNatural] = useState({ w: 0, h: 0 });
  const [rect, setRect] = useState<ROISpec | null>(suggested);
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
  const [count, setCount] = useState(1);
  const [frame, setFrame] = useState(0);

  useEffect(() => setRect(suggested), [suggested]);
  useEffect(() => { framesCount(jobId).then(setCount); }, [jobId]);

  const toImageCoords = (e: React.MouseEvent) => {
    const img = imgRef.current!;
    const r = img.getBoundingClientRect();
    const sx = natural.w / r.width;
    const sy = natural.h / r.height;
    return {
      x: Math.max(0, Math.min(natural.w, Math.round((e.clientX - r.left) * sx))),
      y: Math.max(0, Math.min(natural.h, Math.round((e.clientY - r.top) * sy))),
    };
  };

  const onDown = (e: React.MouseEvent) => setDrag(toImageCoords(e));
  const onMove = (e: React.MouseEvent) => {
    if (!drag) return;
    const p = toImageCoords(e);
    setRect({
      x: Math.min(drag.x, p.x),
      y: Math.min(drag.y, p.y),
      width: Math.abs(p.x - drag.x),
      height: Math.abs(p.y - drag.y),
    });
  };
  const onUp = () => setDrag(null);

  const overlayStyle = (): React.CSSProperties => {
    const img = imgRef.current;
    if (!img || !rect || !natural.w) return { display: "none" };
    const r = img.getBoundingClientRect();
    const sx = r.width / natural.w;
    const sy = r.height / natural.h;
    return { left: rect.x * sx, top: rect.y * sy, width: rect.width * sx, height: rect.height * sy };
  };

  // Live preview: position a copy of the frame so only the ROI shows.
  const previewStyle = (): React.CSSProperties => {
    if (!rect || !rect.width || !rect.height) return { display: "none" };
    const boxW = 220;
    const scale = boxW / rect.width;
    return {
      width: rect.width * scale,
      height: rect.height * scale,
      backgroundImage: `url(${rawFrameUrl(jobId, frame)})`,
      backgroundPosition: `-${rect.x * scale}px -${rect.y * scale}px`,
      backgroundSize: `${natural.w * scale}px ${natural.h * scale}px`,
      backgroundRepeat: "no-repeat",
    };
  };

  return (
    <div className="card">
      <h2>Confirm the image region</h2>
      <p className="muted">
        We auto-detected the image area (green box). Drag a new rectangle if it’s wrong —
        exclude toolbars and the patient banner. Scrub frames to pick a clearer one.
      </p>

      <div className="crop-layout">
        <div className="crop-wrap" onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp}
          onMouseLeave={onUp}>
          <img
            ref={imgRef}
            src={rawFrameUrl(jobId, frame)}
            alt="frame"
            draggable={false}
            onLoad={(e) =>
              setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })
            }
          />
          <div className="crop-overlay" style={overlayStyle()} />
        </div>

        <div className="crop-side">
          <span className="picker-label">Live preview</span>
          <div className="crop-preview" style={previewStyle()} />
          {rect && (
            <div className="muted dims">
              {rect.width} × {rect.height} px
            </div>
          )}
          <button className="ghost small" onClick={() => setRect(suggested)}>
            Reset to auto-detected
          </button>
        </div>
      </div>

      {count > 1 && (
        <label className="slider-row">
          <span>Frame</span>
          <input type="range" min={0} max={count - 1} value={frame}
            onChange={(e) => setFrame(Number(e.target.value))} />
          <em>{frame + 1}/{count}</em>
        </label>
      )}

      <button className="primary" disabled={!rect || rect.width < 4}
        onClick={() => rect && onConfirm(rect)}>
        Confirm crop &amp; reconstruct
      </button>
    </div>
  );
}
