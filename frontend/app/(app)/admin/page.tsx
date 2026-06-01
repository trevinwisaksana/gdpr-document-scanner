"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import {
  Cloud,
  RefreshCw,
  Database,
  FileSearch,
  Users as UsersIcon,
  ScanText,
  ArrowRight,
  Flag,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { PageHeader, DataSourceBadge } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { DonutChart, HBarList, type Slice, type HBar } from "@/components/charts";
import { Button, Spinner, useToast } from "@/components/ui";
import { useAdminData } from "@/lib/live";
import { triggerDriveScan } from "@/lib/api";
import { formatInt, formatDateTime, pct } from "@/lib/format";

export default function AdminDashboardPage() {
  const { toast } = useToast();
  const { data, status, error, refresh, refreshing, updatedAt } = useAdminData();
  const { kpis, owners, flaggedPerOwner } = data;

  // ── Live Cloud Run Drive scan ──────────────────────────────────────────────
  const [driveBusy, setDriveBusy] = useState(false);
  const handleDriveScan = useCallback(async () => {
    setDriveBusy(true);
    try {
      const res = await triggerDriveScan();
      const queued = res.files_queued;
      const statusText = res.status ?? "queued";
      toast(
        typeof queued === "number"
          ? `Drive scan ${statusText} — ${formatInt(queued)} file${queued === 1 ? "" : "s"} queued`
          : `Drive scan ${statusText}`,
        "success"
      );
    } catch {
      toast("Could not reach the Cloud Run scan endpoint", "danger");
    } finally {
      setDriveBusy(false);
    }
  }, [toast]);

  // ── Outcome split (registered → processed → flagged) ───────────────────────
  const unprocessed = Math.max(0, kpis.filesRegistered - kpis.filesProcessed);
  const outcomeSlices: Slice[] = [
    { name: "Flagged (contains PII)", value: kpis.filesFlagged, color: "#dc2626" },
    { name: "Not flagged", value: kpis.filesNotFlagged, color: "#16a34a" },
  ];
  if (unprocessed > 0) {
    outcomeSlices.push({ name: "Not yet processed", value: unprocessed, color: "#cbd5e1" });
  }

  // ── Flagged files per owner ─────────────────────────────────────────────────
  const ownerRows: HBar[] = flaggedPerOwner.map((o) => ({
    label: o.owner,
    value: o.flaggedFiles,
    color: "#d97706",
  }));

  const processedPct = pct(kpis.filesProcessed, kpis.filesRegistered);

  return (
    <div className="animate-fadeIn">
      <PageHeader
        title="Dashboard"
        subtitle="Personal-data exposure across Google Drive, straight from the live scanning pipeline."
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
          <span>
            Showing demo data — the backend could not be reached ({error}). Numbers below are from
            the bundled sample dataset.
          </span>
        </div>
      )}

      {/* ── KPI grid ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
        <KpiCard
          num={formatInt(kpis.filesRegistered)}
          label="Files registered"
          variant="accent"
          mono
          meta={`across ${owners.length} owner${owners.length === 1 ? "" : "s"}`}
          icon={<Database className="h-4 w-4" />}
        />
        <KpiCard
          num={formatInt(kpis.filesProcessed)}
          label="Files processed"
          variant="default"
          mono
          meta={`${processedPct.toFixed(0)}% of registered`}
          icon={<FileSearch className="h-4 w-4" />}
        />
        <KpiCard
          num={formatInt(kpis.filesFlagged)}
          label="Files flagged"
          variant="flag"
          mono
          meta={`${kpis.percentFlagged.toFixed(1)}% of processed`}
          icon={<Flag className="h-4 w-4" />}
        />
        <KpiCard
          num={formatInt(kpis.filesNotFlagged)}
          label="Not flagged"
          variant="ok"
          mono
          icon={<CheckCircle2 className="h-4 w-4" />}
        />
        <KpiCard
          num={formatInt(owners.length)}
          label="Data owners"
          variant="default"
          mono
          meta={`${flaggedPerOwner.length} with flagged data`}
          icon={<UsersIcon className="h-4 w-4" />}
        />
      </div>

      {/* ── Scan control ─────────────────────────────────────────────────── */}
      <div className="card card-pad mt-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="section-label">Scan control</div>
            <h2 className="mt-1 text-[1.05rem] font-semibold text-ink">Run a scan</h2>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button variant="primary" onClick={handleDriveScan} disabled={driveBusy}>
            {driveBusy ? <Spinner /> : <Cloud className="h-4 w-4" />}
            Scan Google Drive
          </Button>
          <Button variant="default" onClick={refresh} disabled={refreshing}>
            {refreshing ? <Spinner /> : <RefreshCw className="h-4 w-4" />}
            Refresh KPIs
          </Button>
          <Link href="/admin/scan" className="btn">
            <ScanText className="h-4 w-4" />
            Live PII scan
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        <p className="mt-3 text-[0.76rem] text-ink-muted">
          "Scan Google Drive" triggers the live Cloud Run pipeline — it lists every accessible Drive
          file and queues it for extraction and PII scanning. Results land in the KPIs above (the
          scan runs in the background; refresh to pull the latest counts).
        </p>
      </div>

      {/* ── Charts row ───────────────────────────────────────────────────── */}
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card card-pad">
          <div className="section-label">Scan outcome</div>
          <h2 className="mb-4 mt-1 text-[1.05rem] font-semibold text-ink">File exposure split</h2>
          <DonutChart data={outcomeSlices} total={kpis.filesRegistered} centerLabel="files" />
        </div>

        <div className="card card-pad">
          <div className="section-label">By data owner</div>
          <h2 className="mb-4 mt-1 text-[1.05rem] font-semibold text-ink">
            <span className="inline-flex items-center gap-2">
              <UsersIcon className="h-4 w-4 text-ink-faint" />
              Flagged files per owner
            </span>
          </h2>
          {ownerRows.length > 0 ? (
            <HBarList rows={ownerRows} />
          ) : (
            <p className="py-6 text-center text-[0.84rem] text-ink-muted">
              No flagged files attributed to an owner yet.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
