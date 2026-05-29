import { useEffect, useRef, useState } from "react";
import type { ROISpec } from "../api";

interface Props {
  imageUrl: string;
  suggested: ROISpec | null;
  onConfirm: (roi: ROISpec) => void;
}

// Lets the user confirm the auto-detected image region or drag a new rectangle.
export function CropEditor({ imageUrl, suggested, onConfirm }: Props) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [natural, setNatural] = useState({ w: 0, h: 0 });
  const [rect, setRect] = useState<ROISpec | null>(suggested);
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => setRect(suggested), [suggested]);

  // Map a mouse event to natural-image pixel coordinates.
  const toImageCoords = (e: React.MouseEvent) => {
    const img = imgRef.current!;
    const r = img.getBoundingClientRect();
    const sx = natural.w / r.width;
    const sy = natural.h / r.height;
    return {
      x: Math.round((e.clientX - r.left) * sx),
      y: Math.round((e.clientY - r.top) * sy),
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

  // Convert natural-pixel rect to on-screen overlay style.
  const overlayStyle = (): React.CSSProperties => {
    const img = imgRef.current;
    if (!img || !rect || !natural.w) return { display: "none" };
    const r = img.getBoundingClientRect();
    const sx = r.width / natural.w;
    const sy = r.height / natural.h;
    return {
      left: rect.x * sx,
      top: rect.y * sy,
      width: rect.width * sx,
      height: rect.height * sy,
    };
  };

  return (
    <div className="card">
      <h2>2. Confirm the image region</h2>
      <p className="muted">
        We auto-detected the image area (green box). Drag a new rectangle if it is wrong —
        exclude toolbars and the patient banner.
      </p>
      <div className="crop-wrap" onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp}>
        <img
          ref={imgRef}
          src={imageUrl}
          alt="first frame"
          draggable={false}
          onLoad={(e) =>
            setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })
          }
        />
        <div className="crop-overlay" style={overlayStyle()} />
      </div>
      <button disabled={!rect || rect.width < 4} onClick={() => rect && onConfirm(rect)}>
        Confirm crop & reconstruct
      </button>
    </div>
  );
}
