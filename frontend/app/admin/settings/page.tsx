"use client";

import { useEffect, useState } from "react";
import { Callout, Card, Flex, Heading, Switch, Text } from "@radix-ui/themes";

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
                When on, a user marked Inactive cannot log in or check out at the kiosk (they can
                still return items). When off, status is just an organizational label.
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
    </AppShell>
  );
}
