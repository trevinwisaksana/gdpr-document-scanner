"use client";

import { useMemo } from "react";
import {
  Plug,
  Clock,
  CalendarClock,
  SlidersHorizontal,
  RotateCcw,
  Info,
} from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Button, Segmented, Toggle } from "@/components/ui";
import { useToast } from "@/components/ui";
import { SourceBadge } from "@/components/file-bits";
import { useSettings, type DeltaFrequency } from "@/lib/settings-store";
import { cn } from "@/lib/format";
import type { SourceType } from "@/lib/types";

const CONNECTORS: SourceType[] = ["onedrive", "sharepoint", "fileshare", "gdrive"];

const RETENTION_OPTIONS = [1, 2, 3, 5, 7];

const FREQUENCY_OPTIONS: { value: DeltaFrequency; label: string }[] = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "custom", label: "Custom" },
];

/** A consistent card shell with an icon header. */
function SettingsCard({
  icon,
  title,
  desc,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card animate-fadeIn">
      <div className="flex items-start gap-3 border-b border-line-soft px-5 py-4">
        <span className="mt-0.5 flex h-9 w-9 flex-none items-center justify-center rounded-[10px] border border-accent-line bg-accent-soft text-accent-strong">
          {icon}
        </span>
        <div className="min-w-0">
          <h2 className="text-[1rem] font-semibold text-ink">{title}</h2>
          <p className="mt-0.5 text-[0.8rem] leading-relaxed text-ink-muted">{desc}</p>
        </div>
      </div>
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

/** Human-readable scan-schedule summary derived from current settings. */
function scheduleSummary(
  frequency: DeltaFrequency,
  scanTime: string,
  customSchedule: string
): string {
  const t = scanTime || "02:00";
  switch (frequency) {
    case "daily":
      return `every day at ${t}`;
    case "weekly":
      return `weekly on Monday at ${t}`;
    case "monthly":
      return `monthly on the 1st at ${t}`;
    case "custom":
      return customSchedule.trim() ? `custom: ${customSchedule.trim()}` : "custom (not yet configured)";
  }
}

export default function AdminSettingsPage() {
  const { admin, setAdmin, setConnector, resetAdmin } = useSettings();
  const { toast } = useToast();

  const enabledConnectors = useMemo(
    () => CONNECTORS.filter((c) => admin.connectors[c]).length,
    [admin.connectors]
  );

  const summary = scheduleSummary(admin.deltaFrequency, admin.scanTime, admin.customSchedule);
  const thresholdPct = Math.round(admin.confidenceThreshold * 100);

  return (
    <div className="animate-fadeIn">
      <PageHeader
        title="Settings"
        subtitle="Configure connectors, retention, and scan scheduling."
      />

      <div className="flex flex-col gap-5">
        {/* ── 1. Connectors ──────────────────────────────────────────── */}
        <SettingsCard
          icon={<Plug className="h-4 w-4" />}
          title="Connectors"
          desc="Controls which sources are included in scans and dashboards. Disabling a connector excludes its files everywhere."
        >
          <div className="mb-3 flex items-center justify-between">
            <span className="label-tiny">Sources</span>
            <span className="font-mono text-[0.72rem] text-ink-muted">
              {enabledConnectors}/{CONNECTORS.length} connected
            </span>
          </div>
          <ul className="divide-y divide-line-soft">
            {CONNECTORS.map((source) => {
              const on = admin.connectors[source];
              return (
                <li key={source} className="flex items-center justify-between gap-4 py-3">
                  <div className="flex min-w-0 flex-col gap-1.5">
                    <SourceBadge source={source} />
                    <span
                      className={cn(
                        "text-[0.76rem] font-medium",
                        on ? "text-ok-text" : "text-ink-faint"
                      )}
                    >
                      {on ? "Connected" : "Disabled"}
                    </span>
                    {source === "gdrive" && (
                      <span className="inline-flex items-center gap-1.5 text-[0.72rem] text-ink-muted">
                        <Info className="h-3 w-3 flex-none text-accent-strong" />
                        Wired to the live Cloud Run scan pipeline.
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={on}
                    aria-label={`Toggle ${source} connector`}
                    onClick={() => setConnector(source, !on)}
                    className={cn(
                      "relative h-6 w-11 flex-none rounded-full transition-colors",
                      on ? "bg-accent" : "border border-line bg-surface-2"
                    )}
                  >
                    <span
                      className={cn(
                        "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-all",
                        on ? "left-[22px]" : "left-0.5"
                      )}
                    />
                  </button>
                </li>
              );
            })}
          </ul>
        </SettingsCard>

        {/* ── 2. Retention period ────────────────────────────────────── */}
        <SettingsCard
          icon={<Clock className="h-4 w-4" />}
          title="Retention period"
          desc="Files older than this are flagged as past-retention across the app (the retention badge updates live)."
        >
          <div className="flex flex-wrap items-center gap-3">
            <Segmented<string>
              options={RETENTION_OPTIONS.map((y) => ({
                value: String(y),
                label: `${y} yr${y === 1 ? "" : "s"}`,
              }))}
              value={String(admin.retentionYears)}
              onChange={(v) => setAdmin({ retentionYears: Number(v) })}
            />
            <span className="font-mono text-[0.72rem] text-ink-muted">
              currently {admin.retentionYears} year{admin.retentionYears === 1 ? "" : "s"}
            </span>
          </div>

          <div className="mt-4 border-t border-line-soft pt-1">
            <Toggle
              checked={admin.autoDeletePastRetention}
              onChange={(v) => setAdmin({ autoDeletePastRetention: v })}
              label="Auto-propose deletion for past-retention files"
              hint="Pre-marks files older than the retention window for review as deletion candidates."
            />
          </div>
        </SettingsCard>

        {/* ── 3. Scan schedule ───────────────────────────────────────── */}
        <SettingsCard
          icon={<CalendarClock className="h-4 w-4" />}
          title="Scan schedule"
          desc="How often incremental (delta) scans run against connected sources."
        >
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <span className="label-tiny">Frequency</span>
              <Segmented<DeltaFrequency>
                options={FREQUENCY_OPTIONS}
                value={admin.deltaFrequency}
                onChange={(v) => setAdmin({ deltaFrequency: v })}
              />
            </div>

            {admin.deltaFrequency === "custom" ? (
              <div className="flex flex-col gap-1.5">
                <label htmlFor="custom-schedule" className="label-tiny">
                  Custom schedule
                </label>
                <input
                  id="custom-schedule"
                  type="text"
                  className="input font-mono"
                  placeholder="e.g. 0 2 * * 1  (cron) or a date-time"
                  value={admin.customSchedule}
                  onChange={(e) => setAdmin({ customSchedule: e.target.value })}
                />
              </div>
            ) : (
              <div className="flex flex-col gap-1.5">
                <label htmlFor="scan-time" className="label-tiny">
                  Time of day
                </label>
                <input
                  id="scan-time"
                  type="time"
                  className="input w-auto font-mono"
                  value={admin.scanTime}
                  onChange={(e) => setAdmin({ scanTime: e.target.value })}
                />
              </div>
            )}

            <div className="flex items-center gap-2 rounded-[10px] border border-accent-line bg-accent-soft px-3.5 py-2.5">
              <CalendarClock className="h-4 w-4 flex-none text-accent-strong" />
              <span className="text-[0.82rem] text-ink">
                Next delta scan:{" "}
                <span className="font-mono font-semibold text-accent-strong">{summary}</span>
              </span>
            </div>
          </div>
        </SettingsCard>

        {/* ── 4. Detection tuning ────────────────────────────────────── */}
        <SettingsCard
          icon={<SlidersHorizontal className="h-4 w-4" />}
          title="Detection tuning"
          desc="Tune how aggressively findings are surfaced and how sensitive values are displayed."
        >
          <div className="flex flex-col gap-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[0.85rem] font-medium text-ink">
                Hide findings below{" "}
                <span className="font-mono font-semibold text-accent-strong">{thresholdPct}%</span>{" "}
                confidence
              </span>
              <span className="font-mono text-[0.72rem] text-ink-muted">{thresholdPct}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={admin.confidenceThreshold}
              onChange={(e) => setAdmin({ confidenceThreshold: Number(e.target.value) })}
              aria-label="Confidence threshold"
              className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-surface-2 accent-accent"
            />
            <div className="flex justify-between font-mono text-[0.66rem] text-ink-faint">
              <span>0% (show all)</span>
              <span>100% (only certain)</span>
            </div>
          </div>

          <div className="mt-3 divide-y divide-line-soft border-t border-line-soft">
            <Toggle
              checked={admin.llmFallback}
              onChange={(v) => setAdmin({ llmFallback: v })}
              label="Use LLM fallback for low-confidence findings"
              hint="Sends low-confidence candidates to the LLM verifier for a second opinion."
            />
            <Toggle
              checked={admin.maskSnippets}
              onChange={(v) => setAdmin({ maskSnippets: v })}
              label="Mask data values in snippets"
              hint="Wired into finding cards — redacts the detected value when previewing context."
            />
          </div>
        </SettingsCard>

        {/* ── Footer ─────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface-alt px-5 py-4">
          <p className="text-[0.8rem] text-ink-muted">
            All settings persist automatically on this device.
          </p>
          <Button
            variant="default"
            onClick={() => {
              resetAdmin();
              toast("Admin settings reset to defaults", "info");
            }}
          >
            <RotateCcw className="h-4 w-4" />
            Reset to defaults
          </Button>
        </div>
      </div>
    </div>
  );
}
