import type { ReactNode } from "react";

/** Pill that tells the user whether a screen is showing live or demo data. */
export function DataSourceBadge({ status }: { status: "live" | "demo" | "loading" }) {
  const map = {
    live: { label: "Live backend", color: "#16a34a", glow: "#f0fdf4" },
    demo: { label: "Demo data", color: "#d97706", glow: "#fffbeb" },
    loading: { label: "Connecting…", color: "#7e92a8", glow: "#eef2f7" },
  } as const;
  const m = map[status];
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-line bg-surface px-2.5 py-1.5 font-mono text-[0.68rem] text-ink-muted">
      <span
        className="inline-block h-1.5 w-1.5 flex-none rounded-full"
        style={{ background: m.color, boxShadow: `0 0 0 3px ${m.glow}` }}
      />
      {m.label}
    </span>
  );
}

export function EngineTag({ label, ok = true }: { label: string; ok?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-line bg-surface px-2.5 py-1.5 font-mono text-[0.68rem] text-ink-muted">
      <span
        className="inline-block h-1.5 w-1.5 flex-none rounded-full"
        style={{
          background: ok ? "#16a34a" : "#7e92a8",
          boxShadow: ok ? "0 0 0 3px #f0fdf4" : "0 0 0 3px #eef2f7",
        }}
      />
      {label}
    </span>
  );
}

export function PageHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-line-soft pb-4">
      <div>
        <h1 className="text-[1.5rem] font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && (
          <p className="mt-1 max-w-[64ch] text-[0.88rem] leading-relaxed text-ink-muted">
            {subtitle}
          </p>
        )}
      </div>
      {right && <div className="flex items-center gap-2">{right}</div>}
    </div>
  );
}
