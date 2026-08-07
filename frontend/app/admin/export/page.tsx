"use client";

import { useState } from "react";
import { Button, Card, Flex, Heading, Text } from "@radix-ui/themes";
import { DownloadIcon } from "@radix-ui/react-icons";

import { AppShell } from "@/components/AppShell";
import { api, ApiError, downloadBlob } from "@/lib/api";

export default function ExportPage() {
  const [busy, setBusy] = useState<"labels" | "database" | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <AppShell>
      {error && (
        <Text size="2" color="red" mb="3" as="p">
          {error}
        </Text>
      )}
      <Flex direction="column" gap="4">
        <Card>
          <Heading size="3">ID cards &amp; item tags (PDF)</Heading>
          <Text as="p" size="2" color="gray" mt="1">
            A multi-up US-Letter sheet with every user ID card and every item tag, in two sections
            — handy for bulk printing or checking the templates. Print a single card or a whole
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
          <Heading size="3">Full database export (.xlsx)</Heading>
          <Text as="p" size="2" color="gray" mt="1">
            One workbook with every table as a sheet: users, groups, item types, items, the
            complete history, and the app settings. The users and items sheets match the import
            format, so rows can be pasted into an import file. The admin password is never
            included.
          </Text>
          <Button
            mt="3"
            loading={busy === "database"}
            onClick={() => download("database", api.databaseXlsx, "stocky-database.xlsx")}
          >
            <DownloadIcon /> Download .xlsx
          </Button>
        </Card>
      </Flex>
    </AppShell>
  );
}
