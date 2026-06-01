"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import { CheckCircle2, Info, Loader2, X, AlertTriangle } from "lucide-react";
import { avatarColor, avatarInitials, cn } from "@/lib/format";
import { PRIORITY_LABEL } from "@/lib/gdpr";
import type { Decision, Detector, Priority } from "@/lib/types";
import { DECISION_META } from "@/lib/types";

// ── Button ──────────────────────────────────────────────────────────────────
type Variant = "default" | "primary" | "danger" | "ok" | "flag" | "ghost";
type Size = "default" | "sm" | "icon";

const VARIANT_CLASS: Record<Variant, string> = {
  default: "",
  primary: "btn-primary",
  danger: "btn-danger",
  ok: "btn-ok",
  flag: "btn-flag",
  ghost: "border-transparent bg-transparent shadow-none hover:bg-surface-2",
};
const SIZE_CLASS: Record<Size, string> = { default: "", sm: "btn-sm", icon: "btn-icon" };

export function Button({
  variant = "default",
  size = "default",
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button className={cn("btn", VARIANT_CLASS[variant], SIZE_CLASS[size], className)} {...props}>
      {children}
    </button>
  );
}

// ── Badges & pills ────────────────────────────────────────────────────────────
const TONE_CLASS: Record<string, string> = {
  ink: "bg-surface-alt text-ink-muted border-line",
  accent: "bg-accent-soft text-accent-strong border-accent-line",
  danger: "bg-danger-soft text-danger-text border-danger-line",
  ok: "bg-ok-soft text-ok-text border-ok-line",
  flag: "bg-flag-soft text-flag-text border-flag-line",
};

export function Badge({
  tone = "ink",
  className,
  children,
}: {
  tone?: keyof typeof TONE_CLASS;
  className?: string;
  children: ReactNode;
}) {
  return <span className={cn("badge", TONE_CLASS[tone], className)}>{children}</span>;
}

export function PriorityPill({ priority }: { priority: Priority }) {
  return <span className={cn("pri", `pri-${priority}`)}>{PRIORITY_LABEL[priority]}</span>;
}

export function DecisionBadge({ decision }: { decision: Decision }) {
  if (decision === "pending") return null;
  const meta = DECISION_META[decision];
  return <Badge tone={meta.tone === "ink" ? "ink" : meta.tone}>{meta.label}</Badge>;
}

const DETECTOR_LABEL: Record<Detector, string> = {
  regex: "regex",
  ner: "NER",
  llm: "LLM",
};
export function DetectorBadge({ detector }: { detector: Detector }) {
  return <span className="badge badge-mono">{DETECTOR_LABEL[detector]}</span>;
}

// ── Confidence bar ──────────────────────────────────────────────────────────
export function ConfidenceBar({ confidence }: { confidence: number }) {
  const p = Math.round(confidence * 100);
  const tone = confidence >= 0.8 ? "danger" : confidence >= 0.5 ? "flag" : "low";
  const color =
    tone === "danger" ? "#dc2626" : tone === "flag" ? "#d97706" : "#7e92a8";
  const labelColor = tone === "low" ? "text-ink-faint" : tone === "flag" ? "text-flag" : "text-danger";
  return (
    <span className={cn("inline-flex items-center gap-1.5 font-mono text-[0.7rem] font-semibold", labelColor)}>
      <span className="h-[5px] w-[34px] overflow-hidden rounded-full bg-surface-2">
        <span className="block h-full rounded-full" style={{ width: `${p}%`, background: color }} />
      </span>
      {p}%
    </span>
  );
}

// ── Avatar ────────────────────────────────────────────────────────────────────
export function Avatar({ name, size = 34 }: { name: string; size?: number }) {
  return (
    <span
      className="flex flex-none items-center justify-center rounded-full font-semibold text-white"
      style={{
        width: size,
        height: size,
        background: avatarColor(name),
        fontSize: size * 0.36,
      }}
    >
      {avatarInitials(name)}
    </span>
  );
}

// ── Toggle (switch) ─────────────────────────────────────────────────────────
export function Toggle({
  checked,
  onChange,
  label,
  hint,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  hint?: string;
  disabled?: boolean;
}) {
  return (
    <label className={cn("flex items-start justify-between gap-4 py-2.5", disabled && "opacity-50")}>
      <span className="min-w-0">
        <span className="block text-[0.85rem] font-medium text-ink">{label}</span>
        {hint && <span className="mt-0.5 block text-[0.76rem] text-ink-muted">{hint}</span>}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-6 w-11 flex-none rounded-full transition-colors",
          checked ? "bg-accent" : "bg-surface-2 border border-line"
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-all",
            checked ? "left-[22px]" : "left-0.5"
          )}
        />
      </button>
    </label>
  );
}

// ── Segmented control ─────────────────────────────────────────────────────────
export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-[9px] border border-line bg-surface-alt p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-[7px] px-3 py-1.5 text-[0.78rem] font-medium transition-colors",
            value === o.value
              ? "bg-surface text-ink shadow-sm"
              : "text-ink-muted hover:text-ink"
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ── Spinner ─────────────────────────────────────────────────────────────────
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin", className)} />;
}

// ── Empty state ─────────────────────────────────────────────────────────────
export function EmptyState({
  icon,
  title,
  hint,
  children,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line bg-surface-alt px-6 py-14 text-center">
      {icon && <div className="mb-3 text-ink-faint">{icon}</div>}
      <div className="text-[0.95rem] font-semibold text-ink">{title}</div>
      {hint && <div className="mt-1 max-w-md text-[0.82rem] text-ink-muted">{hint}</div>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}

// ── Modal ───────────────────────────────────────────────────────────────────
export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg animate-fadeIn rounded-2xl border border-line bg-surface shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line-soft px-5 py-4">
          <h3 className="text-[1rem] font-semibold text-ink">{title}</h3>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-line-soft px-5 py-3">{footer}</div>
        )}
      </div>
    </div>
  );
}

// ── Toast ─────────────────────────────────────────────────────────────────────
type ToastTone = "info" | "success" | "danger" | "flag";
interface Toast {
  id: number;
  message: string;
  tone: ToastTone;
}
interface ToastCtx {
  toast: (message: string, tone?: ToastTone) => void;
}
const ToastContext = createContext<ToastCtx | null>(null);
let toastSeq = 0;

const TOAST_ICON: Record<ToastTone, ReactNode> = {
  info: <Info className="h-4 w-4 text-accent-strong" />,
  success: <CheckCircle2 className="h-4 w-4 text-ok-text" />,
  danger: <AlertTriangle className="h-4 w-4 text-danger-text" />,
  flag: <AlertTriangle className="h-4 w-4 text-flag-text" />,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toast = useCallback((message: string, tone: ToastTone = "info") => {
    const id = ++toastSeq;
    setToasts((t) => [...t, { id, message, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);
  const value = useMemo(() => ({ toast }), [toast]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[60] flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="pointer-events-auto flex animate-fadeIn items-center gap-2.5 rounded-xl border border-line bg-surface px-4 py-3 text-[0.84rem] text-ink shadow-lg"
          >
            {TOAST_ICON[t.tone]}
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastCtx {
  const ctx = useContext(ToastContext);
  if (!ctx) return { toast: () => {} };
  return ctx;
}
