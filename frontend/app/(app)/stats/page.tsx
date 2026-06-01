"use client";

import { useMemo } from "react";
import { Inbox, ShieldCheck, Trash2, XCircle, Clock, FileStack, ListChecks } from "lucide-react";
import { useSession } from "@/lib/session";
import { useDecisions } from "@/lib/decisions";
import { getFlaggedFilesForUser, categoryBreakdown } from "@/lib/data";
import { isPastRetention, pct, cn } from "@/lib/format";
import { categoryLabel, PRIORITY_COLOR } from "@/lib/gdpr";
import { PageHeader, DataSourceBadge } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { DonutChart, HBarList, ProgressBar, type Slice, type HBar } from "@/components/charts";
import { EmptyState } from "@/components/ui";

export default function StatsPage() {
  const { viewedUser } = useSession();
  const { counts } = useDecisions();

  const files = useMemo(
    () => (viewedUser ? getFlaggedFilesForUser(viewedUser.id) : []),
    [viewedUser]
  );
  const fileIds = useMemo(() => files.map((f) => f.id), [files]);
  const c = counts(fileIds);

  const pastRetention = useMemo(
    () => files.filter((f) => isPastRetention(f.lastModified)).length,
    [files]
  );

  if (!viewedUser) return null;

  if (files.length === 0) {
    return (
      <>
        <PageHeader
          title="My stats"
          subtitle={`${viewedUser.name} — ${viewedUser.department}`}
          right={<DataSourceBadge status="demo" />}
        />
        <EmptyState
          icon={<ShieldCheck className="h-9 w-9" />}
          title="Nothing assigned to you"
          hint="You have no flagged files awaiting review. New flags from the next scan will appear here automatically."
        />
      </>
    );
  }

  const fmtMeta = (n: number) =>
    `${Math.round(pct(n, c.total))}% of ${c.total}`;

  const donutData: Slice[] = [
    { name: "Pending review", value: c.pending, color: "#7e92a8" },
    { name: "Marked for deletion", value: c.deleted, color: "#dc2626" },
    { name: "Cancelled (FP)", value: c.cancelled, color: "#16a34a" },
    { name: "Retention extended", value: c.extended, color: "#d97706" },
  ];

  const reviewedPct = c.total > 0 ? (c.decided / c.total) * 100 : 0;

  const catRows: HBar[] = categoryBreakdown(files).map((row) => ({
    label: categoryLabel(row.category),
    value: row.n,
    color: PRIORITY_COLOR[row.priority],
  }));

  return (
    <>
      <PageHeader
        title="My stats"
        subtitle={`${viewedUser.name} — ${viewedUser.department}`}
        right={<DataSourceBadge status="demo" />}
      />

      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <KpiCard
          num={c.total}
          label="Files assigned"
          meta="flagged & owned by you"
          variant="accent"
          mono
          icon={<FileStack className="h-4 w-4" />}
        />
        <KpiCard
          num={c.pending}
          label="Pending review"
          meta={fmtMeta(c.pending)}
          variant="flag"
          mono
          icon={<Inbox className="h-4 w-4" />}
        />
        <KpiCard
          num={c.deleted}
          label="Marked for deletion"
          meta={fmtMeta(c.deleted)}
          variant="danger"
          mono
          icon={<Trash2 className="h-4 w-4" />}
        />
        <KpiCard
          num={c.cancelled}
          label="Cancelled (FP)"
          meta={fmtMeta(c.cancelled)}
          variant="ok"
          mono
          icon={<XCircle className="h-4 w-4" />}
        />
        <KpiCard
          num={c.extended}
          label="Retention extended"
          meta={fmtMeta(c.extended)}
          variant="default"
          mono
          icon={<Clock className="h-4 w-4" />}
        />
      </div>

      {/* Past-retention callout */}
      {pastRetention > 0 && (
        <div className="mt-4 flex items-start gap-3 rounded-xl border border-flag-line bg-flag-soft px-4 py-3">
          <Clock className="mt-0.5 h-4 w-4 flex-none text-flag-text" />
          <p className="text-[0.84rem] leading-relaxed text-flag-text">
            <span className="font-mono font-semibold">{pastRetention}</span> of your
            files {pastRetention === 1 ? "is" : "are"} past the retention window and
            should be reviewed first.
          </p>
        </div>
      )}

      {/* Decision breakdown + review progress */}
      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card card-pad">
          <div className="section-label">Decision breakdown</div>
          <div className="mt-4">
            <DonutChart data={donutData} total={c.total} centerLabel="files" />
          </div>
        </div>

        <div className="card card-pad flex flex-col">
          <div className="section-label">Review progress</div>
          <div className="mt-4 flex flex-1 flex-col justify-center gap-4">
            <div className="flex items-end gap-2">
              <span className="font-mono text-[3rem] font-semibold leading-none tracking-tight text-ok-text">
                {Math.round(reviewedPct)}
              </span>
              <span className="mb-1.5 text-[1.1rem] font-semibold text-ink-faint">%</span>
              <span className="mb-1.5 ml-1 inline-flex items-center gap-1.5 text-[0.78rem] text-ink-muted">
                <ListChecks className="h-3.5 w-3.5 text-ok-text" />
                reviewed
              </span>
            </div>
            <ProgressBar value={reviewedPct} tone="ok" />
            <p className="text-[0.84rem] text-ink-muted">
              <span className="font-mono font-semibold text-ink">{c.decided}</span> of{" "}
              <span className="font-mono font-semibold text-ink">{c.total}</span> files
              reviewed
              {c.pending > 0 && (
                <span className="text-ink-faint">
                  {" "}
                  · <span className="font-mono">{c.pending}</span> still pending
                </span>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Findings by data type */}
      <div className="mt-5 card card-pad">
        <div className="section-label">Findings by data type</div>
        <div className="mt-4">
          {catRows.length > 0 ? (
            <HBarList rows={catRows} />
          ) : (
            <p className="py-6 text-center text-[0.84rem] text-ink-muted">
              No findings to categorise yet.
            </p>
          )}
        </div>
      </div>
    </>
  );
}
