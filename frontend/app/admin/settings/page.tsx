"use client";

import { useEffect, useState } from "react";
import {
  Badge,
  Button,
  Callout,
  Card,
  Code,
  Flex,
  Heading,
  Select,
  Switch,
  Text,
  TextField,
} from "@radix-ui/themes";
import { CheckIcon, CopyIcon } from "@radix-ui/react-icons";

import { AppShell } from "@/components/AppShell";
import { usePrinter } from "@/hooks/usePrinter";
import { api, ApiError } from "@/lib/api";
import { fetchMainHead, fetchTags, type GitHubBranchHead, type GitHubTag } from "@/lib/github";
import type { AppSettings, PrinterState, VersionInfo } from "@/lib/types";

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
        <LabelPrinterCard settings={settings} onUpdate={update} />
        <SoftwareUpdateCard />
        <ChangePasswordCard />
      </Flex>
    </AppShell>
  );
}

const PRINTER_STATE_COLORS: Record<PrinterState, "green" | "red" | "orange" | "gray"> = {
  Ready: "green",
  Connected: "green", // prints fine; just can't report paper/lid status

  "Not configured": "gray",
  "Not checked": "gray",
  Unreachable: "red",
  "Out of paper": "orange",
  "Lid open": "orange",
  Busy: "orange",
  Error: "red",
};

function LabelPrinterCard({
  settings,
  onUpdate,
}: {
  settings: AppSettings | null;
  onUpdate: (patch: Partial<AppSettings>) => void;
}) {
  const { info, refresh } = usePrinter();
  const [checking, setChecking] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  async function check() {
    setChecking(true);
    try {
      await refresh(true); // live status probe (device I/O)
    } finally {
      setChecking(false);
    }
  }

  async function testPrint() {
    setTestResult(null);
    try {
      const r = await api.printerTestPrint();
      const warnings = r.warnings.length ? ` ${r.warnings.join(" ")}` : "";
      setTestResult({ ok: true, message: `Printed a test label.${warnings}` });
    } catch (e) {
      setTestResult({
        ok: false,
        message: e instanceof ApiError ? e.message : "Test print failed.",
      });
    }
  }

  const probed = info?.state !== "Not checked" && info?.state !== "Not configured";

  return (
    <Card>
      <Heading size="3" mb="3">
        Label printer
      </Heading>
      <Flex direction="column" gap="4">
        <Flex justify="between" align="center" gap="4">
          <Flex direction="column" gap="1">
            <Flex gap="2" align="center">
              <Badge color={info ? PRINTER_STATE_COLORS[info.state] : "gray"}>
                {info?.state ?? "…"}
              </Badge>
              <Text size="2" color="gray">
                {info?.configured
                  ? `${info.device} (${info.transport})`
                  : "No printer device configured"}
              </Text>
            </Flex>
            {info?.message && (
              <Text size="1" color="gray">
                {info.message}
              </Text>
            )}
            {probed && info && (info.roll_width_mm || info.battery_percent != null) && (
              <Text size="1" color="gray">
                {info.roll_width_mm
                  ? `Roll from size tag: ${info.roll_width_mm} × ${info.roll_length_mm} mm`
                  : "Roll size tag unreadable"}
                {info.battery_percent != null && ` · Battery ${info.battery_percent}%`}
              </Text>
            )}
          </Flex>
          <Flex gap="2" flexShrink="0">
            <Button
              size="1"
              variant="soft"
              disabled={!info?.configured || checking}
              onClick={check}
            >
              {checking ? "Checking…" : "Check printer"}
            </Button>
            <Button size="1" variant="soft" disabled={!info?.configured} onClick={testPrint}>
              Print test label
            </Button>
          </Flex>
        </Flex>
        {testResult && (
          <Text size="1" color={testResult.ok ? "gray" : "red"}>
            {testResult.message}
          </Text>
        )}

        <Flex asChild justify="between" align="center" gap="4">
          <label>
            <Flex direction="column" gap="1">
              <Text size="2" weight="medium">
                Enable label printing
              </Text>
              <Text size="1" color="gray">
                Adds “Print to label printer” to the print buttons on the Users and Inventory tabs.
                The printer device itself is set with PRINTER_DEVICE in .env.
              </Text>
            </Flex>
            <Switch
              checked={settings?.printer_enabled ?? false}
              disabled={settings === null || !info?.configured}
              onCheckedChange={(checked) => onUpdate({ printer_enabled: checked })}
            />
          </label>
        </Flex>

        <NumberSettingField
          label="Label width (mm)"
          help="Width of the loaded roll. The print head covers at most 48 mm. Stocky barcodes need at least 40 mm."
          min={20}
          max={54}
          value={settings?.label_width_mm ?? null}
          onSave={(v) => onUpdate({ label_width_mm: v })}
        />
        <NumberSettingField
          label="Label height (mm)"
          help="Height of one die-cut label on the roll."
          min={10}
          max={200}
          value={settings?.label_height_mm ?? null}
          onSave={(v) => onUpdate({ label_height_mm: v })}
        />
        <NumberSettingField
          label="Label gap (mm)"
          help="Gap between labels on the roll — the printer's sensor uses it to find each label's edge, so measure it if labels drift or misalign. Nelko rolls are 6 mm."
          min={0}
          max={20}
          value={settings?.label_gap_mm ?? null}
          onSave={(v) => onUpdate({ label_gap_mm: v })}
        />
        <NumberSettingField
          label="Print darkness (0–15)"
          help="TSPL density, sent with every job. PM220 firmware ignores it (darkness is fixed; SPEED only changes feed rate) — kept for TSPL printers that honor it."
          min={0}
          max={15}
          value={settings?.label_density ?? null}
          onSave={(v) => onUpdate({ label_density: v })}
        />
      </Flex>
    </Card>
  );
}

function SoftwareUpdateCard() {
  const [version, setVersion] = useState<VersionInfo | null>(null);
  const [mainHead, setMainHead] = useState<GitHubBranchHead | null>(null);
  const [tags, setTags] = useState<GitHubTag[] | null>(null);
  const [githubDown, setGithubDown] = useState(false);
  const [target, setTarget] = useState<string>("main");
  const [pasted, setPasted] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.version().then(setVersion);
    Promise.all([fetchMainHead(), fetchTags()]).then(([head, tagList]) => {
      setMainHead(head);
      setTags(tagList);
      setGithubDown(head === null && tagList === null);
    });
  }, []);

  const ref = target === "__custom__" ? pasted.trim() : target;
  const upToDate = version !== null && mainHead !== null && mainHead.sha.startsWith(version.commit);
  const commands = `make backup\nmake update REF=${ref || "<ref>"}`;

  async function copy() {
    await navigator.clipboard.writeText(commands);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Card>
      <Heading size="3" mb="3">
        Software update
      </Heading>
      <Flex direction="column" gap="3">
        <Flex align="center" gap="2">
          <Text size="2">
            Running version: <Code>{version ? `${version.version} (${version.commit})` : "…"}</Code>
          </Text>
          {version && mainHead && (
            <Badge color={upToDate ? "green" : "amber"}>
              {upToDate ? "Up to date with main" : "Update available"}
            </Badge>
          )}
        </Flex>

        {githubDown ? (
          <Text size="1" color="gray">
            Couldn&apos;t reach GitHub to list update targets — you can still update manually with
            the commands below (e.g. <Code>REF=main</Code>).
          </Text>
        ) : (
          <Flex align="center" gap="2" wrap="wrap">
            <Text size="2">Update to:</Text>
            <Select.Root value={target} onValueChange={setTarget}>
              <Select.Trigger />
              <Select.Content>
                <Select.Item value="main">
                  main
                  {mainHead
                    ? ` (${mainHead.sha}${mainHead.date ? `, ${mainHead.date.slice(0, 10)}` : ""})`
                    : ""}
                </Select.Item>
                {(tags ?? []).map((t) => (
                  <Select.Item key={t.name} value={t.name}>
                    {t.name} ({t.sha})
                  </Select.Item>
                ))}
                <Select.Item value="__custom__">A specific commit…</Select.Item>
              </Select.Content>
            </Select.Root>
            {target === "__custom__" && (
              <TextField.Root
                placeholder="Paste a commit hash"
                value={pasted}
                onChange={(e) => setPasted(e.target.value)}
                style={{ width: 220 }}
              />
            )}
          </Flex>
        )}

        <Text size="1" color="gray">
          Stocky can&apos;t update itself — run these in the repo on the host (e.g. over SSH).
          Containers are rebuilt and database migrations apply automatically on start; always back
          up first.
        </Text>
        <Flex align="center" gap="2">
          <Code size="2" style={{ whiteSpace: "pre", display: "block", padding: "8px 12px" }}>
            {commands}
          </Code>
          <Button size="1" variant="soft" color="gray" onClick={copy}>
            {copied ? <CheckIcon /> : <CopyIcon />} {copied ? "Copied" : "Copy"}
          </Button>
        </Flex>
      </Flex>
    </Card>
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
