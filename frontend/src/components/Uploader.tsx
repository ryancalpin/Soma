import { useState } from "react";

interface Props {
  onUpload: (file: File, modality: string) => void;
  busy: boolean;
}

const MODALITIES = [
  { value: "auto", label: "Auto-detect" },
  { value: "ct_mri", label: "CT / MRI (3D volume)" },
  { value: "cine", label: "Echo / Cath (2D + time)" },
];

export function Uploader({ onUpload, busy }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [modality, setModality] = useState("auto");

  return (
    <div className="card">
      <h2>1. Upload a screen recording</h2>
      <p className="muted">
        Record yourself scrolling through a study in your PACS/viewer (MP4, MOV or WebM).
        Everything is processed locally — nothing leaves this machine.
      </p>
      <input
        type="file"
        accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        disabled={busy}
      />
      <label className="field">
        Modality
        <select value={modality} onChange={(e) => setModality(e.target.value)} disabled={busy}>
          {MODALITIES.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </label>
      <button disabled={!file || busy} onClick={() => file && onUpload(file, modality)}>
        {busy ? "Uploading…" : "Process recording"}
      </button>
    </div>
  );
}
