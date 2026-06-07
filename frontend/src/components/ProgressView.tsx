import type { JobStatus } from "../api";

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  probe: "Probing recording",
  extract: "Extracting frames",
  roi: "Detecting image region",
  await_roi: "Awaiting crop confirmation",
  ocr: "Reading slice counters (OCR)",
  order: "Ordering frames",
  assemble: "Assembling volume",
  write: "Writing volume",
  done: "Done",
  error: "Error",
};

export function ProgressView({ status }: { status: JobStatus }) {
  const pct = Math.round(status.progress * 100);
  const errored = status.stage === "error";
  return (
    <div className="card">
      <h2>Reconstructing</h2>
      <div className="progress-bar">
        <div className={`progress-fill${errored ? " error" : ""}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="progress-label">
        <span className="spinner" hidden={errored} />
        {STAGE_LABELS[status.stage] ?? status.stage}
        {status.message && status.message !== STAGE_LABELS[status.stage]
          ? ` — ${status.message}` : ""}
        <span className="pct">{pct}%</span>
      </p>
      {status.error && <p className="error">Error: {status.error}</p>}
    </div>
  );
}
