import type { ReactNode } from "react";
import { cn } from "@/lib/format";

type Variant = "default" | "accent" | "flag" | "ok" | "danger";

const SPARK: Record<Variant, string> = {
  default: "bg-line",
  accent: "bg-accent",
  flag: "bg-flag",
  ok: "bg-ok",
  danger: "bg-danger",
};
const NUM_COLOR: Record<Variant, string> = {
  default: "text-ink",
  accent: "text-accent-strong",
  flag: "text-flag",
  ok: "text-ok-text",
  danger: "text-danger-text",
};

export function KpiCard({
  num,
  label,
  meta,
  variant = "default",
  mono = false,
  icon,
}: {
  num: ReactNode;
  label: string;
  meta?: ReactNode;
  variant?: Variant;
  mono?: boolean;
  icon?: ReactNode;
}) {
  return (
    <div className="relative flex flex-col gap-1 overflow-hidden rounded-xl border border-line bg-surface p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div
          className={cn(
            "text-[1.7rem] font-semibold leading-none tracking-tight",
            mono && "font-mono text-[1.4rem]",
            NUM_COLOR[variant]
          )}
        >
          {num}
        </div>
        {icon && <div className="text-ink-faint">{icon}</div>}
      </div>
      <div className="text-[0.78rem] font-medium text-ink-muted">{label}</div>
      {meta && <div className="mt-0.5 font-mono text-[0.68rem] text-ink-faint">{meta}</div>}
      <div className={cn("absolute right-0 top-0 bottom-0 w-1", SPARK[variant])} />
    </div>
  );
}
