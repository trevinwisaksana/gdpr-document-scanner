"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Search, Trash2, ShieldCheck, Clock, RotateCcw, X } from "lucide-react";
import { useSession } from "@/lib/session";
import { useDecisions } from "@/lib/decisions";
import { useSettings } from "@/lib/settings-store";
import {
  getFlaggedFilesForUser,
  sortByRisk,
  fileCategories,
  filePriority,
} from "@/lib/data";
import { categoryColor, categoryLabel } from "@/lib/gdpr";
import { cn, formatDate } from "@/lib/format";
import type { ScannedFile } from "@/lib/types";
import {
  Button,
  PriorityPill,
  DecisionBadge,
  EmptyState,
  useToast,
} from "@/components/ui";
import { PageHeader, DataSourceBadge } from "@/components/PageHeader";
import {
  FileTypeIcon,
  SourceBadge,
  RetentionBadge,
  DecisionDot,
} from "@/components/file-bits";
import { ProgressBar } from "@/components/charts";

type SortKey = "risk" | "recent" | "findings";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "risk", label: "Risk" },
  { value: "recent", label: "Recent" },
  { value: "findings", label: "Findings" },
];

export default function FilesPage() {
  const { viewedUser } = useSession();
  const { user: settings, setUser } = useSettings();
  const { decisionFor, bulkSet, setDecision, counts } = useDecisions();
  const { toast } = useToast();

  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Base set of flagged files for this user (recomputed when the viewer switches).
  const baseFiles = useMemo<ScannedFile[]>(
    () => (viewedUser ? getFlaggedFilesForUser(viewedUser.id) : []),
    [viewedUser]
  );

  // Apply hide-low-risk → sort → name search.
  const files = useMemo<ScannedFile[]>(() => {
    let list = baseFiles;
    if (settings.hideLowRisk) list = list.filter((f) => filePriority(f) !== "low");

    if (settings.defaultSort === "risk") list = sortByRisk(list);
    else if (settings.defaultSort === "recent")
      list = [...list].sort((a, b) => b.lastModified - a.lastModified);
    else list = [...list].sort((a, b) => b.findings.length - a.findings.length);

    const q = query.trim().toLowerCase();
    if (q) list = list.filter((f) => f.name.toLowerCase().includes(q));
    return list;
  }, [baseFiles, settings.hideLowRisk, settings.defaultSort, query]);

  if (!viewedUser) return null;

  const fileIds = files.map((f) => f.id);
  const c = counts(fileIds);
  const reviewedPct = c.total > 0 ? ((c.decided + c.extended) / c.total) * 100 : 0;

  const visibleSelected = files.filter((f) => selected.has(f.id));
  const allVisibleSelected = files.length > 0 && visibleSelected.length === files.length;

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected(allVisibleSelected ? new Set() : new Set(files.map((f) => f.id)));
  }

  function clearSelection() {
    setSelected(new Set());
  }

  function applyBulk(decision: "deleted" | "cancelled" | "extended") {
    const ids = visibleSelected.map((f) => f.id);
    if (ids.length === 0) return;
    bulkSet(ids, decision);
    const n = ids.length;
    const plural = n === 1 ? "file" : "files";
    if (decision === "deleted") toast(`Marked ${n} ${plural} for deletion`, "danger");
    else if (decision === "cancelled") toast(`Dismissed ${n} ${plural} as false positives`, "success");
    else toast(`Extended retention on ${n} ${plural}`, "flag");
    clearSelection();
  }

  const selectedCount = visibleSelected.length;

  return (
    <div className="animate-fadeIn pb-24">
      <PageHeader
        title="My files"
        subtitle="These files were automatically flagged for personal data across your connected sources. Nothing is deleted until you decide — review each item and choose what happens to it."
        right={<DataSourceBadge status="demo" />}
      />

      {/* Summary strip */}
      <div className="card card-pad mb-5">
        <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-4">
          <div className="flex flex-wrap items-center gap-x-7 gap-y-3">
            <SummaryStat label="Flagged" value={c.total} />
            <div className="hidden h-8 w-px bg-line-soft sm:block" />
            <SummaryStat label="Pending" value={c.pending} decision="pending" />
            <SummaryStat label="To delete" value={c.deleted} decision="deleted" />
            <SummaryStat label="Cancelled" value={c.cancelled} decision="cancelled" />
            <SummaryStat label="Extended" value={c.extended} decision="extended" />
          </div>
          <div className="min-w-[200px] flex-1">
            <div className="mb-1.5 flex items-center justify-between text-[0.74rem]">
              <span className="section-label">Review progress</span>
              <span className="font-mono font-semibold text-ink">
                {Math.round(reviewedPct)}% reviewed
              </span>
            </div>
            <ProgressBar value={reviewedPct} tone="ok" />
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-[9px] border border-line bg-surface-alt p-0.5">
          {SORT_OPTIONS.map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => setUser({ defaultSort: o.value })}
              className={cn(
                "rounded-[7px] px-3 py-1.5 text-[0.78rem] font-medium transition-colors",
                settings.defaultSort === o.value
                  ? "bg-surface text-ink shadow-sm"
                  : "text-ink-muted hover:text-ink"
              )}
            >
              {o.label}
            </button>
          ))}
        </div>

        <div className="relative min-w-[200px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
          <input
            className="input pl-9"
            type="text"
            placeholder="Search files by name…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Clear search"
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {files.length > 0 && (
          <label className="flex cursor-pointer select-none items-center gap-2 whitespace-nowrap rounded-lg border border-line bg-surface px-3 py-2 text-[0.78rem] font-medium text-ink-muted hover:text-ink">
            <input
              type="checkbox"
              className="h-4 w-4 cursor-pointer accent-accent"
              checked={allVisibleSelected}
              ref={(el) => {
                if (el) el.indeterminate = selectedCount > 0 && !allVisibleSelected;
              }}
              onChange={toggleAll}
            />
            {allVisibleSelected ? "Select none" : "Select all"}
          </label>
        )}
      </div>

      {/* List */}
      {files.length === 0 ? (
        <EmptyState
          icon={<CheckCircle2 className="h-9 w-9 text-ok-text" />}
          title={query ? "No matching files" : "No flagged files"}
          hint={
            query
              ? "No files match your search. Try a different name."
              : `${viewedUser.name} has no flagged files to review — nothing requires action right now.`
          }
        />
      ) : (
        <div className="card overflow-hidden">
          {files.map((file, i) => {
            const decision = decisionFor(file.id);
            const dimmed = decision === "deleted" || decision === "cancelled";
            const cats = fileCategories(file);
            const isSelected = selected.has(file.id);
            const pri = filePriority(file);
            const highlightHigh = settings.autoExpandHighRisk && pri === "high";
            return (
              <div
                key={file.id}
                className={cn(
                  "group flex items-center gap-3 px-4 transition-colors",
                  settings.density === "compact" ? "py-2" : "py-3.5",
                  i > 0 && "border-t border-line-soft",
                  isSelected ? "bg-accent-soft/50" : "hover:bg-surface-alt",
                  highlightHigh && "border-l-2 border-l-danger",
                  dimmed && "opacity-55"
                )}
              >
                <input
                  type="checkbox"
                  className="h-4 w-4 flex-none cursor-pointer accent-accent"
                  checked={isSelected}
                  onChange={() => toggleOne(file.id)}
                  aria-label={`Select ${file.name}`}
                />

                <FileTypeIcon name={file.name} className="flex-none" />

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/files/${file.id}`}
                      className="truncate text-[0.88rem] font-medium text-ink hover:text-accent-strong hover:underline"
                      title={file.name}
                    >
                      {file.name}
                    </Link>
                    <DecisionBadge decision={decision} />
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5">
                    <SourceBadge source={file.sourceType} />
                    <RetentionBadge lastModified={file.lastModified} />
                    {cats.map((cat) => (
                      <span
                        key={cat}
                        className="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[0.66rem] font-medium"
                        style={{
                          color: categoryColor(cat),
                          borderColor: `${categoryColor(cat)}33`,
                          background: `${categoryColor(cat)}12`,
                        }}
                      >
                        {categoryLabel(cat)}
                      </span>
                    ))}
                    <span className="text-[0.7rem] text-ink-faint">
                      · modified {formatDate(file.lastModified)}
                    </span>
                  </div>
                </div>

                <div className="hidden flex-none text-right md:block">
                  <span className="font-mono text-[0.8rem] font-semibold text-ink">
                    {file.findings.length}
                  </span>
                  <span className="ml-1 text-[0.72rem] text-ink-faint">
                    {file.findings.length === 1 ? "finding" : "findings"}
                  </span>
                </div>

                <div className="flex-none">
                  <PriorityPill priority={pri} />
                </div>

                {dimmed && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setDecision(file.id, "pending")}
                    className="flex-none gap-1.5"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    Reopen
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Sticky bulk action bar */}
      {selectedCount > 0 && (
        <div className="pointer-events-none fixed inset-x-0 bottom-6 z-40 flex justify-center px-4">
          <div className="pointer-events-auto flex animate-fadeIn items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-3 shadow-lg">
            <span className="flex items-center gap-2 pl-1 pr-2 text-[0.82rem] font-medium text-ink">
              <span className="flex h-6 min-w-6 items-center justify-center rounded-full bg-accent px-2 font-mono text-[0.72rem] font-semibold text-white">
                {selectedCount}
              </span>
              selected
            </span>
            <div className="h-7 w-px bg-line-soft" />
            <Button variant="danger" size="sm" className="gap-1.5" onClick={() => applyBulk("deleted")}>
              <Trash2 className="h-3.5 w-3.5" />
              Mark for deletion
            </Button>
            <Button variant="ok" size="sm" className="gap-1.5" onClick={() => applyBulk("cancelled")}>
              <ShieldCheck className="h-3.5 w-3.5" />
              Cancel — false positive
            </Button>
            <Button variant="flag" size="sm" className="gap-1.5" onClick={() => applyBulk("extended")}>
              <Clock className="h-3.5 w-3.5" />
              Extend retention
            </Button>
            <div className="h-7 w-px bg-line-soft" />
            <Button variant="ghost" size="sm" onClick={clearSelection}>
              Clear
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryStat({
  label,
  value,
  decision,
}: {
  label: string;
  value: number;
  decision?: "pending" | "deleted" | "cancelled" | "extended";
}) {
  return (
    <div className="flex items-center gap-2">
      {decision && <DecisionDot decision={decision} />}
      <div className="leading-tight">
        <div className="font-mono text-[1.15rem] font-semibold text-ink">{value}</div>
        <div className="text-[0.7rem] uppercase tracking-wide text-ink-faint">{label}</div>
      </div>
    </div>
  );
}
