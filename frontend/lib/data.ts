// ── Pure selectors over the demo dataset ───────────────────────────────────────
// Synchronous, deterministic reads. Pages layer client-side decisions
// (lib/decisions) and live API data (lib/api) on top of these.

import { DEMO_FILES, DEMO_SCAN_RUNS, DEMO_USERS } from "./demo";
import { categoryPriority, maxPriority, PRIORITY_ORDER } from "./gdpr";
import type { Kpis, PiiCategory, Priority, ScannedFile, User } from "./types";

export function getUsers(): User[] {
  return DEMO_USERS;
}
export function getEmployees(): User[] {
  return DEMO_USERS.filter((u) => u.role === "employee");
}
export function getUserById(id: string): User | undefined {
  return DEMO_USERS.find((u) => u.id === id);
}

export function getAllFiles(): ScannedFile[] {
  return DEMO_FILES;
}
export function getFileById(id: string): ScannedFile | undefined {
  return DEMO_FILES.find((f) => f.id === id);
}

/** A file is "flagged" when it has at least one finding. */
export function isFlagged(f: ScannedFile): boolean {
  return f.findings.length > 0;
}
export function getFlaggedFiles(): ScannedFile[] {
  return DEMO_FILES.filter(isFlagged);
}

/** Files a user is responsible for (direct owner OR master of data) that are flagged. */
export function getFlaggedFilesForUser(userId: string): ScannedFile[] {
  return DEMO_FILES.filter(
    (f) => isFlagged(f) && (f.ownerUserId === userId || f.masterUserId === userId)
  );
}

/** All files a user is responsible for (flagged or not). */
export function getFilesForUser(userId: string): ScannedFile[] {
  return DEMO_FILES.filter((f) => f.ownerUserId === userId || f.masterUserId === userId);
}

export function fileCategories(f: ScannedFile): PiiCategory[] {
  return Array.from(new Set(f.findings.map((x) => x.category)));
}

export function filePriority(f: ScannedFile): Priority {
  return maxPriority(f.findings.map((x) => x.category));
}

/** Sort flagged files by risk (high → low), then by finding count desc. */
export function sortByRisk(files: ScannedFile[]): ScannedFile[] {
  return [...files].sort((a, b) => {
    const pa = PRIORITY_ORDER[filePriority(a)];
    const pb = PRIORITY_ORDER[filePriority(b)];
    if (pa !== pb) return pa - pb;
    return b.findings.length - a.findings.length;
  });
}

/** KPIs computed from the demo corpus (the baseline before live data). */
export function computeKpis(files: ScannedFile[] = DEMO_FILES): Kpis {
  const flagged = files.filter(isFlagged);
  const filesProcessed = files.length;
  const filesFlagged = flagged.length;
  return {
    filesRegistered: files.length,
    filesProcessed,
    filesFlagged,
    filesNotFlagged: filesProcessed - filesFlagged,
    percentFlagged: filesProcessed ? (filesFlagged / filesProcessed) * 100 : 0,
    totalFindings: files.reduce((a, f) => a + f.findings.length, 0),
    bytesScanned: files.reduce((a, f) => a + f.sizeBytes, 0),
  };
}

export interface CategoryCount {
  category: PiiCategory;
  n: number;
  priority: Priority;
}
export function categoryBreakdown(files: ScannedFile[] = DEMO_FILES): CategoryCount[] {
  const counts = new Map<PiiCategory, number>();
  for (const f of files) {
    for (const fd of f.findings) counts.set(fd.category, (counts.get(fd.category) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([category, n]) => ({ category, n, priority: categoryPriority(category) }))
    .sort((a, b) => b.n - a.n);
}

export interface SourceCount {
  sourceType: string;
  nFiles: number;
  nFindings: number;
  bytes: number;
}
export function sourceBreakdown(files: ScannedFile[] = DEMO_FILES): SourceCount[] {
  const map = new Map<string, SourceCount>();
  for (const f of files) {
    const cur =
      map.get(f.sourceType) ?? { sourceType: f.sourceType, nFiles: 0, nFindings: 0, bytes: 0 };
    cur.nFiles += 1;
    cur.nFindings += f.findings.length;
    cur.bytes += f.sizeBytes;
    map.set(f.sourceType, cur);
  }
  return Array.from(map.values()).sort((a, b) => b.nFindings - a.nFindings);
}

export function flaggedPerOwner(): { userId: string; flaggedFiles: number }[] {
  const map = new Map<string, number>();
  for (const f of getFlaggedFiles()) {
    map.set(f.ownerUserId, (map.get(f.ownerUserId) ?? 0) + 1);
  }
  return Array.from(map.entries())
    .map(([userId, flaggedFiles]) => ({ userId, flaggedFiles }))
    .sort((a, b) => b.flaggedFiles - a.flaggedFiles);
}

export function getScanRuns() {
  return DEMO_SCAN_RUNS;
}
export function latestScanRun() {
  return DEMO_SCAN_RUNS[0];
}
