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
  return (
    <div className="card">
      <h2>Processing</h2>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${Math.round(status.progress * 100)}%` }} />
      </div>
      <p className="muted">
        {STAGE_LABELS[status.stage] ?? status.stage}
        {status.message ? ` — ${status.message}` : ""}
      </p>
      {status.error && <p className="error">Error: {status.error}</p>}
    </div>
  );
}
