"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { PrinterInfo } from "@/lib/types";

/**
 * Label-printer availability for the admin pages. Fetches the cheap non-probing
 * GET /api/admin/printer once on mount; `available` gates every "Print to label
 * printer" affordance, so pages render exactly the pre-printer UI when it's false.
 */
export function usePrinter() {
  const [info, setInfo] = useState<PrinterInfo | null>(null);

  const refresh = useCallback(async (probe = false) => {
    try {
      const next = await api.printerInfo(probe);
      setInfo(next);
      return next;
    } catch {
      setInfo(null); // treat an unreadable printer endpoint as "no printer"
      return null;
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { info, available: Boolean(info?.configured && info?.enabled), refresh };
}
