"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Callout, Card, Flex, Heading, TextField } from "@radix-ui/themes";

import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/components/AuthProvider";
import { api, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // No admin password configured yet — send them to first-launch setup instead.
  useEffect(() => {
    api.authStatus().then((s) => {
      if (s.needs_setup) router.replace("/setup");
    });
  }, [router]);

  // The idle auto-logout redirects here with ?reason=idle — tell the admin what happened.
  // (Read from location instead of useSearchParams to avoid a Suspense boundary.)
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("reason") === "idle") {
      setNotice("You were signed out after a period of inactivity.");
    }
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(password);
      await refresh(); // update the shared auth state (e.g. the shell's admin bar) immediately
      router.push("/admin");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell containerSize="1">
      <Card size="4">
        <Heading size="6" mb="4">
          Admin login
        </Heading>
        <form onSubmit={submit}>
          <Flex direction="column" gap="3">
            {notice && (
              <Callout.Root color="amber">
                <Callout.Text>{notice}</Callout.Text>
              </Callout.Root>
            )}
            <TextField.Root
              type="password"
              placeholder="Admin password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
            />
            {error && (
              <Callout.Root color="red">
                <Callout.Text>{error}</Callout.Text>
              </Callout.Root>
            )}
            <Button type="submit" disabled={busy || !password}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </Flex>
        </form>
      </Card>
    </AppShell>
  );
}
