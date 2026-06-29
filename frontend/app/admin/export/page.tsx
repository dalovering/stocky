"use client";

import { useState } from "react";
import { Button, Card, Heading, Text } from "@radix-ui/themes";
import { DownloadIcon } from "@radix-ui/react-icons";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";

export default function ExportPage() {
  const [printing, setPrinting] = useState(false);

  // Download the barcode-label sheet (every user + item) as a PDF the admin can print.
  async function downloadLabels() {
    setPrinting(true);
    try {
      const blob = await api.labelsPdf();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "stocky-barcode-labels.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setPrinting(false);
    }
  }

  return (
    <AppShell title="Export data">
      <Card>
        <Heading size="3">Barcode labels (PDF)</Heading>
        <Text as="p" size="2" color="gray" mt="1">
          One PDF with every user ID-card barcode and every item tag, in two sections — print the
          whole set in one go.
        </Text>
        <Button mt="3" onClick={downloadLabels} loading={printing}>
          <DownloadIcon /> Download PDF
        </Button>
      </Card>
    </AppShell>
  );
}
