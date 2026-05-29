import React, { useCallback, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import {
  JobStatus, ROISpec, firstFrameUrl, submitRoi, subscribeEvents, uploadRecording,
} from "./api";
import { Uploader } from "./components/Uploader";
import { CropEditor } from "./components/CropEditor";
import { ProgressView } from "./components/ProgressView";
import { NiiVueViewer } from "./components/NiiVueViewer";
import { CinePlayer } from "./components/CinePlayer";
import "./styles.css";

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

  return (
    <div className="app">
      <header>
        <h1>Soma</h1>
        <p className="tagline">Screen recording → interactive 3D / 4D medical viewer</p>
        {jobId && <button className="link" onClick={reset}>Start over</button>}
      </header>

      {!jobId && <Uploader onUpload={onUpload} busy={busy} />}

      {jobId && stage === "await_roi" && (
        <CropEditor
          imageUrl={firstFrameUrl(jobId)}
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
    </div>
  );
}

function ResultSummary({ status }: { status: JobStatus }) {
  const m = status.meta!;
  return (
    <div className="card summary">
      <h2>Reconstruction ready</h2>
      <ul>
        <li>Type: <b>{m.output_kind.replace(/_/g, " ")}</b> ({m.modality})</li>
        <li>Shape: {m.shape.join(" × ")}</li>
        <li>
          OCR: {m.ocr.counter_found
            ? `${m.ocr.frames_confident}/${m.ocr.frames_total} frames read (${m.ocr.detected_format})`
            : "no counter detected — used content-based ordering"}
        </li>
        {m.completeness.expected_slices > 0 && (
          <li>
            Slices: {m.completeness.present_slices}/{m.completeness.expected_slices} present
            {m.completeness.missing_slices.length > 0 &&
              ` (${m.completeness.missing_slices.length} interpolated)`}
            , {m.completeness.timepoints} timepoint(s)
          </li>
        )}
      </ul>
      <p className="warn">{m.note}</p>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
