"use client";

import { useState, type ReactNode } from "react";
import {
  Monitor,
  Eye,
  ArrowUpDown,
  EyeOff,
  Maximize2,
  Sparkles,
  Bell,
  Mail,
  BellRing,
  RotateCcw,
  ServerCog,
} from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Button, Segmented, Toggle, Spinner, Badge, useToast } from "@/components/ui";
import { useSettings, type UserSettings } from "@/lib/settings-store";
import { OLLAMA_URL, ollamaAvailable } from "@/lib/ollama";

// ── Local: bordered settings card with a titled header ──────────────────────
function SettingsCard({
  icon,
  title,
  hint,
  children,
}: {
  icon: ReactNode;
  title: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <section className="card animate-fadeIn">
      <div className="flex items-start gap-3 border-b border-line-soft px-5 py-4">
        <span className="flex h-9 w-9 flex-none items-center justify-center rounded-[10px] border border-accent-line bg-accent-soft text-accent-strong">
          {icon}
        </span>
        <div className="min-w-0">
          <h2 className="text-[0.98rem] font-semibold leading-tight text-ink">{title}</h2>
          {hint && <p className="mt-0.5 text-[0.78rem] text-ink-muted">{hint}</p>}
        </div>
      </div>
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

// ── Local: a labelled row that pairs a control with explanatory copy ─────────
function ControlRow({
  label,
  hint,
  control,
}: {
  label: ReactNode;
  hint?: string;
  control: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-2.5">
      <div className="min-w-0">
        <div className="text-[0.85rem] font-medium text-ink">{label}</div>
        {hint && <div className="mt-0.5 text-[0.76rem] text-ink-muted">{hint}</div>}
      </div>
      <div className="flex-none">{control}</div>
    </div>
  );
}

// "Live" tag shown next to settings that take effect immediately.
function LiveTag() {
  return (
    <Badge tone="ok" className="ml-2 align-middle">
      Live
    </Badge>
  );
}

const DENSITY_OPTIONS: { value: UserSettings["density"]; label: string }[] = [
  { value: "comfortable", label: "Comfortable" },
  { value: "compact", label: "Compact" },
];

const SORT_OPTIONS: { value: UserSettings["defaultSort"]; label: string }[] = [
  { value: "risk", label: "Risk" },
  { value: "recent", label: "Recent" },
  { value: "findings", label: "Findings" },
];

export default function SettingsPage() {
  const { ready, user, setUser, resetUser } = useSettings();
  const { toast } = useToast();
  const [testing, setTesting] = useState(false);

  async function testOllama() {
    setTesting(true);
    try {
      const ok = await ollamaAvailable();
      if (ok) toast("Ollama reachable", "success");
      else toast("Ollama not reachable at " + OLLAMA_URL, "danger");
    } finally {
      setTesting(false);
    }
  }

  if (!ready) {
    return (
      <>
        <PageHeader title="Settings" subtitle="Personalise how your flagged files are shown." />
        <div className="flex items-center gap-2 px-1 py-8 text-[0.85rem] text-ink-muted">
          <Spinner /> Loading your preferences…
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Personalise how your flagged files are shown."
        right={
          <Badge tone="accent">
            <Eye className="h-3.5 w-3.5" /> Saved to this browser
          </Badge>
        }
      />

      <p className="mb-5 max-w-[68ch] text-[0.82rem] leading-relaxed text-ink-muted">
        Most preferences are <span className="font-medium text-ok-text">live</span> — they change
        your file list and finding cards the moment you toggle them. Notification options are saved
        for your account. Everything persists automatically in this browser.
      </p>

      <div className="grid gap-5">
        {/* 1) Display */}
        <SettingsCard
          icon={<Monitor className="h-[18px] w-[18px]" />}
          title="Display"
          hint="Control the look and ordering of your flagged-files view."
        >
          <div className="divide-y divide-line-soft">
            <ControlRow
              label={
                <>
                  Density
                  <LiveTag />
                </>
              }
              hint="Spacing of rows in the file list."
              control={
                <Segmented
                  options={DENSITY_OPTIONS}
                  value={user.density}
                  onChange={(density) => setUser({ density })}
                />
              }
            />

            <Toggle
              checked={user.showSnippets}
              onChange={(showSnippets) => setUser({ showSnippets })}
              label="Show data snippets on finding cards"
              hint="Display the matched excerpt under each finding. Takes effect immediately."
            />

            <Toggle
              checked={user.autoExpandHighRisk}
              onChange={(autoExpandHighRisk) => setUser({ autoExpandHighRisk })}
              label="Highlight high-risk files"
              hint="Adds a red accent stripe to high-priority files in your list. Applied immediately."
            />

            <Toggle
              checked={user.hideLowRisk}
              onChange={(hideLowRisk) => setUser({ hideLowRisk })}
              label="Hide low-risk files from my list"
              hint="Keep your queue focused on what matters most. Applied to the file list immediately."
            />

            <ControlRow
              label={
                <>
                  Default sort
                  <LiveTag />
                </>
              }
              hint="How your flagged files are ordered when the page loads."
              control={
                <Segmented
                  options={SORT_OPTIONS}
                  value={user.defaultSort}
                  onChange={(defaultSort) => setUser({ defaultSort })}
                />
              }
            />
          </div>
        </SettingsCard>

        {/* 2) AI summaries (local Ollama) */}
        <SettingsCard
          icon={<Sparkles className="h-[18px] w-[18px]" />}
          title="AI summaries (local Ollama)"
          hint="Plain-English explanations of why a file was flagged, generated on your machine."
        >
          <div className="grid gap-4">
            <div>
              <label htmlFor="ollama-model" className="label-tiny">
                Model
              </label>
              <input
                id="ollama-model"
                className="input mt-1.5 font-mono"
                value={user.ollamaModel}
                onChange={(e) => setUser({ ollamaModel: e.target.value })}
                placeholder="llama3.2"
                spellCheck={false}
                autoComplete="off"
              />
              <p className="mt-1.5 text-[0.76rem] text-ink-muted">
                Model used to explain why a file was flagged (runs on your machine).
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-line bg-surface-alt px-3.5 py-3">
              <div className="flex items-center gap-2.5 min-w-0">
                <ServerCog className="h-4 w-4 flex-none text-ink-faint" />
                <div className="min-w-0">
                  <div className="label-tiny">Endpoint</div>
                  <div className="truncate font-mono text-[0.8rem] text-ink">{OLLAMA_URL}</div>
                </div>
              </div>
              <Button size="sm" onClick={testOllama} disabled={testing}>
                {testing ? <Spinner /> : <ServerCog className="h-3.5 w-3.5" />}
                {testing ? "Testing…" : "Test connection"}
              </Button>
            </div>
          </div>
        </SettingsCard>

        {/* 3) Notifications */}
        <SettingsCard
          icon={<Bell className="h-[18px] w-[18px]" />}
          title="Notifications"
          hint="Choose how you hear about new personal-data findings."
        >
          <div className="divide-y divide-line-soft">
            <Toggle
              checked={user.notifyEmail}
              onChange={(notifyEmail) => setUser({ notifyEmail })}
              label="Email me about new findings"
              hint="Receive an email digest when the scanner detects new personal data in your files."
            />
            <Toggle
              checked={user.notifyOnNewFlags}
              onChange={(notifyOnNewFlags) => setUser({ notifyOnNewFlags })}
              label="Notify when new files are flagged"
              hint="Get a heads-up the moment one of your files is newly flagged."
            />
          </div>
          <p className="mt-3 flex items-center gap-1.5 text-[0.74rem] text-ink-faint">
            <Mail className="h-3.5 w-3.5" />
            Notification delivery is cosmetic in this demo — preferences are still saved.
          </p>
        </SettingsCard>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-line bg-surface-alt px-5 py-4">
          <div className="text-[0.8rem] text-ink-muted">
            Restore every preference on this page to its default value.
          </div>
          <Button
            variant="ghost"
            onClick={() => {
              resetUser();
              toast("Settings reset");
            }}
          >
            <RotateCcw className="h-4 w-4" />
            Reset to defaults
          </Button>
        </div>
      </div>
    </>
  );
}
