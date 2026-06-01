// ── Backend (Google Cloud Run) client ──────────────────────────────────────────
// Typed helpers for the endpoints actually exposed by app/main.py (verified live
// against the deployed image). The deployment is current — these all work:
//
//   GET  /health
//   POST /scan/text
//   GET  /kpis/total-files-registered | total-files-flagged
//   GET  /kpis/total-files-processed  | percentage-files-flagged
//   GET  /kpis/owners                 | flagged-files-per-owner
//   POST /workflows/drive/scan
//
// Two routes exist in the contract but are backed by an unprovisioned SQLite
// store on Cloud Run and currently 500, so the UI does NOT depend on them:
//   GET   /users/{id}/files          (per-user flagged files)
//   PATCH /findings/{id}/status      (finding decision)
// updateFindingStatus() below is kept as a best-effort no-op-on-failure call.

import type {
  Detector,
  Finding,
  Kpis,
  OwnerStat,
  PiiCategory,
  ScannedFile,
  SourceType,
} from "./types";

// Default to the deployed backend so the admin dashboard is live out of the box.
// Override with NEXT_PUBLIC_API_BASE_URL; set it to "" (or DEMO_MODE=true) to
// force the bundled demo dataset everywhere.
const DEFAULT_API_BASE = "https://dashboard-http-95861934207.us-central1.run.app";
const RAW_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;

export const API_BASE = (RAW_BASE === undefined ? DEFAULT_API_BASE : RAW_BASE).replace(/\/$/, "");
export const DEMO_MODE =
  (process.env.NEXT_PUBLIC_DEMO_MODE ?? "").toLowerCase() === "true" || API_BASE === "";

/** True when we should attempt live calls (a base URL is set and demo isn't forced). */
export const LIVE = Boolean(API_BASE) && !DEMO_MODE;

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE) throw new ApiError(0, "API base URL not configured");
  // Only attach a JSON content-type on requests that carry a body — keeps GETs
  // as CORS "simple" requests where possible.
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string>) };
  if (init?.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

/** Liveness probe. The deployed image exposes /health (there is no /healthz). */
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

// ── KPIs (Postgres drive_files) ────────────────────────────────────────────────

interface KpiValue {
  value: number;
}

/** Live drive-scan KPIs. Only the fields the backend can serve are populated. */
export type LiveKpis = Pick<
  Kpis,
  "filesRegistered" | "filesFlagged" | "filesProcessed" | "filesNotFlagged" | "percentFlagged"
>;

export async function fetchKpis(): Promise<LiveKpis> {
  const [registered, flagged, processed, percent] = await Promise.all([
    req<KpiValue>("/kpis/total-files-registered"),
    req<KpiValue>("/kpis/total-files-flagged"),
    req<KpiValue>("/kpis/total-files-processed"),
    req<KpiValue>("/kpis/percentage-files-flagged"),
  ]);
  return {
    filesRegistered: registered.value,
    filesFlagged: flagged.value,
    filesProcessed: processed.value,
    filesNotFlagged: Math.max(0, processed.value - flagged.value),
    percentFlagged: percent.value,
  };
}

/** Distinct data owners recorded in Drive (Google account emails). */
export async function fetchOwners(): Promise<string[]> {
  const data = await req<{ owners: string[] }>("/kpis/owners");
  return data.owners ?? [];
}

export async function fetchFlaggedPerOwner(): Promise<OwnerStat[]> {
  const data = await req<{ items: { owner: string; flagged_files: number }[] }>(
    "/kpis/flagged-files-per-owner"
  );
  return (data.items ?? []).map((i) => ({ owner: i.owner, flaggedFiles: i.flagged_files }));
}

// ── Live PII text scan (/scan/text) ─────────────────────────────────────────────

/** Detector toggles mirrored from app/main.py RegexConfigPayload. */
export interface ScanConfig {
  emails: boolean;
  phones: boolean;
  usernames: boolean;
  signatures: boolean;
  id_documents: boolean;
  ip_addresses: boolean;
  credit_cards: boolean;
  iban: boolean;
  ssn: boolean;
  dob: boolean;
}

export interface ScanFinding {
  category: string;
  snippet: string;
  /** "regex" | "ner" | "llm" — which detection tier produced the hit. */
  source: string;
  /** Present for regex hits. */
  pattern?: string;
  /** Present when NER/LLM contributes a score. */
  confidence?: number;
}

export interface ScanTextResult {
  file_path: string;
  findings: ScanFinding[];
  has_pii: boolean;
}

export async function scanText(text: string, config?: Partial<ScanConfig>): Promise<ScanTextResult> {
  return req<ScanTextResult>("/scan/text", {
    method: "POST",
    body: JSON.stringify(config ? { text, config } : { text }),
  });
}

// ── Workflows ───────────────────────────────────────────────────────────────────

/** Trigger the live Google Drive scan pipeline (real, fire-and-forget). */
export async function triggerDriveScan(): Promise<{
  files_queued?: number;
  failed?: number;
  status?: string;
}> {
  return req("/workflows/drive/scan", { method: "POST", body: "{}" });
}

// ── Findings (best-effort — SQLite store not provisioned in prod) ────────────────

export type FindingAction = "confirm_delete" | "keep" | "false_positive";

/** Persist a file-level decision via PATCH /files/{file_id}/status. */
export async function updateFileStatus(
  fileId: string,
  action: FindingAction
): Promise<void> {
  await req(`/files/${encodeURIComponent(fileId)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ action }),
  });
}

export interface ApiFlaggedFile {
  id: string;
  path: string;
  source_type: string;
  size_bytes: number;
  last_modified: number;
  last_scanned_at: number | null;
  n_findings: number;
  finding_categories: string[];
}

export async function fetchFlaggedFilesForUser(userId: string): Promise<ApiFlaggedFile[]> {
  const data = await req<{ user_id: string; total: number; files: ApiFlaggedFile[] }>(
    `/users/${encodeURIComponent(userId)}/files`
  );
  return data.files;
}

export function adaptApiFile(f: ApiFlaggedFile, userId: string): ScannedFile {
  const name = f.path.split("/").pop() ?? f.path;
  const findings: Finding[] = f.finding_categories.map((cat, i) => ({
    id: `${f.id}__${i}`,
    fileId: f.id,
    category: cat as PiiCategory,
    snippet: "",
    confidence: 1,
    detector: "regex" as Detector,
    gdprArticles: [],
  }));
  return {
    id: f.id,
    name,
    path: f.path,
    sourceType: f.source_type as SourceType,
    mimeType: "",
    sizeBytes: f.size_bytes,
    lastModified: f.last_modified,
    lastScannedAt: f.last_scanned_at ?? 0,
    ownerUserId: userId,
    masterUserId: null,
    text: "",
    findings,
  };
}

export { ApiError };
