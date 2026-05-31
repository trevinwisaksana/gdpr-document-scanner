"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Cloud,
  Play,
  FastForward,
  RotateCcw,
  Layers,
  Database,
  FileSearch,
} from "lucide-react";
import { PageHeader, EngineTag } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { DonutChart, HBarList, ProgressBar, type Slice, type HBar } from "@/components/charts";
import { Button, Spinner, useToast } from "@/components/ui";
import {
  computeKpis,
  latestScanRun,
  getFlaggedFiles,
  getAllFiles,
  isFlagged,
  sourceBreakdown,
  categoryBreakdown,
} from "@/lib/data";
import { useDecisions } from "@/lib/decisions";
import { triggerDriveScan, API_BASE } from "@/lib/api";
import { humanBytes, formatDate, SOURCE_LABEL } from "@/lib/format";
import { categoryLabel, PRIORITY_COLOR } from "@/lib/gdpr";
import type { ScannedFile, Decision } from "@/lib/types";

type ScanType = "full" | "delta";

interface SimState {
  running: boolean;
  type: ScanType | null;
  total: number;
  done: number;
  currentFile: string | null;
}

const IDLE: SimState = { running: false, type: null, total: 0, done: 0, currentFile: null };

export default function AdminDashboardPage() {
  const { toast } = useToast();
  const { counts, decisionFor, reset } = useDecisions();

  const kpis = computeKpis();
  const latest = latestScanRun();
  const flagged = getFlaggedFiles();
  const c = counts(flagged.map((f) => f.id));
  const sources = sourceBreakdown();
  const cats = categoryBreakdown();

  // ── Live Cloud Run scan ───────────────────────────────────────────────────
  const [driveBusy, setDriveBusy] = useState(false);
  const handleDriveScan = useCallback(async () => {
    setDriveBusy(true);
    try {
      const res = await triggerDriveScan();
      const queued = res.files_queued;
      const status = res.status ?? "queued";
      toast(
        typeof queued === "number"
          ? `Drive scan ${status} — ${queued} file${queued === 1 ? "" : "s"} queued`
          : `Drive scan ${status}`,
        "success"
      );
    } catch {
      toast("Could not reach the Cloud Run endpoint", "danger");
    } finally {
      setDriveBusy(false);
    }
  }, [toast]);

  // ── Simulated local scan with live progress ──────────────────────────────
  const [sim, setSim] = useState<SimState>(IDLE);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => () => clearTimer(), [clearTimer]);

  const startSim = useCallback(
    (type: ScanType) => {
      clearTimer();
      const all = getAllFiles();
      const queue: ScannedFile[] =
        type === "delta" ? all.filter((f) => f.lastModified > latest.startedAt) : all;

      if (queue.length === 0) {
        toast("Delta scan — no files changed since the last scan", "info");
        return;
      }

      const total = queue.length;
      setSim({ running: true, type, total, done: 0, currentFile: queue[0].name });

      let i = 0;
      const step = () => {
        const file = queue[i];
        setSim({
          running: true,
          type,
          total,
          done: i + 1,
          currentFile: file.name,
        });
        i += 1;
        if (i < total) {
          const delay = 90 + Math.floor(Math.random() * 30); // 90–120ms
          timerRef.current = setTimeout(step, delay);
        } else {
          timerRef.current = null;
          const flaggedCount = queue.filter(isFlagged).length;
          setSim(IDLE);
          toast(
            `${type === "delta" ? "Delta" : "Full"} scan complete — ${total} file${
              total === 1 ? "" : "s"
            }, ${flaggedCount} flagged`,
            "success"
          );
        }
      };
      timerRef.current = setTimeout(step, 110);
    },
    [clearTimer, latest.startedAt, toast]
  );

  const handleReset = useCallback(() => {
    reset();
    toast("All review decisions reset to pending", "info");
  }, [reset, toast]);

  // ── Donut: most-recent-scan outcome split with volume ─────────────────────
  const all = getAllFiles();
  const notFlaggedFiles = all.filter((f) => !isFlagged(f));
  const flaggedByDecision: Record<Exclude<Decision, "pending"> | "pending", ScannedFile[]> = {
    pending: [],
    deleted: [],
    cancelled: [],
    extended: [],
  };
  for (const f of flagged) {
    flaggedByDecision[decisionFor(f.id)].push(f);
  }
  const volume = (files: ScannedFile[]) =>
    humanBytes(files.reduce((a, f) => a + f.sizeBytes, 0));

  const outcomeSlices: Slice[] = [
    {
      name: "Pending review",
      value: c.pending,
      color: "#d97706",
      detail: volume(flaggedByDecision.pending),
    },
    {
      name: "Marked for deletion",
      value: c.deleted,
      color: "#dc2626",
      detail: volume(flaggedByDecision.deleted),
    },
    {
      name: "Cancelled (false positive)",
      value: c.cancelled,
      color: "#16a34a",
      detail: volume(flaggedByDecision.cancelled),
    },
    {
      name: "Retention extended",
      value: c.extended,
      color: "#2b7be9",
      detail: volume(flaggedByDecision.extended),
    },
    {
      name: "Not flagged",
      value: notFlaggedFiles.length,
      color: "#cbd5e1",
      detail: volume(notFlaggedFiles),
    },
  ];

  // ── Bars ──────────────────────────────────────────────────────────────────
  const catRows: HBar[] = cats.map((cat) => ({
    label: categoryLabel(cat.category),
    value: cat.n,
    color: PRIORITY_COLOR[cat.priority],
  }));

  const sourceRows: HBar[] = sources.map((s) => ({
    label: SOURCE_LABEL[s.sourceType] ?? s.sourceType,
    value: s.nFindings,
    color: "#0891b2",
    sub: `${s.nFiles} file${s.nFiles === 1 ? "" : "s"} · ${humanBytes(s.bytes)}`,
  }));

  const simPct = sim.total > 0 ? (sim.done / sim.total) * 100 : 0;
  const remaining = Math.max(0, sim.total - sim.done);

  return (
    <div className="animate-fadeIn">
      <PageHeader
        title="Dashboard"
        subtitle="Personal-data exposure across all connected sources."
        right={
          <div className="flex items-center gap-2">
            <EngineTag label={API_BASE ? "backend: live" : "engine: demo"} ok={Boolean(API_BASE)} />
            <span className="hidden whitespace-nowrap font-mono text-[0.68rem] text-ink-faint sm:inline">
              Last scan {formatDate(latest.finishedAt)}
            </span>
          </div>
        }
      />

      {/* ── KPI grid ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
        <KpiCard
          num={kpis.filesProcessed}
          label="Files scanned"
          variant="accent"
          meta={`across ${sources.length} source${sources.length === 1 ? "" : "s"}`}
          icon={<FileSearch className="h-4 w-4" />}
        />
        <KpiCard
          num={kpis.filesFlagged}
          label="Files flagged"
          variant="flag"
          meta={`${kpis.percentFlagged.toFixed(1)}% of scanned`}
        />
        <KpiCard num={kpis.totalFindings} label="Total findings" variant="flag" />
        <KpiCard
          num={humanBytes(kpis.bytesScanned)}
          label="Volume scanned"
          variant="default"
          mono
          icon={<Database className="h-4 w-4" />}
        />
        <KpiCard num={`${latest.durationSec}s`} label="Last scan" variant="default" meta={latest.type} />
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
          <Button variant="primary" onClick={handleDriveScan} disabled={driveBusy || sim.running}>
            {driveBusy ? <Spinner /> : <Cloud className="h-4 w-4" />}
            Scan Google Drive
          </Button>
          <Button variant="default" onClick={() => startSim("full")} disabled={sim.running || driveBusy}>
            <Play className="h-4 w-4" />
            Full scan
          </Button>
          <Button variant="default" onClick={() => startSim("delta")} disabled={sim.running || driveBusy}>
            <FastForward className="h-4 w-4" />
            Delta scan
          </Button>
          <Button variant="ghost" onClick={handleReset} disabled={sim.running}>
            <RotateCcw className="h-4 w-4" />
            Reset decisions
          </Button>
        </div>

        <p className="mt-3 text-[0.76rem] text-ink-muted">
          Google Drive scan triggers the live Cloud Run pipeline; Full/Delta are simulated on the
          demo dataset.
        </p>

        {/* ── Live scan progress ─────────────────────────────────────────── */}
        {sim.running && (
          <div className="mt-5 animate-fadeIn rounded-xl border border-line-soft bg-surface-alt p-4">
            <div className="scan-beam-wrap mb-3">
              <div className="scan-beam" />
            </div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-[0.82rem] font-medium text-ink">
                <Spinner className="text-accent-strong" />
                Running {sim.type === "delta" ? "delta" : "full"} scan
              </span>
              <span className="font-mono text-[0.74rem] font-semibold text-accent-strong">
                {Math.round(simPct)}%
              </span>
            </div>
            <ProgressBar value={simPct} />
            <div className="mt-2 truncate font-mono text-[0.72rem] text-ink-faint">
              scanning {sim.currentFile} · {sim.done} / {sim.total} ({Math.round(simPct)}% complete,{" "}
              {remaining} remaining)
            </div>
          </div>
        )}
      </div>

      {/* ── Charts row ───────────────────────────────────────────────────── */}
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card card-pad">
          <div className="section-label">Most recent scan — file outcomes</div>
          <h2 className="mb-4 mt-1 text-[1.05rem] font-semibold text-ink">Outcome split</h2>
          <DonutChart
            data={outcomeSlices}
            total={kpis.filesProcessed}
            centerLabel="files"
          />
        </div>

        <div className="card card-pad">
          <div className="section-label">Findings by PII type</div>
          <h2 className="mb-4 mt-1 text-[1.05rem] font-semibold text-ink">
            <span className="inline-flex items-center gap-2">
              <Layers className="h-4 w-4 text-ink-faint" />
              Categories detected
            </span>
          </h2>
          <HBarList rows={catRows} />
        </div>
      </div>

      {/* ── By source ────────────────────────────────────────────────────── */}
      <div className="card card-pad mt-4">
        <div className="section-label">By source</div>
        <h2 className="mb-4 mt-1 text-[1.05rem] font-semibold text-ink">Findings per connected source</h2>
        <HBarList rows={sourceRows} />
      </div>
    </div>
  );
}
