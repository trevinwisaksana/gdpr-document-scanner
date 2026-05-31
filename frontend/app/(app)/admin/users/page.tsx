"use client";

import { useMemo, useState } from "react";
import { Users as UsersIcon } from "lucide-react";
import { getUsers, getScanRuns, getFlaggedFilesForUser } from "@/lib/data";
import { useDecisions } from "@/lib/decisions";
import { formatDate, cn } from "@/lib/format";
import { Avatar, Badge } from "@/components/ui";
import { ProgressBar } from "@/components/charts";
import { PageHeader } from "@/components/PageHeader";
import type { User, ScanRun } from "@/lib/types";

interface UserRow {
  user: User;
  fileIds: string[];
  assigned: number;
  pending: number;
  deleted: number;
  cancelled: number;
  extended: number;
  decided: number;
  total: number;
  reviewPct: number;
}

export default function AdminUsersPage() {
  const users = useMemo<User[]>(() => getUsers(), []);
  const runs = useMemo<ScanRun[]>(() => getScanRuns(), []);
  const { counts } = useDecisions();

  const [selectedRunId, setSelectedRunId] = useState<string>(runs[0]?.id ?? "");
  const selectedRun = runs.find((r) => r.id === selectedRunId) ?? runs[0];

  const rows: UserRow[] = useMemo(() => {
    return users.map((user) => {
      const fileIds = getFlaggedFilesForUser(user.id).map((f) => f.id);
      const c = counts(fileIds);
      const total = c.total;
      const reviewPct = total > 0 ? (c.decided / total) * 100 : 0;
      return {
        user,
        fileIds,
        assigned: fileIds.length,
        pending: c.pending,
        deleted: c.deleted,
        cancelled: c.cancelled,
        extended: c.extended,
        decided: c.decided,
        total,
        reviewPct,
      };
    });
  }, [users, counts]);

  // Totals across employees only (the DPO/admin holds no assigned files).
  const totals = useMemo(() => {
    return rows
      .filter((r) => r.user.role === "employee")
      .reduce(
        (acc, r) => ({
          assigned: acc.assigned + r.assigned,
          pending: acc.pending + r.pending,
          deleted: acc.deleted + r.deleted,
          cancelled: acc.cancelled + r.cancelled,
          extended: acc.extended + r.extended,
        }),
        { assigned: 0, pending: 0, deleted: 0, cancelled: 0, extended: 0 }
      );
  }, [rows]);

  return (
    <div className="animate-fadeIn">
      <PageHeader
        title="Users"
        subtitle="Per-user review progress across the data estate."
        right={
          selectedRun && (
            <span className="inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-line bg-surface px-3 py-1.5 font-mono text-[0.7rem] text-ink-muted">
              as of {formatDate(selectedRun.startedAt)}
            </span>
          )
        }
      />

      {/* Scan snapshot selector */}
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <span className="label-tiny">Scan snapshot</span>
        <div className="inline-flex flex-wrap gap-1 rounded-[9px] border border-line bg-surface-alt p-0.5">
          {runs.map((run) => {
            const active = run.id === selectedRunId;
            return (
              <button
                key={run.id}
                type="button"
                onClick={() => setSelectedRunId(run.id)}
                className={cn(
                  "rounded-[7px] px-3 py-1.5 font-mono text-[0.72rem] font-medium transition-colors",
                  active
                    ? "bg-surface text-ink shadow-sm"
                    : "text-ink-muted hover:text-ink"
                )}
                aria-pressed={active}
              >
                {run.label || formatDate(run.startedAt)}
              </button>
            );
          })}
        </div>
      </div>

      {/* Users table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[0.83rem]">
            <thead>
              <tr className="border-b border-line bg-surface-alt text-left">
                <th className="px-4 py-3 font-semibold text-ink-muted">User</th>
                <th className="px-4 py-3 font-semibold text-ink-muted">Department</th>
                <th className="px-4 py-3 font-semibold text-ink-muted">Role</th>
                <th className="px-4 py-3 text-right font-semibold text-ink-muted">Assigned</th>
                <th className="px-4 py-3 text-right font-semibold text-ink-muted">Pending</th>
                <th className="px-4 py-3 text-right font-semibold text-ink-muted">Deleted</th>
                <th className="px-4 py-3 text-right font-semibold text-ink-muted">Cancelled</th>
                <th className="px-4 py-3 text-right font-semibold text-ink-muted">Extended</th>
                <th className="px-4 py-3 font-semibold text-ink-muted">Review</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const noAssigned = r.assigned === 0;
                return (
                  <tr
                    key={r.user.id}
                    className="border-b border-line-soft transition-colors last:border-b-0 hover:bg-surface-alt"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Avatar name={r.user.name} size={32} />
                        <div className="min-w-0">
                          <div className="truncate font-medium text-ink">{r.user.name}</div>
                          <div className="truncate font-mono text-[0.72rem] text-ink-faint">
                            {r.user.email}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-ink-muted">{r.user.department}</td>
                    <td className="px-4 py-3">
                      <Badge tone={r.user.role === "admin" ? "accent" : "ink"}>
                        {r.user.role === "admin" ? "Admin" : "Employee"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-semibold text-ink">
                      {noAssigned ? <span className="text-ink-faint">—</span> : r.assigned}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-ink-muted">
                      {noAssigned ? <span className="text-ink-faint">—</span> : r.pending}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-ink-muted">
                      {noAssigned ? <span className="text-ink-faint">—</span> : r.deleted}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-ink-muted">
                      {noAssigned ? <span className="text-ink-faint">—</span> : r.cancelled}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-ink-muted">
                      {noAssigned ? <span className="text-ink-faint">—</span> : r.extended}
                    </td>
                    <td className="px-4 py-3">
                      {noAssigned ? (
                        <span className="text-ink-faint">—</span>
                      ) : (
                        <div className="flex items-center gap-2.5">
                          <ProgressBar value={r.reviewPct} tone="ok" className="w-24" />
                          <span className="w-9 flex-none text-right font-mono text-[0.74rem] font-semibold text-ink">
                            {Math.round(r.reviewPct)}%
                          </span>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-line bg-surface-alt font-semibold">
                <td className="px-4 py-3 text-ink" colSpan={3}>
                  <span className="inline-flex items-center gap-2">
                    <UsersIcon className="h-3.5 w-3.5 text-ink-faint" />
                    Totals — {rows.filter((r) => r.user.role === "employee").length} employees
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-mono text-ink">{totals.assigned}</td>
                <td className="px-4 py-3 text-right font-mono text-ink">{totals.pending}</td>
                <td className="px-4 py-3 text-right font-mono text-ink">{totals.deleted}</td>
                <td className="px-4 py-3 text-right font-mono text-ink">{totals.cancelled}</td>
                <td className="px-4 py-3 text-right font-mono text-ink">{totals.extended}</td>
                <td className="px-4 py-3" />
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );
}
