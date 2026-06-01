"use client";

import { useMemo } from "react";
import { Users as UsersIcon, AlertCircle } from "lucide-react";
import { PageHeader, DataSourceBadge } from "@/components/PageHeader";
import { Avatar } from "@/components/ui";
import { ProgressBar } from "@/components/charts";
import { useAdminData } from "@/lib/live";
import { formatInt, formatDateTime, pct } from "@/lib/format";

export default function AdminUsersPage() {
  const { data, status, error, updatedAt } = useAdminData();

  const rows = useMemo(
    () => [...data.flaggedPerOwner].sort((a, b) => b.flaggedFiles - a.flaggedFiles),
    [data.flaggedPerOwner]
  );
  const totalFlagged = useMemo(() => rows.reduce((a, r) => a + r.flaggedFiles, 0), [rows]);
  // Owners with no flagged files at all (present in /kpis/owners but not in the
  // per-owner flagged breakdown).
  const cleanOwners = useMemo(() => {
    const flaggedSet = new Set(rows.map((r) => r.owner));
    return data.owners.filter((o) => !flaggedSet.has(o));
  }, [data.owners, rows]);

  return (
    <div className="animate-fadeIn">
      <PageHeader
        title="Data owners"
        subtitle="Flagged-file exposure grouped by the Google Drive account that owns each file."
        right={
          <div className="flex items-center gap-2">
            <DataSourceBadge status={status === "loading" ? "loading" : status} />
            {updatedAt != null && (
              <span className="hidden whitespace-nowrap font-mono text-[0.68rem] text-ink-faint sm:inline">
                as of {formatDateTime(updatedAt)}
              </span>
            )}
          </div>
        }
      />

      {status === "demo" && error && (
        <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-flag-line bg-flag-soft px-4 py-3 text-[0.82rem] text-flag-text">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-none" />
          <span>Showing demo data — the backend could not be reached ({error}).</span>
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[0.84rem]">
            <thead>
              <tr className="border-b border-line bg-surface-alt text-left">
                <th className="px-4 py-3 font-semibold text-ink-muted">#</th>
                <th className="px-4 py-3 font-semibold text-ink-muted">Owner</th>
                <th className="px-4 py-3 text-right font-semibold text-ink-muted">Flagged files</th>
                <th className="px-4 py-3 font-semibold text-ink-muted">Share of flagged</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const share = pct(r.flaggedFiles, totalFlagged);
                return (
                  <tr
                    key={r.owner}
                    className="border-b border-line-soft transition-colors last:border-b-0 hover:bg-surface-alt"
                  >
                    <td className="px-4 py-3 font-mono text-ink-faint">{i + 1}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Avatar name={r.owner} size={32} />
                        <span className="truncate font-mono text-[0.8rem] text-ink">{r.owner}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-semibold text-flag-text">
                      {formatInt(r.flaggedFiles)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <ProgressBar value={share} tone="flag" className="w-32" />
                        <span className="w-12 flex-none text-right font-mono text-[0.74rem] font-semibold text-ink">
                          {share.toFixed(1)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {cleanOwners.map((owner) => (
                <tr
                  key={owner}
                  className="border-b border-line-soft transition-colors last:border-b-0 hover:bg-surface-alt"
                >
                  <td className="px-4 py-3 font-mono text-ink-faint">—</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar name={owner} size={32} />
                      <span className="truncate font-mono text-[0.8rem] text-ink">{owner}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink-faint">0</td>
                  <td className="px-4 py-3 text-[0.78rem] text-ink-faint">No flagged files</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-line bg-surface-alt font-semibold">
                <td className="px-4 py-3" />
                <td className="px-4 py-3 text-ink">
                  <span className="inline-flex items-center gap-2">
                    <UsersIcon className="h-3.5 w-3.5 text-ink-faint" />
                    {data.owners.length} owner{data.owners.length === 1 ? "" : "s"}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-mono text-flag-text">
                  {formatInt(totalFlagged)}
                </td>
                <td className="px-4 py-3" />
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <p className="mt-4 text-[0.78rem] leading-relaxed text-ink-muted">
        Per-user review workflow (assigned / pending / deleted) isn’t available from the live API —
        the backend only exposes flagged-file counts per owner. The employee workspace demonstrates
        that review flow on bundled demo data.
      </p>
    </div>
  );
}
