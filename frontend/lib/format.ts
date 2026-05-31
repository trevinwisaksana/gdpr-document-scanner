import clsx, { type ClassValue } from "clsx";

/** Tailwind-friendly className combiner. */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}

/** Human-readable byte size, e.g. 4.2 MB. Mirrors shell.human_bytes. */
export function humanBytes(n: number): string {
  let f = Math.max(0, n);
  const units = ["B", "KB", "MB", "GB", "TB"];
  for (const unit of units) {
    if (f < 1024 || unit === "TB") {
      return unit === "B" ? `${Math.round(f)} B` : `${f.toFixed(1)} ${unit}`;
    }
    f /= 1024;
  }
  return `${f.toFixed(1)} TB`;
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** e.g. "12 Mar 2024" */
export function formatDate(ms: number): string {
  const d = new Date(ms);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

/** e.g. "12 Mar 2024, 14:30" */
export function formatDateTime(ms: number): string {
  const d = new Date(ms);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${formatDate(ms)}, ${hh}:${mm}`;
}

/** Coarse relative time, e.g. "3 years ago", "5 days ago". */
export function relativeTime(ms: number, now: number = Date.now()): string {
  const diff = now - ms;
  const day = 86_400_000;
  const year = 365.25 * day;
  if (diff >= year) {
    const y = Math.floor(diff / year);
    return `${y} year${y === 1 ? "" : "s"} ago`;
  }
  if (diff >= 30 * day) {
    const mo = Math.floor(diff / (30 * day));
    return `${mo} month${mo === 1 ? "" : "s"} ago`;
  }
  if (diff >= day) {
    const d = Math.floor(diff / day);
    return `${d} day${d === 1 ? "" : "s"} ago`;
  }
  return "today";
}

export const RETENTION_YEARS = 3;

/** True if the file is older than the retention window (default 3 years). */
export function isPastRetention(
  lastModified: number,
  retentionYears: number = RETENTION_YEARS,
  now: number = Date.now()
): boolean {
  return now - lastModified > retentionYears * 365.25 * 86_400_000;
}

export function pct(value: number, total: number): number {
  return total > 0 ? (value / total) * 100 : 0;
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** Deterministic avatar color from a name. Mirrors shell.avatar_color. */
const AVATAR_COLORS = [
  "#4f5bd5", "#d62976", "#962fbf", "#23a566", "#e07b39",
  "#2b7be9", "#6b4fbb", "#c1392b", "#2e86ab", "#b5451b",
];
export function avatarColor(name: string): string {
  const sum = [...name].reduce((a, c) => a + c.charCodeAt(0), 0);
  return AVATAR_COLORS[sum % AVATAR_COLORS.length];
}
export function avatarInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return parts.length >= 2
    ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    : name.slice(0, 2).toUpperCase();
}

export const SOURCE_LABEL: Record<string, string> = {
  onedrive: "OneDrive",
  sharepoint: "SharePoint",
  fileshare: "File share",
  gdrive: "Google Drive",
};
