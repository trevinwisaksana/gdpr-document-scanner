"use client";

// ── Live admin data, with automatic demo fallback ───────────────────────────────
// The admin/DPO surface reads real aggregates from the deployed backend (Postgres
// drive_files via /kpis/*). If the backend is unreachable or DEMO_MODE is on, we
// fall back to the bundled demo dataset so the dashboard is never blank. The
// returned `status` tells the UI whether it's showing "live" or "demo" data.

import { useCallback, useEffect, useState } from "react";
import { LIVE, fetchKpis, fetchOwners, fetchFlaggedPerOwner, type LiveKpis } from "./api";
import { computeKpis, flaggedPerOwner, getUserById } from "./data";

export interface OwnerFlagged {
  owner: string;
  flaggedFiles: number;
}

export interface AdminLiveData {
  kpis: LiveKpis;
  owners: string[];
  flaggedPerOwner: OwnerFlagged[];
}

export type LiveStatus = "loading" | "live" | "demo";

/** Build the fallback view from the bundled demo corpus. Deterministic (no Date). */
function demoData(): AdminLiveData {
  const k = computeKpis();
  const per: OwnerFlagged[] = flaggedPerOwner().map(({ userId, flaggedFiles }) => ({
    owner: getUserById(userId)?.name ?? userId,
    flaggedFiles,
  }));
  return {
    kpis: {
      filesRegistered: k.filesRegistered,
      filesFlagged: k.filesFlagged,
      filesProcessed: k.filesProcessed,
      filesNotFlagged: k.filesNotFlagged,
      percentFlagged: k.percentFlagged,
    },
    owners: per.map((p) => p.owner),
    flaggedPerOwner: per,
  };
}

export interface UseAdminData {
  data: AdminLiveData;
  status: LiveStatus;
  error: string | null;
  refresh: () => void;
  refreshing: boolean;
  /** epoch ms of the last successful live fetch (null until then). */
  updatedAt: number | null;
}

export function useAdminData(): UseAdminData {
  const [data, setData] = useState<AdminLiveData>(() => demoData());
  const [status, setStatus] = useState<LiveStatus>(LIVE ? "loading" : "demo");
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!LIVE) {
      setData(demoData());
      setStatus("demo");
      return;
    }
    setRefreshing(true);
    try {
      const [kpis, owners, per] = await Promise.all([
        fetchKpis(),
        fetchOwners(),
        fetchFlaggedPerOwner(),
      ]);
      setData({ kpis, owners, flaggedPerOwner: per });
      setStatus("live");
      setError(null);
      setUpdatedAt(Date.now());
    } catch (e) {
      setData(demoData());
      setStatus("demo");
      setError(e instanceof Error ? e.message : "could not reach the backend");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { data, status, error, refresh: load, refreshing, updatedAt };
}
