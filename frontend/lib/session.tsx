"use client";

import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { ADMIN_ID, CREDENTIALS, DEFAULT_EMPLOYEE_ID } from "./demo";
import { getUserById } from "./data";
import type { Role, User } from "./types";
import { usePersisted } from "./use-persisted";

interface SessionState {
  authUserId: string | null;
  viewedUserId: string | null;
}

interface SessionContextValue {
  ready: boolean;
  authUser: User | null;
  /** The user whose files/stats are currently being viewed (employee demo can switch). */
  viewedUser: User | null;
  role: Role | null;
  isAdmin: boolean;
  isAuthed: boolean;
  login: (username: string, password: string) => { ok: boolean; error?: string };
  logout: () => void;
  /** Switch which user's view is shown (FRONTEND.md "switch to other user's view"). */
  switchViewedUser: (userId: string) => void;
}

const EMPTY: SessionState = { authUserId: null, viewedUserId: null };
const Ctx = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState, ready] = usePersisted<SessionState>("gdpr.session", EMPTY);

  const login = useCallback(
    (username: string, password: string) => {
      const entry = CREDENTIALS[username.trim().toLowerCase()];
      if (!entry || entry.password !== password) {
        return { ok: false, error: "Invalid credentials. Try admin/admin or user/user." };
      }
      setState({ authUserId: entry.userId, viewedUserId: entry.userId });
      return { ok: true };
    },
    [setState]
  );

  const logout = useCallback(() => setState(EMPTY), [setState]);

  const switchViewedUser = useCallback(
    (userId: string) => setState((prev) => ({ ...prev, viewedUserId: userId })),
    [setState]
  );

  const value = useMemo<SessionContextValue>(() => {
    const authUser = state.authUserId ? getUserById(state.authUserId) ?? null : null;
    const role = authUser?.role ?? null;
    // Admins keep their own context; employees default to themselves.
    const viewedId =
      state.viewedUserId ??
      (role === "admin" ? ADMIN_ID : authUser?.id ?? DEFAULT_EMPLOYEE_ID);
    const viewedUser = getUserById(viewedId) ?? authUser;
    return {
      ready,
      authUser,
      viewedUser,
      role,
      isAdmin: role === "admin",
      isAuthed: authUser != null,
      login,
      logout,
      switchViewedUser,
    };
  }, [state, ready, login, logout, switchViewedUser]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
