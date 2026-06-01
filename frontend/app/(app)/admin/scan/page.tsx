"use client";

import { useCallback, useMemo, useState } from "react";
import { ScanText, Sparkles, ShieldCheck, ShieldAlert, Eraser, SlidersHorizontal } from "lucide-react";
import { PageHeader, DataSourceBadge } from "@/components/PageHeader";
import { Button, Spinner, Badge, Toggle, useToast } from "@/components/ui";
import { scanText, API_BASE, type ScanConfig, type ScanFinding } from "@/lib/api";
import { CATEGORY_META } from "@/lib/gdpr";
import type { PiiCategory } from "@/lib/types";

const SAMPLE = `SUPPLIER ONBOARDING — Robert Bosch GmbH
Primary contact: Markus Bergmann
Email: m.bergmann@nordwind-logistik.de
Phone: +49 711 4023 8890
Registered address: Industriestraße 14, 70565 Stuttgart, Germany
IBAN: DE89 3704 0044 0532 0130 00
Authorised signatory: Markus Bergmann (signed 12.03.2024)`;

const CONFIG_FIELDS: { key: keyof ScanConfig; label: string }[] = [
  { key: "emails", label: "Emails" },
  { key: "phones", label: "Phone numbers" },
  { key: "usernames", label: "Usernames" },
  { key: "signatures", label: "Signatures" },
  { key: "id_documents", label: "ID documents" },
  { key: "ip_addresses", label: "IP addresses" },
  { key: "credit_cards", label: "Credit cards" },
  { key: "iban", label: "IBAN" },
  { key: "ssn", label: "SSN" },
  { key: "dob", label: "Date of birth" },
];

const DEFAULT_CONFIG: ScanConfig = {
  emails: true,
  phones: true,
  usernames: true,
  signatures: true,
  id_documents: true,
  ip_addresses: true,
  credit_cards: true,
  iban: true,
  ssn: true,
  dob: true,
};

const SOURCE_LABEL: Record<string, string> = { regex: "regex", ner: "NER", llm: "LLM" };

/** Human label for a category — falls back to a prettified key for non-GDPR keys. */
function prettyCategory(cat: string): string {
  const meta = CATEGORY_META[cat as PiiCategory];
  if (meta) return meta.label;
  return cat
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
function categoryColor(cat: string): string {
  return CATEGORY_META[cat as PiiCategory]?.color ?? "#7e92a8";
}
function categoryIcon(cat: string): string {
  return CATEGORY_META[cat as PiiCategory]?.icon ?? "•";
}

export default function LiveScanPage() {
  const { toast } = useToast();
  const [text, setText] = useState("");
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<ScanFinding[] | null>(null);
  const [hasPii, setHasPii] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [config, setConfig] = useState<ScanConfig>(DEFAULT_CONFIG);

  // Only send a config payload when the user has narrowed it from the default.
  const configTouched = useMemo(
    () => CONFIG_FIELDS.some(({ key }) => !config[key]),
    [config]
  );

  const runScan = useCallback(async () => {
    const trimmed = text.trim();
    if (!trimmed) {
      toast("Enter some text to scan", "info");
      return;
    }
    setScanning(true);
    setResult(null);
    try {
      const res = await scanText(trimmed, configTouched ? config : undefined);
      setResult(res.findings);
      setHasPii(res.has_pii);
      toast(
        res.has_pii
          ? `Found ${res.findings.length} personal-data item${res.findings.length === 1 ? "" : "s"}`
          : "No personal data detected",
        res.has_pii ? "flag" : "success"
      );
    } catch (e) {
      toast(
        `Scan failed${e instanceof Error ? ` — ${e.message}` : ""}. Is the backend reachable?`,
        "danger"
      );
    } finally {
      setScanning(false);
    }
  }, [text, config, configTouched, toast]);

  const clearAll = useCallback(() => {
    setText("");
    setResult(null);
    setHasPii(false);
  }, []);

  return (
    <div className="animate-fadeIn">
      <PageHeader
        title="Live PII scan"
        subtitle="Paste any text and run it through the deployed detection pipeline — regex, then Azure NER, then LLM fallback. This calls the real backend (POST /scan/text)."
        right={<DataSourceBadge status={API_BASE ? "live" : "demo"} />}
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        {/* ── Input ──────────────────────────────────────────────────────── */}
        <div className="flex flex-col gap-3">
          <div className="card card-pad">
            <div className="mb-2 flex items-center justify-between">
              <span className="section-label">Text to scan</span>
              <span className="font-mono text-[0.7rem] text-ink-faint">{text.length} chars</span>
            </div>
            <textarea
              className="input min-h-[260px] resize-y font-mono text-[0.82rem] leading-relaxed"
              placeholder="Paste a document excerpt, an email, a spreadsheet row…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              spellCheck={false}
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button variant="primary" onClick={runScan} disabled={scanning || !text.trim()}>
                {scanning ? <Spinner /> : <ScanText className="h-4 w-4" />}
                {scanning ? "Scanning…" : "Scan text"}
              </Button>
              <Button variant="default" onClick={() => setText(SAMPLE)} disabled={scanning}>
                <Sparkles className="h-4 w-4" />
                Load sample
              </Button>
              <Button variant="ghost" onClick={clearAll} disabled={scanning || (!text && !result)}>
                <Eraser className="h-4 w-4" />
                Clear
              </Button>
            </div>
          </div>

          {/* ── Results ──────────────────────────────────────────────────── */}
          {result !== null && (
            <div className="card card-pad animate-fadeIn">
              <div className="mb-3 flex flex-wrap items-center gap-2.5">
                {hasPii ? (
                  <span className="inline-flex items-center gap-2 text-[0.92rem] font-semibold text-danger-text">
                    <ShieldAlert className="h-4.5 w-4.5" />
                    Personal data detected
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2 text-[0.92rem] font-semibold text-ok-text">
                    <ShieldCheck className="h-4.5 w-4.5" />
                    No personal data detected
                  </span>
                )}
                <Badge tone={hasPii ? "danger" : "ok"}>
                  {result.length} finding{result.length === 1 ? "" : "s"}
                </Badge>
              </div>

              {result.length > 0 ? (
                <div className="flex flex-col gap-2.5">
                  {result.map((f, i) => (
                    <FindingRow key={`${f.category}-${i}`} finding={f} />
                  ))}
                </div>
              ) : (
                <p className="text-[0.84rem] text-ink-muted">
                  The pipeline ran cleanly and found no GDPR-relevant personal data in this text.
                </p>
              )}
            </div>
          )}
        </div>

        {/* ── Detector config ──────────────────────────────────────────────── */}
        <div className="flex flex-col gap-3">
          <div className="card card-pad">
            <button
              type="button"
              onClick={() => setShowConfig((v) => !v)}
              className="flex w-full items-center justify-between gap-2 text-left"
            >
              <span className="inline-flex items-center gap-2 text-[0.92rem] font-semibold text-ink">
                <SlidersHorizontal className="h-4 w-4 text-ink-faint" />
                Regex detectors
              </span>
              <span className="font-mono text-[0.7rem] text-ink-faint">
                {CONFIG_FIELDS.filter(({ key }) => config[key]).length}/{CONFIG_FIELDS.length} on
              </span>
            </button>
            <p className="mt-1 text-[0.76rem] text-ink-muted">
              Toggle which regex detectors run. NER + LLM fallback always run when regex finds
              nothing.
            </p>
            {showConfig && (
              <div className="mt-2 divide-y divide-line-soft">
                {CONFIG_FIELDS.map(({ key, label }) => (
                  <Toggle
                    key={key}
                    checked={config[key]}
                    onChange={(v) => setConfig((c) => ({ ...c, [key]: v }))}
                    label={label}
                  />
                ))}
              </div>
            )}
            {!showConfig && configTouched && (
              <p className="mt-2 text-[0.72rem] font-medium text-flag-text">
                Custom detector selection active.
              </p>
            )}
          </div>

          <div className="rounded-xl border border-dashed border-line bg-surface-alt px-4 py-3.5 text-[0.78rem] leading-relaxed text-ink-muted">
            <p className="mb-1 font-semibold text-ink">How it works</p>
            The text never touches Google Drive — it runs through the same{" "}
            <code className="font-mono text-ink">scan_text()</code> pipeline the background scanner
            uses: deterministic regex first, then Azure NER, then an LLM verifier for low-confidence
            hits.
          </div>
        </div>
      </div>
    </div>
  );
}

// ── A single live finding ───────────────────────────────────────────────────────
function FindingRow({ finding }: { finding: ScanFinding }) {
  const color = categoryColor(finding.category);
  return (
    <div
      className="rounded-[11px] border border-line bg-surface-alt p-3.5"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2.5">
        <span className="text-base leading-none">{categoryIcon(finding.category)}</span>
        <span className="text-[0.84rem] font-semibold text-ink">
          {prettyCategory(finding.category)}
        </span>
        <span className="badge badge-mono">{SOURCE_LABEL[finding.source] ?? finding.source}</span>
        {typeof finding.confidence === "number" && (
          <span className="font-mono text-[0.7rem] font-semibold text-ink-muted">
            {Math.round(finding.confidence * 100)}%
          </span>
        )}
      </div>
      <code className="snippet">{finding.snippet}</code>
    </div>
  );
}
