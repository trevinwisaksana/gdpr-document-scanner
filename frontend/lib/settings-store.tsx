"use client";

import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { OLLAMA_MODEL } from "./ollama";
import type { SourceType } from "./types";
import { usePersisted } from "./use-persisted";

export interface UserSettings {
  density: "comfortable" | "compact";
  showSnippets: boolean;
  autoExpandHighRisk: boolean;
  defaultSort: "risk" | "recent" | "findings";
  hideLowRisk: boolean;
  ollamaModel: string;
  notifyEmail: boolean;
  notifyOnNewFlags: boolean;
}

export type DeltaFrequency = "daily" | "weekly" | "monthly" | "custom";

export interface AdminSettings {
  connectors: Record<SourceType, boolean>;
  retentionYears: number;
  deltaFrequency: DeltaFrequency;
  scanTime: string; // "HH:MM"
  customSchedule: string; // free-form / ISO for "custom"
  confidenceThreshold: number; // 0..1 — hide findings below this
  autoDeletePastRetention: boolean;
  llmFallback: boolean;
  maskSnippets: boolean;
}

export const DEFAULT_USER_SETTINGS: UserSettings = {
  density: "comfortable",
  showSnippets: true,
  autoExpandHighRisk: true,
  defaultSort: "risk",
  hideLowRisk: false,
  ollamaModel: OLLAMA_MODEL,
  notifyEmail: true,
  notifyOnNewFlags: true,
};

export const DEFAULT_ADMIN_SETTINGS: AdminSettings = {
  connectors: { onedrive: true, sharepoint: true, fileshare: true, gdrive: true },
  retentionYears: 3,
  deltaFrequency: "weekly",
  scanTime: "02:00",
  customSchedule: "",
  confidenceThreshold: 0,
  autoDeletePastRetention: false,
  llmFallback: true,
  maskSnippets: false,
};

interface SettingsContextValue {
  ready: boolean;
  user: UserSettings;
  admin: AdminSettings;
  setUser: (patch: Partial<UserSettings>) => void;
  setAdmin: (patch: Partial<AdminSettings>) => void;
  setConnector: (source: SourceType, enabled: boolean) => void;
  resetUser: () => void;
  resetAdmin: () => void;
}

const Ctx = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [user, setUserState, ru] = usePersisted<UserSettings>(
    "gdpr.settings.user",
    DEFAULT_USER_SETTINGS
  );
  const [admin, setAdminState, ra] = usePersisted<AdminSettings>(
    "gdpr.settings.admin",
    DEFAULT_ADMIN_SETTINGS
  );

  const setUser = useCallback(
    (patch: Partial<UserSettings>) => setUserState((p) => ({ ...p, ...patch })),
    [setUserState]
  );
  const setAdmin = useCallback(
    (patch: Partial<AdminSettings>) => setAdminState((p) => ({ ...p, ...patch })),
    [setAdminState]
  );
  const setConnector = useCallback(
    (source: SourceType, enabled: boolean) =>
      setAdminState((p) => ({ ...p, connectors: { ...p.connectors, [source]: enabled } })),
    [setAdminState]
  );

  const value = useMemo<SettingsContextValue>(
    () => ({
      ready: ru && ra,
      user,
      admin,
      setUser,
      setAdmin,
      setConnector,
      resetUser: () => setUserState(DEFAULT_USER_SETTINGS),
      resetAdmin: () => setAdminState(DEFAULT_ADMIN_SETTINGS),
    }),
    [ru, ra, user, admin, setUser, setAdmin, setConnector, setUserState, setAdminState]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSettings must be used within SettingsProvider");
  return ctx;
}
