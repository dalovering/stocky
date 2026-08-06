"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Callout, Card, Flex, Heading, Text, TextField } from "@radix-ui/themes";

import { AppShell } from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";

export default function SetupPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // If setup has already happened, this page has nothing to do — send them to log in instead.
  useEffect(() => {
    api.authStatus().then((s) => {
      if (!s.needs_setup) router.replace("/login");
    });
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await api.setupAdmin(password);
      router.push("/admin");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Setup failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell containerSize="1">
      <Card size="4">
        <Heading size="6" mb="2">
          Set the admin password
        </Heading>
        <Text size="2" color="gray" as="p" mb="4">
          This is a one-time setup — choose a password for the Administration views. You can
          change it later from Admin → Settings.
        </Text>
        <form onSubmit={submit}>
          <Flex direction="column" gap="3">
            <TextField.Root
              type="password"
              placeholder="New admin password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
            />
            <TextField.Root
              type="password"
              placeholder="Confirm password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
            {error && (
              <Callout.Root color="red">
                <Callout.Text>{error}</Callout.Text>
              </Callout.Root>
            )}
            <Button type="submit" disabled={busy || !password || !confirm}>
              {busy ? "Setting up…" : "Set password & continue"}
            </Button>
          </Flex>
        </form>
      </Card>
    </AppShell>
  );
}
