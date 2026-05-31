"use client";

import { categoryColor, categoryIcon, categoryLabel, categoryPriority } from "@/lib/gdpr";
import { useSettings } from "@/lib/settings-store";
import type { Finding } from "@/lib/types";
import { ConfidenceBar, DetectorBadge, PriorityPill } from "./ui";
import { whyFor } from "@/lib/gdpr";

function maskSnippet(s: string): string {
  // Reveal label before the colon, mask values; otherwise mask the tail.
  return s.replace(/[A-Za-z0-9][A-Za-z0-9.@+/_-]{2,}/g, (tok) =>
    tok.length <= 3 ? tok : tok.slice(0, 1) + "•".repeat(Math.min(tok.length - 1, 6))
  );
}

export function FindingCard({ finding }: { finding: Finding }) {
  const { user, admin } = useSettings();
  const color = categoryColor(finding.category);
  const priority = categoryPriority(finding.category);
  const snippet = admin.maskSnippets ? maskSnippet(finding.snippet) : finding.snippet;

  return (
    <div
      className="rounded-[11px] border border-line bg-surface-alt p-3.5"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      <div className="mb-2.5 flex flex-wrap items-center gap-2.5">
        <span className="text-base leading-none">{categoryIcon(finding.category)}</span>
        <span className="text-[0.84rem] font-semibold text-ink">
          {categoryLabel(finding.category)}
        </span>
        <PriorityPill priority={priority} />
        <ConfidenceBar confidence={finding.confidence} />
        <DetectorBadge detector={finding.detector} />
      </div>

      {user.showSnippets && <code className="snippet">{snippet}</code>}

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-[0.76rem] text-ink-muted">
        {finding.gdprArticles.map((a) => (
          <span key={a} className="article-pill">
            {a}
          </span>
        ))}
        <span className="ml-1">{whyFor(finding.category)}</span>
      </div>
    </div>
  );
}
