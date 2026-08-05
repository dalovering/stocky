"use client";

import { useState } from "react";
import { Button, Card, Heading, Text } from "@radix-ui/themes";
import { DownloadIcon } from "@radix-ui/react-icons";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";

export default function ExportPage() {
  const [printing, setPrinting] = useState(false);

  // Download the multi-up card sheet (every user ID card + every item tag) as a printable PDF.
  async function downloadLabels() {
    setPrinting(true);
    try {
      const blob = await api.labelsPdf();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "stocky-cards.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setPrinting(false);
    }
  }

  return (
    <AppShell>
      <Card>
        <Heading size="3">ID cards &amp; item tags (PDF)</Heading>
        <Text as="p" size="2" color="gray" mt="1">
          A multi-up US-Letter sheet with every user ID card and every item tag, in two sections —
          handy for bulk printing or checking the templates. Print a single card or a whole
          group/type from the Users and Inventory tabs.
        </Text>
        <Button mt="3" onClick={downloadLabels} loading={printing}>
          <DownloadIcon /> Download PDF
        </Button>
      </Card>
    </AppShell>
  );
}
