"use client";

import { useMemo, useState } from "react";
import { Clock3, FileSearch, Flag, ScrollText } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { TrendChart } from "@/components/charts";
import { Badge, Segmented } from "@/components/ui";
import { getScanRuns } from "@/lib/data";
import { cn, formatDate, formatDateTime, humanBytes } from "@/lib/format";
import type { ScanRun } from "@/lib/types";

type Metric = "flagged" | "findings" | "scanned";

const METRIC_OPTIONS: { value: Metric; label: string }[] = [
  { value: "flagged", label: "Files flagged" },
  { value: "findings", label: "Total findings" },
  { value: "scanned", label: "Files scanned" },
];

const METRIC_COLOR: Record<Metric, string> = {
  flagged: "#d97706",
  findings: "#dc2626",
  scanned: "#0891b2",
};

const METRIC_TITLE: Record<Metric, string> = {
  flagged: "Files flagged per run",
  findings: "Total findings per run",
  scanned: "Files scanned per run",
};

const TYPE_META: Record<ScanRun["type"], { tone: "accent" | "flag" | "ok"; label: string }> = {
  full: { tone: "accent", label: "Full" },
  delta: { tone: "flag", label: "Delta" },
  drive: { tone: "ok", label: "Drive" },
};

/** Short MM/DD label for the chart axis. */
function shortDate(ms: number): string {
  const d = new Date(ms);
  return `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
}

function DecisionDots({ run }: { run: ScanRun }) {
  const cells: { key: string; label: string; n: number; color: string }[] = [
    { key: "pending", label: "Pending", n: run.pending, color: "#7e92a8" },
    { key: "deleted", label: "Deleted", n: run.deleted, color: "#dc2626" },
    { key: "cancelled", label: "Cancelled", n: run.cancelled, color: "#0891b2" },
    { key: "extended", label: "Extended", n: run.extended, color: "#d97706" },
  ];
  return (
    <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1">
      {cells.map((c) => (
        <span
          key={c.key}
          title={`${c.label}: ${c.n}`}
          className={cn(
            "inline-flex items-center gap-1.5 font-mono text-[0.74rem]",
            c.n > 0 ? "text-ink" : "text-ink-faint"
          )}
        >
          <span
            className="inline-block h-2 w-2 flex-none rounded-full"
            style={{ background: c.n > 0 ? c.color : "#cdd6e2" }}
          />
          {c.n}
        </span>
      ))}
    </div>
  );
}

export default function AdminHistoryPage() {
  const runs = useMemo<ScanRun[]>(() => getScanRuns(), []);
  const [metric, setMetric] = useState<Metric>("flagged");

  const chartData = useMemo(
    () =>
      [...runs].reverse().map((r) => ({
        label: shortDate(r.startedAt),
        flagged: r.filesFlagged,
        findings: r.totalFindings,
        scanned: r.filesScanned,
      })),
    [runs]
  );

  const latestId = runs[0]?.id;

  return (
    <div className="animate-fadeIn">
      <PageHeader
        title="Scan history"
        subtitle="Point-in-time snapshots captured at the start of each scan run."
      />

      {/* ── Trend ─────────────────────────────────────────────────────── */}
      <section className="card card-pad mb-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="section-label">Trend</div>
            <h2 className="mt-1 text-[1.02rem] font-semibold text-ink">{METRIC_TITLE[metric]}</h2>
          </div>
          <Segmented options={METRIC_OPTIONS} value={metric} onChange={setMetric} />
        </div>
        <TrendChart data={chartData} dataKey={metric} color={METRIC_COLOR[metric]} />
      </section>

      {/* ── Runs table ────────────────────────────────────────────────── */}
      <section className="card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft px-5 py-4">
          <div className="flex items-center gap-2.5">
            <ScrollText className="h-4 w-4 text-ink-faint" />
            <h2 className="text-[1.02rem] font-semibold text-ink">All scan runs</h2>
          </div>
          <span className="font-mono text-[0.74rem] text-ink-faint">
            {runs.length} run{runs.length === 1 ? "" : "s"}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] border-collapse text-[0.84rem]">
            <thead>
              <tr className="border-b border-line-soft text-left text-[0.68rem] uppercase tracking-wide text-ink-faint">
                <th className="px-5 py-2.5 font-medium">Run</th>
                <th className="px-3 py-2.5 font-medium">Started</th>
                <th className="px-3 py-2.5 text-right font-medium">Duration</th>
                <th className="px-3 py-2.5 text-right font-medium">Scanned</th>
                <th className="px-3 py-2.5 text-right font-medium">Flagged</th>
                <th className="px-3 py-2.5 text-right font-medium">Not flagged</th>
                <th className="px-3 py-2.5 text-right font-medium">Findings</th>
                <th className="px-3 py-2.5 text-right font-medium">Volume</th>
                <th className="px-5 py-2.5 text-right font-medium">Decisions at snapshot</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const isLatest = r.id === latestId;
                const meta = TYPE_META[r.type];
                const flaggedPct =
                  r.filesScanned > 0 ? Math.round((r.filesFlagged / r.filesScanned) * 100) : 0;
                return (
                  <tr
                    key={r.id}
                    className={cn(
                      "border-b border-line-soft transition-colors last:border-0 hover:bg-surface-alt",
                      isLatest && "bg-accent-soft/40"
                    )}
                  >
                    {/* Run: type badge + label + recent marker */}
                    <td className="px-5 py-3.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                        <span className="font-mono text-[0.78rem] text-ink">{r.label}</span>
                        {isLatest && (
                          <Badge tone="ok" className="badge-mono">
                            Most recent
                          </Badge>
                        )}
                      </div>
                    </td>

                    {/* Started */}
                    <td className="whitespace-nowrap px-3 py-3.5 text-[0.8rem] text-ink-muted">
                      {formatDateTime(r.startedAt)}
                      <span className="block text-[0.7rem] text-ink-faint">{formatDate(r.startedAt)}</span>
                    </td>

                    {/* Duration */}
                    <td className="px-3 py-3.5 text-right font-mono text-[0.8rem] text-ink-muted">
                      {r.durationSec}s
                    </td>

                    {/* Scanned */}
                    <td className="px-3 py-3.5 text-right font-mono text-[0.82rem] font-medium text-ink">
                      {r.filesScanned}
                    </td>

                    {/* Flagged + percent */}
                    <td className="px-3 py-3.5 text-right">
                      <span className="font-mono text-[0.82rem] font-semibold text-flag-text">
                        {r.filesFlagged}
                      </span>
                      <span className="ml-1.5 font-mono text-[0.7rem] text-ink-faint">
                        {flaggedPct}%
                      </span>
                    </td>

                    {/* Not flagged */}
                    <td className="px-3 py-3.5 text-right font-mono text-[0.82rem] text-ink-muted">
                      {r.filesNotFlagged}
                    </td>

                    {/* Findings */}
                    <td className="px-3 py-3.5 text-right font-mono text-[0.82rem] font-medium text-danger-text">
                      {r.totalFindings}
                    </td>

                    {/* Volume */}
                    <td className="whitespace-nowrap px-3 py-3.5 text-right font-mono text-[0.8rem] text-ink-muted">
                      {humanBytes(r.bytesScanned)}
                    </td>

                    {/* Decisions at snapshot */}
                    <td className="px-5 py-3.5">
                      <DecisionDots run={r} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Legend footer */}
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t border-line-soft px-5 py-3 text-[0.72rem] text-ink-muted">
          <span className="flex items-center gap-1.5">
            <FileSearch className="h-3.5 w-3.5 text-ink-faint" /> Scanned / flagged are counts at run start
          </span>
          <span className="flex items-center gap-1.5">
            <Flag className="h-3.5 w-3.5 text-flag-text" /> Percent is share of scanned files flagged
          </span>
          <span className="flex items-center gap-1.5">
            <Clock3 className="h-3.5 w-3.5 text-ink-faint" /> Decisions reflect the snapshot just before the next run
          </span>
        </div>
      </section>
    </div>
  );
}
