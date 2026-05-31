// ── Core domain types, mirrored from the backend (scanner/store.py, app/main.py) ──

export type Role = "admin" | "employee";

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  department: string;
}

export type PiiCategory =
  | "name"
  | "username"
  | "email"
  | "signature"
  | "photo_video"
  | "phone"
  | "fax"
  | "home_address"
  | "billing_shipping_address"
  | "passport"
  | "id_card"
  | "drivers_license"
  | "travel_history";

export type Priority = "high" | "medium" | "low";

export type Detector = "regex" | "ner" | "llm";

export type SourceType = "onedrive" | "sharepoint" | "fileshare" | "gdrive";

/** Backend finding status (scanner/store.py). The frontend additionally tracks
 *  per-file "decisions" client-side (see Decision). */
export type FindingStatus = "open" | "keep" | "delete" | "false_positive";

export interface Finding {
  id: string;
  fileId: string;
  category: PiiCategory;
  snippet: string;
  confidence: number; // 0..1
  detector: Detector;
  gdprArticles: string[];
}

export interface ScannedFile {
  id: string;
  name: string;
  path: string;
  sourceType: SourceType;
  mimeType: string;
  sizeBytes: number;
  lastModified: number; // epoch ms
  lastScannedAt: number; // epoch ms
  ownerUserId: string;
  masterUserId: string | null;
  /** Extracted text used for preview + Ollama summary input. */
  text: string;
  findings: Finding[];
}

/** A user's review decision for a flagged file. Tracked client-side. */
export type Decision = "pending" | "deleted" | "cancelled" | "extended";

export const DECISION_META: Record<
  Decision,
  { label: string; verb: string; tone: "ink" | "danger" | "ok" | "flag" | "accent" }
> = {
  pending: { label: "Pending review", verb: "Pending", tone: "ink" },
  deleted: { label: "Marked for deletion", verb: "Deleted", tone: "danger" },
  cancelled: { label: "Cancelled — false positive", verb: "Cancelled", tone: "ok" },
  extended: { label: "Retention extended", verb: "Extended", tone: "flag" },
};

// ── Aggregates ────────────────────────────────────────────────────────────────

export interface Kpis {
  filesRegistered: number;
  filesProcessed: number;
  filesFlagged: number;
  filesNotFlagged: number;
  percentFlagged: number;
  totalFindings: number;
  bytesScanned: number;
}

export interface OwnerStat {
  owner: string; // user id
  flaggedFiles: number;
}

/** A point-in-time snapshot of one scan, for the admin history page. */
export interface ScanRun {
  id: string;
  label: string;
  type: "full" | "delta" | "drive";
  startedAt: number; // epoch ms
  finishedAt: number; // epoch ms
  durationSec: number;
  filesScanned: number;
  filesFlagged: number;
  filesNotFlagged: number;
  bytesScanned: number;
  totalFindings: number;
  // decision breakdown captured just before the next scan started
  pending: number;
  deleted: number;
  cancelled: number;
  extended: number;
}

/** Live state of an in-progress scan (drives the admin progress bar). */
export interface ScanProgress {
  running: boolean;
  type: "full" | "delta" | "drive" | null;
  total: number;
  done: number;
  currentFile: string | null;
}
