"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

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
  const router = useRouter();

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

  // ---- Admin idle auto-logout -------------------------------------------------------------
  // While a session is active, sign the admin out after the configured minutes without
  // pointer/keyboard activity (admin_idle_timeout_minutes, 0 = off). Client-enforced comfort
  // feature for a shared device; the JWT's absolute expiry is the server-side backstop.
  const authed = status?.authenticated === true;
  const pathnameRef = useRef(pathname);
  useEffect(() => {
    pathnameRef.current = pathname;
  });

  useEffect(() => {
    if (!authed) return;

    let idleMs = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let lastReset = 0;
    let cancelled = false;

    const expire = async () => {
      await api.logout();
      await refresh();
      if (pathnameRef.current.startsWith("/admin")) router.replace("/login?reason=idle");
    };
    const resetTimer = () => {
      if (timer) clearTimeout(timer);
      if (idleMs > 0) timer = setTimeout(() => void expire(), idleMs);
    };
    const onActivity = () => {
      const now = Date.now();
      if (now - lastReset < 1000) return; // throttle: at most one reset per second
      lastReset = now;
      resetTimer();
    };

    api
      .getSettings()
      .then((s) => {
        if (cancelled) return;
        idleMs = s.admin_idle_timeout_minutes * 60_000;
        resetTimer();
      })
      .catch(() => {}); // e.g. the session just expired — leave the timer off

    const events = ["pointerdown", "keydown", "wheel", "mousemove"] as const;
    for (const e of events) window.addEventListener(e, onActivity, { passive: true });
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      for (const e of events) window.removeEventListener(e, onActivity);
    };
  }, [authed, refresh, router]);

  return <AuthContext.Provider value={{ status, refresh }}>{children}</AuthContext.Provider>;
}
