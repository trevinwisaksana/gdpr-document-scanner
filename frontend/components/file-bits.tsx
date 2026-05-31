"use client";

import {
  FileImage,
  FileSpreadsheet,
  FileText,
  FileType,
  File as FileIcon,
  Cloud,
  FolderTree,
  HardDrive,
  Network,
} from "lucide-react";
import { cn, isPastRetention, SOURCE_LABEL } from "@/lib/format";
import { useSettings } from "@/lib/settings-store";
import type { Decision, SourceType } from "@/lib/types";
import { DECISION_META } from "@/lib/types";

export function FileTypeIcon({ name, className }: { name: string; className?: string }) {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  const cls = cn("h-4 w-4", className);
  if (["xlsx", "xls", "csv"].includes(ext)) return <FileSpreadsheet className={cn(cls, "text-ok-text")} />;
  if (["png", "jpg", "jpeg", "gif"].includes(ext)) return <FileImage className={cn(cls, "text-accent-strong")} />;
  if (ext === "pdf") return <FileType className={cn(cls, "text-danger-text")} />;
  if (["doc", "docx"].includes(ext)) return <FileText className={cn(cls, "text-[#3868c8]")} />;
  if (["txt", "md", "log"].includes(ext)) return <FileText className={cn(cls, "text-ink-faint")} />;
  return <FileIcon className={cls} />;
}

const SOURCE_ICON: Record<SourceType, typeof Cloud> = {
  onedrive: Cloud,
  sharepoint: Network,
  fileshare: HardDrive,
  gdrive: FolderTree,
};

export function SourceBadge({ source }: { source: SourceType }) {
  const Icon = SOURCE_ICON[source];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface-alt px-2 py-0.5 font-mono text-[0.66rem] font-medium text-ink-muted">
      <Icon className="h-3 w-3" />
      {SOURCE_LABEL[source] ?? source}
    </span>
  );
}

export function RetentionBadge({ lastModified }: { lastModified: number }) {
  const { admin } = useSettings();
  if (!isPastRetention(lastModified, admin.retentionYears)) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-flag-line bg-flag-soft px-2 py-0.5 text-[0.66rem] font-semibold text-flag-text">
      ⏰ Past {admin.retentionYears}-yr retention
    </span>
  );
}

const DOT_COLOR: Record<Decision, string> = {
  pending: "#7e92a8",
  deleted: "#dc2626",
  cancelled: "#16a34a",
  extended: "#d97706",
};

export function DecisionDot({ decision, withLabel }: { decision: Decision; withLabel?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[0.7rem] font-medium text-ink-muted">
      <span className="h-2 w-2 flex-none rounded-full" style={{ background: DOT_COLOR[decision] }} />
      {withLabel && DECISION_META[decision].verb}
    </span>
  );
}
