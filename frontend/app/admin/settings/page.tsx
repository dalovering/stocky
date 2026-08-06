"use client";

import { useEffect, useState } from "react";
import { Button, Callout, Card, Flex, Heading, Switch, Text, TextField } from "@radix-ui/themes";

import { AppShell } from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import type { AppSettings } from "@/lib/types";

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getSettings().then(setSettings);
  }, []);

  async function update(patch: Partial<AppSettings>) {
    try {
      setSettings(await api.updateSettings(patch));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save the setting.");
    }
  }

  return (
    <AppShell containerSize="2">
      {error && (
        <Callout.Root color="red" mb="3" role="alert">
          <Callout.Text>{error}</Callout.Text>
        </Callout.Root>
      )}
      <Flex direction="column" gap="4">
        <Card>
          <Heading size="3" mb="3">
            Kiosk
          </Heading>
          <Flex asChild justify="between" align="center" gap="4">
            <label>
              <Flex direction="column" gap="1">
                <Text size="2" weight="medium">
                  Block inactive users at the kiosk
                </Text>
                <Text size="1" color="gray">
                  When on, a user marked Inactive cannot log in or check out at the kiosk (they
                  can still return items). When off, status is just an organizational label.
                </Text>
              </Flex>
              <Switch
                checked={settings?.kiosk_block_inactive_users ?? false}
                disabled={settings === null}
                onCheckedChange={(checked) => update({ kiosk_block_inactive_users: checked })}
              />
            </label>
          </Flex>
        </Card>
        <ChangePasswordCard />
      </Flex>
    </AppShell>
  );
}

function ChangePasswordCard() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    if (newPassword !== confirmPassword) {
      setError("New passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not change the password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <Heading size="3" mb="3">
        Admin password
      </Heading>
      <form onSubmit={submit}>
        <Flex direction="column" gap="3" maxWidth="360px">
          <TextField.Root
            type="password"
            placeholder="Current password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
          />
          <TextField.Root
            type="password"
            placeholder="New password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
          <TextField.Root
            type="password"
            placeholder="Confirm new password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
          {error && (
            <Callout.Root color="red">
              <Callout.Text>{error}</Callout.Text>
            </Callout.Root>
          )}
          {success && (
            <Callout.Root color="green">
              <Callout.Text>Password changed.</Callout.Text>
            </Callout.Root>
          )}
          <Button
            type="submit"
            disabled={busy || !currentPassword || !newPassword || !confirmPassword}
          >
            {busy ? "Changing…" : "Change password"}
          </Button>
        </Flex>
      </form>
    </Card>
  );
}
