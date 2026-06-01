"use client";

import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { updateFileStatus, type FindingAction } from "./api";
import type { Decision } from "./types";
import { usePersisted } from "./use-persisted";

type DecisionMap = Record<string, Decision>;

export interface DecisionCounts {
  total: number;
  pending: number;
  deleted: number;
  cancelled: number;
  extended: number;
  /** decided = deleted + cancelled (removed from the review cycle) */
  decided: number;
}

interface DecisionsContextValue {
  ready: boolean;
  decisionFor: (fileId: string) => Decision;
  setDecision: (fileId: string, decision: Decision) => void;
  bulkSet: (fileIds: string[], decision: Decision) => void;
  reset: () => void;
  /** Aggregate decision counts across a set of files. */
  counts: (fileIds: string[]) => DecisionCounts;
}

const Ctx = createContext<DecisionsContextValue | null>(null);

const DECISION_TO_ACTION: Partial<Record<Decision, FindingAction>> = {
  deleted: "confirm_delete",
  cancelled: "false_positive",
  extended: "keep",
};

export function DecisionsProvider({ children }: { children: ReactNode }) {
  const [map, setMap, ready] = usePersisted<DecisionMap>("gdpr.decisions", {});

  const decisionFor = useCallback((fileId: string): Decision => map[fileId] ?? "pending", [map]);

  const setDecision = useCallback(
    (fileId: string, decision: Decision) => {
      setMap((prev) => {
        const next = { ...prev };
        if (decision === "pending") delete next[fileId];
        else next[fileId] = decision;
        return next;
      });
      const action = DECISION_TO_ACTION[decision];
      if (action) {
        updateFileStatus(fileId, action).catch(() => {
          /* decision is kept client-side if the backend call fails */
        });
      }
    },
    [setMap]
  );

  const bulkSet = useCallback(
    (fileIds: string[], decision: Decision) => {
      setMap((prev) => {
        const next = { ...prev };
        for (const id of fileIds) {
          if (decision === "pending") delete next[id];
          else next[id] = decision;
        }
        return next;
      });
    },
    [setMap]
  );

  const reset = useCallback(() => setMap({}), [setMap]);

  const counts = useCallback(
    (fileIds: string[]): DecisionCounts => {
      const c: DecisionCounts = { total: fileIds.length, pending: 0, deleted: 0, cancelled: 0, extended: 0, decided: 0 };
      for (const id of fileIds) {
        const d = map[id] ?? "pending";
        c[d] += 1;
      }
      c.decided = c.deleted + c.cancelled;
      return c;
    },
    [map]
  );

  const value = useMemo<DecisionsContextValue>(
    () => ({ ready, decisionFor, setDecision, bulkSet, reset, counts }),
    [ready, decisionFor, setDecision, bulkSet, reset, counts]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useDecisions(): DecisionsContextValue {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useDecisions must be used within DecisionsProvider");
  return ctx;
}
