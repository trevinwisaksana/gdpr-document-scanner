// ── Backend (Google Cloud Run) client ──────────────────────────────────────────
// The deployed image is currently stale and only exposes /healthz +
// /workflows/drive/scan (see memory: deployed-backend-gap). These typed helpers
// match the *intended* contract in app/main.py, so the app auto-upgrades to live
// data the moment those routes deploy. Everything degrades to demo data on error.

import type { Kpis, OwnerStat } from "./types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");
export const DEMO_MODE =
  (process.env.NEXT_PUBLIC_DEMO_MODE ?? "").toLowerCase() === "true" || API_BASE === "";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE) throw new ApiError(0, "API base URL not configured");
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

/** Liveness — note the deployed image uses /healthz (not /health). */
export async function checkHealth(): Promise<boolean> {
  for (const p of ["/healthz", "/health"]) {
    try {
      const res = await fetch(`${API_BASE}${p}`);
      if (res.ok) return true;
    } catch {
      /* try next */
    }
  }
  return false;
}

/** Trigger the live Google Drive scan pipeline (this endpoint IS deployed). */
export async function triggerDriveScan(): Promise<{
  files_queued?: number;
  failed?: number;
  status?: string;
}> {
  return req("/workflows/drive/scan", { method: "POST", body: "{}" });
}

/** Assemble KPIs from the (intended) /kpis/* endpoints. Throws if not live. */
export async function fetchKpis(): Promise<Partial<Kpis>> {
  const [registered, flagged, processed, percent] = await Promise.all([
    req<{ value: number }>("/kpis/total-files-registered"),
    req<{ value: number }>("/kpis/total-files-flagged"),
    req<{ value: number }>("/kpis/total-files-processed"),
    req<{ value: number }>("/kpis/percentage-files-flagged"),
  ]);
  return {
    filesRegistered: registered.value,
    filesFlagged: flagged.value,
    filesProcessed: processed.value,
    filesNotFlagged: Math.max(0, processed.value - flagged.value),
    percentFlagged: percent.value,
  };
}

export async function fetchFlaggedPerOwner(): Promise<OwnerStat[]> {
  const data = await req<{ items: { owner: string; flagged_files: number }[] }>(
    "/kpis/flagged-files-per-owner"
  );
  return data.items.map((i) => ({ owner: i.owner, flaggedFiles: i.flagged_files }));
}

export type FindingAction = "confirm_delete" | "keep" | "false_positive";

/** Persist a finding decision (intended PATCH /findings/{id}/status). */
export async function updateFindingStatus(
  findingId: string,
  action: FindingAction
): Promise<void> {
  await req(`/findings/${encodeURIComponent(findingId)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ action }),
  });
}

export { ApiError };
