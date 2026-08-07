"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

import { api } from "@/lib/api";
import type { AuthStatus } from "@/lib/types";

type AuthContextValue = {
  /** null until the first /api/auth/status round-trip completes. */
  status: AuthStatus | null;
  /** Re-fetch the auth status; call after login/logout so the UI updates without a reload. */
  refresh: () => Promise<AuthStatus | null>;
};

const AuthContext = createContext<AuthContextValue>({
  status: null,
  refresh: async () => null,
});

/** The client-side view of the admin session, shared app-wide (AppShell, guards, idle logout). */
export function useAuth() {
  return useContext(AuthContext);
}

/**
 * Owns the client's knowledge of "is an admin signed in?". The session itself is an httpOnly
 * cookie the browser scripts can't read, so this polls the tiny `/api/auth/status` endpoint at
 * the moments it could have changed: on load, on navigation, and when the tab regains focus.
 * Purely UI feedback — every admin endpoint still enforces the cookie server-side.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const pathname = usePathname();

  const refresh = useCallback(async () => {
    try {
      const s = await api.authStatus();
      setStatus(s);
      return s;
    } catch {
      // Backend unreachable — keep whatever we last knew rather than flashing state changes.
      return null;
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, pathname]);

  useEffect(() => {
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refresh]);

  return <AuthContext.Provider value={{ status, refresh }}>{children}</AuthContext.Provider>;
}
