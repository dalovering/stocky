"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Callout, Card, Container, Flex, Heading, TextField } from "@radix-ui/themes";

import { api, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(password);
      router.push("/admin");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Container size="1" p="6">
      <Card size="4">
        <Heading size="6" mb="4">
          Admin login
        </Heading>
        <form onSubmit={submit}>
          <Flex direction="column" gap="3">
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
    </Container>
  );
}
