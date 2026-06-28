"use client";

// Listens for barcode scans anywhere on the page (no focused input required) and invokes
// a callback with the decoded value. Uses the pure state machine in lib/scanner.ts.

import { useEffect, useRef } from "react";

import { EMPTY_SCAN_STATE, feedKey, isEditableTarget, type ScanState } from "@/lib/scanner";

interface Props {
  onScan: (code: string) => void;
  /** If true, ignore keystrokes while an input/textarea/select is focused. Default true. */
  ignoreWhenEditing?: boolean;
  enabled?: boolean;
}

export function BarcodeScannerProvider({
  onScan,
  ignoreWhenEditing = true,
  enabled = true,
}: Props) {
  const stateRef = useRef<ScanState>(EMPTY_SCAN_STATE);
  // Keep the latest callback without re-binding the listener.
  const onScanRef = useRef(onScan);
  useEffect(() => {
    onScanRef.current = onScan;
  });

  useEffect(() => {
    if (!enabled) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (ignoreWhenEditing && isEditableTarget(e.target)) return;

      // Only single printable characters and Enter are meaningful to a scanner.
      const key = e.key === "Enter" ? "Enter" : e.key.length === 1 ? e.key : null;
      if (key === null) return;

      const now = typeof performance !== "undefined" ? performance.now() : Date.now();
      const { state, scanned } = feedKey(stateRef.current, key, now);
      stateRef.current = state;

      if (scanned !== null) {
        // Prevent the Enter from also submitting anything in the background.
        e.preventDefault();
        onScanRef.current(scanned);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled, ignoreWhenEditing]);

  return null;
}
