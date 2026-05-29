// Typed API client for the Soma backend.

export type Stage =
  | "queued" | "probe" | "extract" | "roi" | "await_roi"
  | "ocr" | "order" | "assemble" | "write" | "done" | "error";

export type OutputKind = "volume_3d" | "volume_4d" | "cine_2d_time";

export interface ROISpec { x: number; y: number; width: number; height: number; }

export interface VolumeMeta {
  output_kind: OutputKind;
  modality: string;
  shape: number[];
  is_rgb: boolean;
  z_aspect: number;
  note: string;
  ocr: { frames_total: number; frames_confident: number; counter_found: boolean; detected_format: string | null };
  completeness: { expected_slices: number; present_slices: number; missing_slices: number[]; timepoints: number };
}

export interface JobStatus {
  job_id: string;
  stage: Stage;
  progress: number;
  message: string;
  error: string | null;
  suggested_roi: ROISpec | null;
  meta: VolumeMeta | null;
}

export async function uploadRecording(file: File, modality: string): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  form.append("modality", modality);
  const res = await fetch("/api/jobs", { method: "POST", body: form });
  if (!res.ok) throw new Error(`upload failed: ${res.status}`);
  const data = await res.json();
  return data.job_id;
}

export async function submitRoi(jobId: string, roi: ROISpec): Promise<void> {
  const res = await fetch(`/api/jobs/${jobId}/roi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(roi),
  });
  if (!res.ok) throw new Error(`roi submit failed: ${res.status}`);
}

export function firstFrameUrl(jobId: string): string {
  return `/api/jobs/${jobId}/first-frame`;
}

export function rawFrameUrl(jobId: string, frame: number): string {
  return `/api/jobs/${jobId}/frame/${frame}`;
}

export async function framesCount(jobId: string): Promise<number> {
  const res = await fetch(`/api/jobs/${jobId}/frames-count`);
  if (!res.ok) return 1;
  return (await res.json()).count ?? 1;
}

export function volumeUrl(jobId: string): string {
  return `/api/jobs/${jobId}/volume.nii.gz`;
}

export function cineFrameUrl(jobId: string, frame: number): string {
  return `/api/jobs/${jobId}/cine/${frame}`;
}

// Subscribe to SSE progress; calls onStatus for each update.
export function subscribeEvents(jobId: string, onStatus: (s: JobStatus) => void): () => void {
  const es = new EventSource(`/api/jobs/${jobId}/events`);
  es.addEventListener("status", (e) => {
    onStatus(JSON.parse((e as MessageEvent).data));
  });
  es.onerror = () => es.close();
  return () => es.close();
}
