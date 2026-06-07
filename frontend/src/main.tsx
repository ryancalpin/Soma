import React, { useCallback, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import {
  JobStatus, ROISpec, submitRoi, subscribeEvents, uploadRecording,
} from "./api";
import { Uploader } from "./components/Uploader";
import { CropEditor } from "./components/CropEditor";
import { ProgressView } from "./components/ProgressView";
import { NiiVueViewer } from "./components/NiiVueViewer";
import { CinePlayer } from "./components/CinePlayer";
import "./styles.css";

const STEPS = ["Upload", "Crop", "Reconstruct", "View"];

function stepIndex(jobId: string | null, stage?: string): number {
  if (!jobId) return 0;
  if (stage === "await_roi") return 1;
  if (stage === "done") return 3;
  return 2;
}

function App() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const unsubRef = useRef<(() => void) | null>(null);

  useEffect(() => () => unsubRef.current?.(), []);

  const onUpload = useCallback(async (file: File, modality: string) => {
    setBusy(true);
    try {
      const id = await uploadRecording(file, modality);
      setJobId(id);
      unsubRef.current?.();
      unsubRef.current = subscribeEvents(id, setStatus);
    } finally {
      setBusy(false);
    }
  }, []);

  const onConfirmRoi = useCallback(async (roi: ROISpec) => {
    if (jobId) await submitRoi(jobId, roi);
  }, [jobId]);

  const reset = () => {
    unsubRef.current?.();
    setJobId(null);
    setStatus(null);
  };

  const stage = status?.stage;
  const meta = status?.meta ?? null;
  const current = stepIndex(jobId, stage);

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <span className="logo">◑</span>
          <div>
            <h1>Soma</h1>
            <p className="tagline">Screen recording → interactive 3D / 4D viewer</p>
          </div>
        </div>
        {jobId && <button className="ghost small" onClick={reset}>Start over</button>}
      </header>

      <ol className="stepper">
        {STEPS.map((label, i) => (
          <li key={label} className={i === current ? "active" : i < current ? "done" : ""}>
            <span className="dot">{i < current ? "✓" : i + 1}</span>
            {label}
          </li>
        ))}
      </ol>

      {!jobId && <Uploader onUpload={onUpload} busy={busy} />}

      {jobId && stage === "await_roi" && (
        <CropEditor
          jobId={jobId}
          suggested={status?.suggested_roi ?? null}
          onConfirm={onConfirmRoi}
        />
      )}

      {jobId && status && stage !== "done" && stage !== "await_roi" && (
        <ProgressView status={status} />
      )}

      {jobId && stage === "done" && meta && (
        <>
          <ResultSummary status={status!} />
          {meta.output_kind === "cine_2d_time"
            ? <CinePlayer jobId={jobId} meta={meta} />
            : <NiiVueViewer jobId={jobId} meta={meta} />}
        </>
      )}

      <footer className="app-footer">
        Processed locally · not for primary diagnosis
      </footer>
    </div>
  );
}

function ResultSummary({ status }: { status: JobStatus }) {
  const m = status.meta!;
  return (
    <div className="card summary">
      <h2>Reconstruction ready</h2>
      <div className="summary-grid">
        <div><span className="k">Type</span><span className="v">{m.output_kind.replace(/_/g, " ")}</span></div>
        <div><span className="k">Modality</span><span className="v">{m.modality}</span></div>
        <div><span className="k">Shape</span><span className="v">{m.shape.join(" × ")}</span></div>
        <div>
          <span className="k">OCR</span>
          <span className="v">
            {m.ocr.counter_found
              ? `${m.ocr.frames_confident}/${m.ocr.frames_total} (${m.ocr.detected_format})`
              : "content-based"}
          </span>
        </div>
        {m.completeness.expected_slices > 0 && (
          <div>
            <span className="k">Slices</span>
            <span className="v">
              {m.completeness.present_slices}/{m.completeness.expected_slices}
              {m.completeness.missing_slices.length > 0 &&
                ` (${m.completeness.missing_slices.length} interp.)`}
              {m.completeness.timepoints > 1 && ` · ${m.completeness.timepoints} timepts`}
            </span>
          </div>
        )}
      </div>
      <p className="warn">{m.note}</p>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
