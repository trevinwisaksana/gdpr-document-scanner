"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Clock,
  RotateCcw,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

import { getFileById, getFlaggedFilesForUser } from "@/lib/data";
import { useSession } from "@/lib/session";
import { useDecisions } from "@/lib/decisions";
import { useSettings } from "@/lib/settings-store";
import { categoryColor } from "@/lib/gdpr";
import { cn, formatDate, humanBytes } from "@/lib/format";
import { fallbackSummary, ollamaAvailable, streamSummary } from "@/lib/ollama";
import type { Decision, ScannedFile } from "@/lib/types";

import { Button, DecisionBadge, EmptyState, Spinner, useToast } from "@/components/ui";
import { DataSourceBadge } from "@/components/PageHeader";
import { FindingCard } from "@/components/FindingCard";
import { DecisionDot, FileTypeIcon, RetentionBadge, SourceBadge } from "@/components/file-bits";

// Decisions that keep a file inside the review cycle.
const CYCLE_DECISIONS: Decision[] = ["pending", "extended"];

// ── Snippet highlighting ───────────────────────────────────────────────────────
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

interface Mark {
  start: number;
  end: number;
  color: string;
}

/**
 * Builds HTML for the document preview, highlighting the FIRST literal
 * occurrence of each finding snippet with its category color. Non-overlapping;
 * snippets not present in the text are skipped. Falls back to escaped plain text.
 */
function buildPreviewHtml(file: ScannedFile): string {
  const text = file.text;
  const marks: Mark[] = [];

  for (const finding of file.findings) {
    const snippet = finding.snippet?.trim();
    if (!snippet || snippet.length < 2) continue;
    const color = categoryColor(finding.category);

    // First occurrence that does not overlap an existing mark.
    let from = 0;
    for (;;) {
      const idx = text.indexOf(snippet, from);
      if (idx === -1) break;
      const end = idx + snippet.length;
      const overlaps = marks.some((m) => idx < m.end && end > m.start);
      if (!overlaps) {
        marks.push({ start: idx, end, color });
        break;
      }
      from = idx + 1;
    }
  }

  if (marks.length === 0) return escapeHtml(text);

  marks.sort((a, b) => a.start - b.start);

  let html = "";
  let cursor = 0;
  for (const m of marks) {
    if (m.start < cursor) continue; // safety against overlap
    html += escapeHtml(text.slice(cursor, m.start));
    const piece = escapeHtml(text.slice(m.start, m.end));
    html +=
      `<mark style="background:${m.color}24;color:inherit;border-radius:3px;` +
      `padding:0 2px;box-decoration-break:clone;-webkit-box-decoration-break:clone;` +
      `box-shadow:inset 0 -1px 0 ${m.color}66;">${piece}</mark>`;
    cursor = m.end;
  }
  html += escapeHtml(text.slice(cursor));
  return html;
}

export default function FileViewerPage() {
  const { fileId } = useParams() as { fileId: string };
  const router = useRouter();
  const { viewedUser } = useSession();
  const { decisionFor, setDecision } = useDecisions();
  const { user: userSettings, admin } = useSettings();
  const { toast } = useToast();

  // ── AI summary state ──────────────────────────────────────────────────────
  const [summary, setSummary] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summarySource, setSummarySource] = useState<"ollama" | "fallback" | null>(null);
  const [summaryModel, setSummaryModel] = useState<string | undefined>(undefined);
  const abortRef = useRef<AbortController | null>(null);

  // Abort any in-flight stream on unmount or when the file changes.
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  // Reset the summary whenever we navigate to a different file.
  useEffect(() => {
    abortRef.current?.abort();
    setSummary("");
    setSummaryLoading(false);
    setSummarySource(null);
    setSummaryModel(undefined);
  }, [fileId]);

  const userFiles = useMemo(
    () => (viewedUser ? getFlaggedFilesForUser(viewedUser.id) : []),
    [viewedUser]
  );

  const current = getFileById(fileId);
  const ownsCurrent =
    !!current &&
    !!viewedUser &&
    (current.ownerUserId === viewedUser.id || current.masterUserId === viewedUser.id);

  // The review cycle: files still pending or with extended retention.
  const cycle = useMemo(
    () => userFiles.filter((f) => CYCLE_DECISIONS.includes(decisionFor(f.id))),
    [userFiles, decisionFor]
  );

  /** Find the neighbour in the cycle relative to a file id, wrapping around. */
  const neighbourInCycle = useCallback(
    (id: string, dir: 1 | -1): ScannedFile | null => {
      if (cycle.length === 0) return null;
      const idx = cycle.findIndex((f) => f.id === id);
      if (idx === -1) {
        // Current file is not in the cycle (e.g. just decided): fall back to an end.
        return dir === 1 ? cycle[0] : cycle[cycle.length - 1];
      }
      const next = (idx + dir + cycle.length) % cycle.length;
      return cycle[next];
    },
    [cycle]
  );

  const generateSummary = useCallback(async () => {
    if (!current) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setSummary("");
    setSummarySource(null);
    setSummaryModel(undefined);
    setSummaryLoading(true);

    const reachable = await ollamaAvailable();
    if (ctrl.signal.aborted) return;

    if (reachable) {
      try {
        const result = await streamSummary(
          current,
          (chunk) => {
            if (!ctrl.signal.aborted) setSummary((prev) => prev + chunk);
          },
          { model: userSettings.ollamaModel, signal: ctrl.signal }
        );
        if (ctrl.signal.aborted) return;
        setSummary(result.text);
        setSummarySource("ollama");
        setSummaryModel(result.model);
        setSummaryLoading(false);
        return;
      } catch {
        if (ctrl.signal.aborted) return;
        // fall through to the rule-based summary
      }
    }

    setSummary(fallbackSummary(current, current.findings));
    setSummarySource("fallback");
    setSummaryLoading(false);
  }, [current, userSettings.ollamaModel]);

  // ── Guards ─────────────────────────────────────────────────────────────────
  if (!viewedUser) {
    return (
      <div className="card card-pad animate-fadeIn">
        <EmptyState title="No user selected" hint="Pick a user to review their flagged files." />
      </div>
    );
  }

  if (!current || !ownsCurrent) {
    return (
      <div className="mx-auto max-w-xl animate-fadeIn">
        <EmptyState
          icon={<X className="h-7 w-7" />}
          title="File not found"
          hint="This file does not exist, or it is not part of the files you are responsible for."
        >
          <Link href="/files" className="btn btn-sm">
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to all files
          </Link>
        </EmptyState>
      </div>
    );
  }

  const currentDecision = decisionFor(current.id);
  const findingIds = current.findings.map((f) => f.id);
  const visibleFindings = current.findings.filter(
    (f) => f.confidence >= admin.confidenceThreshold
  );
  const previewHtml = buildPreviewHtml(current);

  // ── Navigation ───────────────────────────────────────────────────────────--
  const goNeighbour = (dir: 1 | -1) => {
    const target = neighbourInCycle(current.id, dir);
    if (!target) {
      toast("No other files in the review cycle.", "info");
      return;
    }
    if (target.id === current.id) {
      toast("This is the only file left to review.", "info");
      return;
    }
    router.push(`/files/${target.id}`);
  };

  const DECISION_TOAST: Record<Exclude<Decision, "pending">, { msg: string; tone: "danger" | "success" | "flag" }> = {
    deleted: { msg: "Marked for deletion.", tone: "danger" },
    cancelled: { msg: "Dismissed as a false positive.", tone: "success" },
    extended: { msg: "Retention extended.", tone: "flag" },
  };

  const applyDecision = (decision: Exclude<Decision, "pending">) => {
    setDecision(current.id, decision, findingIds);
    const t = DECISION_TOAST[decision];
    toast(t.msg, t.tone);

    if (decision === "extended") {
      // Stays in the cycle — advance to the next pending/extended file.
      const next = neighbourInCycle(current.id, 1);
      if (next && next.id !== current.id) router.push(`/files/${next.id}`);
      return;
    }

    // deleted / cancelled — removed from the cycle. The remaining files are the
    // current cycle minus this one.
    const remaining = cycle.filter((f) => f.id !== current.id);
    if (remaining.length === 0) {
      toast("All files reviewed.", "success");
      router.push("/files");
      return;
    }
    const idx = cycle.findIndex((f) => f.id === current.id);
    const nextFromRemaining =
      idx === -1 ? remaining[0] : remaining[idx % remaining.length];
    router.push(`/files/${nextFromRemaining.id}`);
  };

  const reopen = () => {
    setDecision(current.id, "pending");
    toast("Reopened for review.", "info");
  };

  const cyclePosition = (() => {
    const idx = cycle.findIndex((f) => f.id === current.id);
    return idx === -1 ? null : idx + 1;
  })();

  return (
    <div className="animate-fadeIn">
      {/* ── Top bar ──────────────────────────────────────────────────────── */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-line-soft pb-3">
        <div className="flex items-center gap-3">
          <Link
            href="/files"
            className="inline-flex items-center gap-1.5 text-[0.82rem] font-medium text-ink-muted transition-colors hover:text-ink"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            All files
          </Link>
          <span className="h-4 w-px bg-line" />
          <span className="text-[0.82rem] text-ink-muted">
            Reviewing as <span className="font-semibold text-ink">{viewedUser.name}</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          {cyclePosition != null && (
            <span className="font-mono text-[0.72rem] text-ink-faint">
              {cyclePosition} / {cycle.length} in review
            </span>
          )}
          {currentDecision !== "pending" && <DecisionBadge decision={currentDecision} />}
          <DataSourceBadge status="demo" />
        </div>
      </div>

      {/* ── Three-column workspace ───────────────────────────────────────── */}
      <div className="grid h-[calc(100vh-170px)] grid-cols-[210px_minmax(0,1fr)_340px] gap-4">
        {/* LEFT — explorer */}
        <div className="card flex min-h-0 flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-line-soft px-3 py-2.5">
            <span className="text-[0.7rem] font-semibold uppercase tracking-[0.06em] text-ink-faint">
              Flagged files
            </span>
            <span className="font-mono text-[0.7rem] text-ink-faint">{userFiles.length}</span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-1.5">
            {userFiles.map((f) => {
              const d = decisionFor(f.id);
              const active = f.id === current.id;
              const dimmed = d === "deleted" || d === "cancelled";
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => router.push(`/files/${f.id}`)}
                  title={f.name}
                  className={cn(
                    "mb-0.5 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left transition-colors",
                    active
                      ? "bg-accent-soft text-accent-strong"
                      : "text-ink hover:bg-surface-2",
                    dimmed && !active && "opacity-45"
                  )}
                >
                  <FileTypeIcon name={f.name} className="flex-none" />
                  <span
                    className={cn(
                      "min-w-0 flex-1 truncate text-[0.78rem]",
                      active ? "font-semibold" : "font-medium"
                    )}
                  >
                    {f.name}
                  </span>
                  <DecisionDot decision={d} />
                </button>
              );
            })}
          </div>
        </div>

        {/* CENTER — preview */}
        <div className="card flex min-h-0 flex-col overflow-hidden">
          <div className="border-b border-line-soft px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <FileTypeIcon name={current.name} className="h-5 w-5" />
              <span className="truncate text-[0.98rem] font-semibold text-ink">{current.name}</span>
              <SourceBadge source={current.sourceType} />
              <RetentionBadge lastModified={current.lastModified} />
            </div>
            <div className="mt-1.5 truncate font-mono text-[0.72rem] text-ink-faint">
              {humanBytes(current.sizeBytes)} · modified {formatDate(current.lastModified)} ·{" "}
              {current.path}
            </div>

            {/* Action toolbar */}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1">
                <Button size="sm" onClick={() => goNeighbour(-1)} aria-label="Previous file">
                  <ChevronLeft className="h-3.5 w-3.5" />
                  Previous
                </Button>
                <Button size="sm" onClick={() => goNeighbour(1)} aria-label="Next file">
                  Next
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>

              <span className="mx-0.5 h-5 w-px bg-line" />

              <Button
                size="sm"
                variant="danger"
                onClick={() => applyDecision("deleted")}
                aria-pressed={currentDecision === "deleted"}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </Button>
              <Button
                size="sm"
                variant="ok"
                onClick={() => applyDecision("cancelled")}
                aria-pressed={currentDecision === "cancelled"}
              >
                <X className="h-3.5 w-3.5" />
                Cancel · false positive
              </Button>
              <Button
                size="sm"
                variant="flag"
                onClick={() => applyDecision("extended")}
                aria-pressed={currentDecision === "extended"}
              >
                <Clock className="h-3.5 w-3.5" />
                Extend retention
              </Button>

              {currentDecision !== "pending" && (
                <Button size="sm" variant="ghost" onClick={reopen}>
                  <RotateCcw className="h-3.5 w-3.5" />
                  Reopen
                </Button>
              )}
            </div>
          </div>

          {/* Document pane */}
          <div className="min-h-0 flex-1 overflow-y-auto bg-surface p-5">
            {current.text.trim() ? (
              <pre
                className="whitespace-pre-wrap break-words font-mono text-[0.8rem] leading-relaxed text-ink"
                dangerouslySetInnerHTML={{ __html: previewHtml }}
              />
            ) : (
              <div className="pt-6">
                <EmptyState
                  title="No extractable text"
                  hint="This file type has no preview text. Findings are still shown on the right."
                />
              </div>
            )}
          </div>
        </div>

        {/* RIGHT — findings + summary */}
        <div className="card flex min-h-0 flex-col overflow-hidden">
          <div className="min-h-0 flex-1 overflow-y-auto p-3.5">
            {/* Section 1 — findings */}
            <div className="section-label !mt-0">
              Detected personal data ({visibleFindings.length})
            </div>
            {visibleFindings.length > 0 ? (
              <div className="flex flex-col gap-2.5">
                {visibleFindings.map((f) => (
                  <FindingCard key={f.id} finding={f} />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No findings above threshold"
                hint={
                  current.findings.length > 0
                    ? "All findings fall below the current confidence threshold."
                    : "No personal data was detected in this file."
                }
              />
            )}

            {/* Section 2 — AI summary */}
            <div className="section-label">Why was this flagged?</div>
            <SummaryPanel
              loading={summaryLoading}
              summary={summary}
              source={summarySource}
              model={summaryModel}
              onGenerate={generateSummary}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── AI summary panel ────────────────────────────────────────────────────────--
function SummaryPanel({
  loading,
  summary,
  source,
  model,
  onGenerate,
}: {
  loading: boolean;
  summary: string;
  source: "ollama" | "fallback" | null;
  model?: string;
  onGenerate: () => void;
}): ReactNode {
  const hasContent = summary.length > 0;

  if (!hasContent && !loading) {
    return (
      <div className="rounded-[11px] border border-dashed border-line bg-surface-alt p-4 text-center">
        <p className="mb-3 text-[0.8rem] leading-relaxed text-ink-muted">
          Generate a plain-English explanation of why this file was flagged, using your local
          Ollama model.
        </p>
        <Button variant="primary" size="sm" onClick={onGenerate}>
          <Sparkles className="h-3.5 w-3.5" />
          Generate summary
        </Button>
      </div>
    );
  }

  return (
    <div className="rounded-[11px] border border-line bg-surface-alt p-3.5">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-[0.74rem] font-semibold text-ink">
          <Sparkles className="h-3.5 w-3.5 text-accent-strong" />
          AI summary
          {loading && <Spinner className="ml-1 h-3.5 w-3.5 text-ink-faint" />}
        </span>
        {!loading && hasContent && (
          <Button variant="ghost" size="sm" onClick={onGenerate}>
            <RotateCcw className="h-3 w-3" />
            Regenerate
          </Button>
        )}
      </div>

      {hasContent ? (
        <p className="whitespace-pre-wrap text-[0.82rem] leading-relaxed text-ink">{summary}</p>
      ) : (
        <p className="text-[0.8rem] text-ink-muted">Generating…</p>
      )}

      {!loading && source === "fallback" && (
        <p className="mt-3 border-t border-line-soft pt-2.5 text-[0.72rem] leading-relaxed text-ink-faint">
          Ollama not reachable — showing a rule-based summary. Run{" "}
          <code className="font-mono text-ink-muted">OLLAMA_ORIGINS=* ollama serve</code> to enable
          local AI summaries.
        </p>
      )}
      {!loading && source === "ollama" && model && (
        <p className="mt-3 border-t border-line-soft pt-2.5 font-mono text-[0.7rem] text-ink-faint">
          Generated locally by {model}
        </p>
      )}
    </div>
  );
}
