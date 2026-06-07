import { useEffect, useRef, useState } from "react";

interface Props {
  onUpload: (file: File, modality: string) => void;
  busy: boolean;
}

const MODALITIES = [
  { value: "auto", label: "Auto-detect", hint: "Let Soma decide from the recording" },
  { value: "ct_mri", label: "CT / MRI", hint: "Scroll-through → 3D volume" },
  { value: "cine", label: "Echo / Cath", hint: "Single view → 2D + time loop" },
];

const ACCEPT = ["video/mp4", "video/quicktime", "video/webm"];

function prettySize(bytes: number) {
  const mb = bytes / 1024 / 1024;
  return mb > 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(1)} MB`;
}

export function Uploader({ onUpload, busy }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [modality, setModality] = useState("auto");
  const [dragOver, setDragOver] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) return setPreviewUrl(null);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const accept = (f: File | undefined | null) => {
    if (!f) return;
    const ok = ACCEPT.includes(f.type) || /\.(mp4|mov|webm)$/i.test(f.name);
    if (!ok) {
      setError("Please choose an MP4, MOV or WebM screen recording.");
      return;
    }
    setError(null);
    setFile(f);
  };

  return (
    <div className="card">
      <h2>Upload a screen recording</h2>
      <p className="muted">
        Record yourself scrolling through a study in your PACS/viewer, then drop the
        clip here. Everything is processed locally — nothing leaves this machine.
      </p>

      {!file ? (
        <div
          className={`dropzone${dragOver ? " over" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            accept(e.dataTransfer.files?.[0]);
          }}
        >
          <div className="dz-icon">⤓</div>
          <p><b>Drag &amp; drop</b> your recording here</p>
          <p className="muted">or click to browse · MP4, MOV, WebM</p>
          <input
            ref={inputRef}
            type="file"
            hidden
            accept={ACCEPT.join(",") + ",.mp4,.mov,.webm"}
            onChange={(e) => accept(e.target.files?.[0])}
          />
        </div>
      ) : (
        <div className="file-preview">
          {previewUrl && <video src={previewUrl} controls className="preview-video" />}
          <div className="file-meta">
            <div className="file-name" title={file.name}>{file.name}</div>
            <div className="muted">{prettySize(file.size)}</div>
            <button className="ghost small" onClick={() => setFile(null)} disabled={busy}>
              Choose a different file
            </button>
          </div>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      <div className="modality-picker">
        <span className="picker-label">Modality</span>
        <div className="seg">
          {MODALITIES.map((m) => (
            <button
              key={m.value}
              className={m.value === modality ? "active" : ""}
              onClick={() => setModality(m.value)}
              disabled={busy}
              title={m.hint}
            >
              {m.label}
            </button>
          ))}
        </div>
        <span className="muted picker-hint">
          {MODALITIES.find((m) => m.value === modality)!.hint}
        </span>
      </div>

      <button
        className="primary"
        disabled={!file || busy}
        onClick={() => file && onUpload(file, modality)}
      >
        {busy ? "Uploading…" : "Process recording"}
      </button>
    </div>
  );
}
