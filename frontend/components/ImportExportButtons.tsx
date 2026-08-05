"use client";

import { useRef } from "react";
import { Button } from "@radix-ui/themes";
import { DownloadIcon, UploadIcon } from "@radix-ui/react-icons";

import { ApiError, downloadBlob } from "@/lib/api";
import type { ImportResult } from "@/lib/types";

/**
 * The "Download .xlsx" + "Import" button pair (with a hidden file input) shared by the users and
 * inventory toolbars. Handles the download, the file pick, and error reporting; the page supplies
 * the entity-specific export/import calls and reacts to the result.
 */
export function ImportExportButtons({
  exportName,
  onExport,
  onImport,
  onImported,
  onError,
}: {
  exportName: string;
  onExport: () => Promise<Blob>;
  onImport: (file: File) => Promise<ImportResult>;
  onImported: (result: ImportResult) => void;
  onError: (message: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);

  async function doExport() {
    try {
      downloadBlob(await onExport(), exportName);
    } catch (e) {
      onError(e instanceof ApiError ? e.message : "Download failed.");
    }
  }

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    onImport(file)
      .then(onImported)
      .catch((err) => onError(err instanceof ApiError ? err.message : "Import failed."));
  }

  return (
    <>
      <Button variant="soft" color="gray" onClick={doExport}>
        <DownloadIcon /> .xlsx
      </Button>
      <Button variant="soft" color="gray" onClick={() => input.current?.click()}>
        <UploadIcon /> Import
      </Button>
      <input ref={input} type="file" accept=".xlsx" hidden onChange={onFile} />
    </>
  );
}
