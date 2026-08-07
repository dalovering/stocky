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
          <Flex direction="column" gap="4">
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
            <NumberSettingField
              label="Kiosk auto-logout (seconds)"
              help="Log the scanned-in user out after this much inactivity at the kiosk. 0 disables it."
              min={0}
              max={3600}
              value={settings?.kiosk_idle_timeout_seconds ?? null}
              onSave={(v) => update({ kiosk_idle_timeout_seconds: v })}
            />
          </Flex>
        </Card>
        <Card>
          <Heading size="3" mb="3">
            Admin session
          </Heading>
          <NumberSettingField
            label="Admin auto-logout (minutes)"
            help="Sign the admin out after this much inactivity, on any page. 0 disables it.
                  Sessions still expire 8 hours after login regardless (JWT_EXPIRE_MINUTES)."
            min={0}
            max={480}
            value={settings?.admin_idle_timeout_minutes ?? null}
            onSave={(v) => update({ admin_idle_timeout_minutes: v })}
          />
        </Card>
        <TimezoneCard settings={settings} onSaved={setSettings} />
        <ChangePasswordCard />
      </Flex>
    </AppShell>
  );
}

/** A labelled numeric setting with an explicit Save button (numbers shouldn't PATCH per keystroke). */
function NumberSettingField({
  label,
  help,
  min,
  max,
  value,
  onSave,
}: {
  label: string;
  help: string;
  min: number;
  max: number;
  value: number | null; // null while settings are loading
  onSave: (v: number) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null); // null = mirror the saved value
  const shown = draft ?? (value != null ? String(value) : "");
  const parsed = Number(shown);
  const valid = shown !== "" && Number.isInteger(parsed) && parsed >= min && parsed <= max;
  const dirty = draft !== null && value !== null && parsed !== value;

  return (
    <Flex justify="between" align="center" gap="4">
      <Flex direction="column" gap="1">
        <Text size="2" weight="medium">
          {label}
        </Text>
        <Text size="1" color="gray">
          {help}
        </Text>
      </Flex>
      <Flex gap="2" align="center" flexShrink="0">
        <TextField.Root
          type="number"
          min={min}
          max={max}
          value={shown}
          disabled={value === null}
          onChange={(e) => setDraft(e.target.value)}
          style={{ width: 90 }}
        />
        <Button
          size="1"
          disabled={!dirty || !valid}
          onClick={() => {
            onSave(parsed);
            setDraft(null);
          }}
        >
          Save
        </Button>
      </Flex>
    </Flex>
  );
}

function TimezoneCard({
  settings,
  onSaved,
}: {
  settings: AppSettings | null;
  onSaved: (s: AppSettings) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const shown = draft ?? settings?.timezone ?? "";
  const dirty = draft !== null && settings !== null && draft.trim() !== settings.timezone;

  async function save() {
    setError(null);
    try {
      onSaved(await api.updateSettings({ timezone: shown.trim() }));
      setDraft(null);
    } catch (e) {
      // A 422 here means the zone name wasn't recognized — say so instead of dumping
      // FastAPI's structured validation detail.
      setError(
        e instanceof ApiError && e.status === 422
          ? "Not a valid IANA time zone name (e.g. America/New_York)."
          : "Could not save the time zone.",
      );
    }
  }

  return (
    <Card>
      <Heading size="3" mb="3">
        Time zone
      </Heading>
      <Flex direction="column" gap="2">
        <Text size="1" color="gray">
          IANA zone name used wherever Stocky needs a local calendar day or local timestamps —
          attendance tracking and spreadsheet exports. Example: America/New_York.
        </Text>
        <Flex gap="2" align="center">
          <TextField.Root
            value={shown}
            disabled={settings === null}
            onChange={(e) => setDraft(e.target.value)}
            style={{ width: 240 }}
          />
          <Button size="1" disabled={!dirty || shown.trim() === ""} onClick={save}>
            Save
          </Button>
        </Flex>
        {error && (
          <Callout.Root color="red">
            <Callout.Text>{error}</Callout.Text>
          </Callout.Root>
        )}
      </Flex>
    </Card>
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
