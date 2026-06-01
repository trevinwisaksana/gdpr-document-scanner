"use client";

import type { ReactNode } from "react";
import { DecisionsProvider } from "@/lib/decisions";
import { SessionProvider } from "@/lib/session";
import { SettingsProvider } from "@/lib/settings-store";
import { ToastProvider } from "@/components/ui";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <SettingsProvider>
        <DecisionsProvider>
          <ToastProvider>{children}</ToastProvider>
        </DecisionsProvider>
      </SettingsProvider>
    </SessionProvider>
  );
}
