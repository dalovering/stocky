"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Flex, Spinner } from "@radix-ui/themes";

import { api } from "@/lib/api";

/**
 * Admin subtree guard: redirects to /setup if no admin password has been configured yet, else to
 * /login unless authenticated. The shared chrome (top bar, nav, logout) lives in `AppShell`,
 * which each admin page renders with its own title/actions — keeping the guard here means it
 * runs once for the whole subtree.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    api
      .authStatus()
      .then((s) => {
        if (s.needs_setup) router.replace("/setup");
        else if (!s.authenticated) router.replace("/login");
        else setReady(true);
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!ready) {
    return (
      <Flex align="center" justify="center" style={{ height: "100vh" }}>
        <Spinner size="3" />
      </Flex>
    );
  }

  return <>{children}</>;
}
