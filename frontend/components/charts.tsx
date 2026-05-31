"use client";

import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/format";

export interface Slice {
  name: string;
  value: number;
  color: string;
  /** optional secondary label, e.g. a byte volume */
  detail?: string;
}

// ── Donut with center total + side legend ─────────────────────────────────────
export function DonutChart({
  data,
  total,
  centerLabel,
  unit = "",
}: {
  data: Slice[];
  total?: number;
  centerLabel?: string;
  unit?: string;
}) {
  const sum = total ?? data.reduce((a, d) => a + d.value, 0);
  const shown = data.filter((d) => d.value > 0);
  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row">
      <div className="relative h-[180px] w-[180px] flex-none">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={shown.length ? shown : [{ name: "none", value: 1, color: "#eef2f7" }]}
              dataKey="value"
              innerRadius={56}
              outerRadius={84}
              paddingAngle={shown.length > 1 ? 2 : 0}
              stroke="none"
              startAngle={90}
              endAngle={-270}
            >
              {(shown.length ? shown : [{ color: "#eef2f7" }]).map((d, i) => (
                <Cell key={i} fill={d.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v: number, n: string) => [`${v}${unit}`, n]}
              contentStyle={{
                borderRadius: 10,
                border: "1px solid #dde3ec",
                fontSize: 12,
                fontFamily: "IBM Plex Sans, sans-serif",
                boxShadow: "0 4px 14px rgba(50,70,100,.1)",
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-[1.5rem] font-semibold leading-none text-ink">{sum}</span>
          {centerLabel && (
            <span className="mt-1 text-[0.66rem] uppercase tracking-wide text-ink-faint">
              {centerLabel}
            </span>
          )}
        </div>
      </div>
      <ul className="flex-1 space-y-2">
        {data.map((d) => {
          const p = sum > 0 ? Math.round((d.value / sum) * 100) : 0;
          return (
            <li key={d.name} className="flex items-center gap-2.5 text-[0.82rem]">
              <span className="h-2.5 w-2.5 flex-none rounded-sm" style={{ background: d.color }} />
              <span className="flex-1 text-ink-muted">{d.name}</span>
              {d.detail && <span className="font-mono text-[0.7rem] text-ink-faint">{d.detail}</span>}
              <span className="font-mono font-semibold text-ink">{d.value}</span>
              <span className="w-9 text-right font-mono text-[0.72rem] text-ink-faint">{p}%</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── Horizontal bar list ───────────────────────────────────────────────────────
export interface HBar {
  label: string;
  value: number;
  color?: string;
  sub?: string;
}
export function HBarList({ rows, unit = "" }: { rows: HBar[]; unit?: string }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="space-y-1">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[140px_1fr_auto] items-center gap-3 py-1">
          <div className="truncate text-[0.78rem] text-ink-muted" title={r.label}>
            {r.label}
          </div>
          <div className="h-[9px] overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${(r.value / max) * 100}%`, background: r.color ?? "#d97706" }}
            />
          </div>
          <div className="text-right font-mono text-[0.74rem] font-medium text-ink">
            {r.value}
            {unit}
            {r.sub && <span className="ml-1 text-ink-faint">{r.sub}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Progress bar ──────────────────────────────────────────────────────────────
export function ProgressBar({
  value,
  tone = "accent",
  className,
}: {
  value: number; // 0..100
  tone?: "accent" | "ok" | "flag";
  className?: string;
}) {
  const color = tone === "ok" ? "#16a34a" : tone === "flag" ? "#d97706" : "#0891b2";
  return (
    <div className={cn("h-2 overflow-hidden rounded-full bg-surface-2", className)}>
      <div
        className="h-full rounded-full transition-all duration-300"
        style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color }}
      />
    </div>
  );
}

// ── Trend area chart (admin history) ──────────────────────────────────────────
export function TrendChart({
  data,
  dataKey,
  color = "#0891b2",
}: {
  data: { label: string; [k: string]: number | string }[];
  dataKey: string;
  color?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={160}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <defs>
          <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11, fill: "#7e92a8", fontFamily: "IBM Plex Mono" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "#7e92a8", fontFamily: "IBM Plex Mono" }}
          axisLine={false}
          tickLine={false}
          width={36}
        />
        <Tooltip
          contentStyle={{
            borderRadius: 10,
            border: "1px solid #dde3ec",
            fontSize: 12,
            fontFamily: "IBM Plex Sans, sans-serif",
          }}
        />
        <Area
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={2}
          fill={`url(#grad-${dataKey})`}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
