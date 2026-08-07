"use client";

import { useRef, useState } from "react";
import { Badge, Box, Button, Callout, Card, Dialog, Flex, Heading, Text } from "@radix-ui/themes";
import { DownloadIcon, UploadIcon } from "@radix-ui/react-icons";

import { AppShell } from "@/components/AppShell";
import { DialogHeader } from "@/components/Dialogs";
import { api, ApiError, downloadBlob } from "@/lib/api";
import type { RestoreEntityPlan, RestorePlan, RestoreRowChange } from "@/lib/types";

const ENTITY_LABELS: Record<RestoreEntityPlan["kind"], string> = {
  groups: "Groups",
  item_types: "Item types",
  users: "Users",
  items: "Items",
};
const DETAIL_ROWS = 8; // shown per change list; counts always tell the full story

function planHasChanges(plan: RestorePlan): boolean {
  return (
    plan.entities.some((e) => e.create_count + e.update_count + e.delete_count > 0) ||
    plan.events_add + plan.events_remove + plan.events_relink > 0 ||
    plan.settings.length > 0
  );
}

function ChangeList({
  color,
  title,
  rows,
  count,
}: {
  color: "green" | "blue" | "red";
  title: string;
  rows: RestoreRowChange[];
  count: number;
}) {
  if (count === 0) return null;
  const shown = rows.slice(0, DETAIL_ROWS);
  return (
    <Box mt="1">
      <Badge color={color}>
        {title} {count}
      </Badge>
      <Box pl="3" mt="1">
        {shown.map((row) => (
          <Text as="p" size="1" key={row.id}>
            {row.label}
            {row.fields.length > 0 && (
              <Text color="gray">
                {" — "}
                {row.fields
                  .map((f) => `${f.field}: ${f.old ?? "(empty)"} → ${f.new ?? "(empty)"}`)
                  .join(", ")}
              </Text>
            )}
          </Text>
        ))}
        {count > shown.length && (
          <Text as="p" size="1" color="gray">
            …and {count - shown.length} more
          </Text>
        )}
      </Box>
    </Box>
  );
}

function EntitySection({ entity }: { entity: RestoreEntityPlan }) {
  const total = entity.create_count + entity.update_count + entity.delete_count;
  if (total === 0) return null;
  return (
    <Box mt="2">
      <Text size="2" weight="bold">
        {ENTITY_LABELS[entity.kind]}
      </Text>
      <Text size="1" color="gray">
        {" "}
        · {entity.unchanged} unchanged
      </Text>
      <ChangeList color="green" title="restore" rows={entity.creates} count={entity.create_count} />
      <ChangeList color="blue" title="revert" rows={entity.updates} count={entity.update_count} />
      <ChangeList color="red" title="remove" rows={entity.deletes} count={entity.delete_count} />
    </Box>
  );
}

export default function ExportPage() {
  const [busy, setBusy] = useState<"labels" | "database" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [backupFile, setBackupFile] = useState<File | null>(null);
  const [plan, setPlan] = useState<RestorePlan | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restored, setRestored] = useState<RestorePlan | null>(null);

  async function download(kind: "labels" | "database", blob: () => Promise<Blob>, name: string) {
    setBusy(kind);
    setError(null);
    try {
      downloadBlob(await blob(), name);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Download failed.");
    } finally {
      setBusy(null);
    }
  }

  function onBackupPicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(null);
    setRestored(null);
    setPreviewing(true);
    api
      .restorePreview(file)
      .then((preview) => {
        setBackupFile(file);
        setPlan(preview);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Preview failed."))
      .finally(() => setPreviewing(false));
  }

  async function applyRestore() {
    if (!backupFile) return;
    setRestoring(true);
    setError(null);
    try {
      const result = await api.restoreApply(backupFile);
      if (result.errors.length > 0) {
        setPlan(result); // shouldn't happen after a clean preview, but surface it
        return;
      }
      setPlan(null);
      setBackupFile(null);
      setRestored(result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Restore failed.");
    } finally {
      setRestoring(false);
    }
  }

  const changes = plan !== null && plan.errors.length === 0 && planHasChanges(plan);

  return (
    <AppShell>
      {error && (
        <Text size="2" color="red" mb="3" as="p">
          {error}
        </Text>
      )}
      {restored && (
        <Callout.Root color="green" mb="3">
          <Callout.Text>
            Backup restored — {plainSummary(restored)}. The admin password was not changed.
          </Callout.Text>
        </Callout.Root>
      )}
      <Flex direction="column" gap="4">
        <Card>
          <Heading size="3">ID cards &amp; item tags (PDF)</Heading>
          <Text as="p" size="2" color="gray" mt="1">
            A multi-up US-Letter sheet with every user ID card and every item tag, in two sections —
            handy for bulk printing or checking the templates. Print a single card or a whole
            group/type from the Users and Inventory tabs.
          </Text>
          <Button
            mt="3"
            loading={busy === "labels"}
            onClick={() => download("labels", api.labelsPdf, "stocky-cards.pdf")}
          >
            <DownloadIcon /> Download PDF
          </Button>
        </Card>
        <Card>
          <Heading size="3">Full database backup (.xlsx)</Heading>
          <Text as="p" size="2" color="gray" mt="1">
            One workbook with every table as a sheet: users, groups, item types, items, the complete
            history, and the app settings. The users and items sheets match the import format, so
            rows can be pasted into an import file. The admin password is never included. This file
            is also the restore format below — download one before risky changes.
          </Text>
          <Button
            mt="3"
            loading={busy === "database"}
            onClick={() => download("database", api.databaseXlsx, "stocky-database.xlsx")}
          >
            <DownloadIcon /> Download .xlsx
          </Button>
        </Card>
        <Card>
          <Heading size="3">Restore from backup</Heading>
          <Text as="p" size="2" color="gray" mt="1">
            Upload a database backup to roll everything back to it: users, groups, item types,
            items, history, and settings. You&apos;ll see exactly what would change before anything
            is touched. Rows added since the backup are removed, edited rows are reverted, and
            deleted rows come back — including loan history, so item statuses return to what they
            were. The admin password is not affected.
          </Text>
          <Button
            mt="3"
            color="red"
            variant="soft"
            loading={previewing}
            onClick={() => fileInput.current?.click()}
          >
            <UploadIcon /> Choose backup…
          </Button>
          <input ref={fileInput} type="file" accept=".xlsx" hidden onChange={onBackupPicked} />
        </Card>
      </Flex>

      <Dialog.Root open={plan !== null} onOpenChange={(open) => !open && setPlan(null)}>
        <Dialog.Content style={{ maxWidth: 640 }}>
          <DialogHeader title="Restore from backup" />
          {plan !== null && plan.errors.length > 0 && (
            <>
              <Callout.Root color="red" mt="2">
                <Callout.Text>
                  This file can&apos;t be restored — fix the problems below or upload an unmodified
                  backup. Nothing was changed.
                </Callout.Text>
              </Callout.Root>
              <Box mt="2" style={{ maxHeight: 320, overflowY: "auto" }}>
                {plan.errors.map((err, i) => (
                  <Text as="p" size="1" key={i}>
                    <Text weight="bold">{err.sheet}</Text>
                    {err.row !== null && ` row ${err.row}`}: {err.message}
                  </Text>
                ))}
              </Box>
            </>
          )}
          {plan !== null && plan.errors.length === 0 && (
            <>
              {!changes ? (
                <Text as="p" size="2" mt="2">
                  This backup already matches the current database — there is nothing to change.
                </Text>
              ) : (
                <>
                  <Text as="p" size="2" mt="2">
                    Applying this backup will make the changes below.{" "}
                    <Text weight="bold">This cannot be undone</Text> — consider downloading a fresh
                    backup first.
                  </Text>
                  <Box mt="2" style={{ maxHeight: 380, overflowY: "auto" }}>
                    {plan.entities.map((entity) => (
                      <EntitySection key={entity.kind} entity={entity} />
                    ))}
                    {plan.events_add + plan.events_remove + plan.events_relink > 0 && (
                      <Box mt="2">
                        <Text size="2" weight="bold">
                          History
                        </Text>
                        <Text as="p" size="1" color="gray">
                          {plan.events_add} events restored · {plan.events_remove} newer events
                          removed · {plan.events_relink} corrected · {plan.events_unchanged}{" "}
                          unchanged. Item statuses and current loans follow the restored history.
                        </Text>
                      </Box>
                    )}
                    {plan.settings.length > 0 && (
                      <Box mt="2">
                        <Text size="2" weight="bold">
                          Settings
                        </Text>
                        {plan.settings.map((s) => (
                          <Text as="p" size="1" key={s.key}>
                            {s.key}: {s.old || "(unset)"} → {s.new || "(unset)"}
                          </Text>
                        ))}
                      </Box>
                    )}
                  </Box>
                </>
              )}
              <Flex gap="3" mt="4" justify="end">
                <Button variant="soft" color="gray" onClick={() => setPlan(null)}>
                  Cancel
                </Button>
                <Button color="red" disabled={!changes} loading={restoring} onClick={applyRestore}>
                  Restore database
                </Button>
              </Flex>
            </>
          )}
        </Dialog.Content>
      </Dialog.Root>
    </AppShell>
  );
}

function plainSummary(plan: RestorePlan): string {
  const created = plan.entities.reduce((n, e) => n + e.create_count, 0);
  const updated = plan.entities.reduce((n, e) => n + e.update_count, 0);
  const deleted = plan.entities.reduce((n, e) => n + e.delete_count, 0);
  const parts = [
    `${created} rows restored`,
    `${updated} reverted`,
    `${deleted} removed`,
    `${plan.events_add + plan.events_relink} history events restored`,
    `${plan.settings.length} settings changed`,
  ];
  return parts.join(", ");
}
