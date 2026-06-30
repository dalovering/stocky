"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Two-way sync between a page's filter state and the URL query string, so filters survive a reload
 * and links are shareable. Client-only and uses `history.replaceState` (no navigation, no re-render,
 * no history spam). `decode` runs once on mount to seed state from the URL (it calls the page's own
 * setters); `params` is the current state, serialized back to the URL whenever it changes.
 *
 * Returns `hydrated` — false until the URL has been read. Gate the initial data fetch on it so the
 * page fetches once with the URL's filters, not twice (defaults, then URL).
 */
export function useUrlFilters({
  decode,
  params,
}: {
  decode: (sp: URLSearchParams) => void;
  params: Record<string, string | readonly string[] | undefined>;
}): boolean {
  const [hydrated, setHydrated] = useState(false);
  const decodeRef = useRef(decode);
  useEffect(() => {
    decodeRef.current = decode;
  });

  // Seed state from the URL once, on mount.
  useEffect(() => {
    decodeRef.current(new URLSearchParams(window.location.search));
    setHydrated(true);
  }, []);

  // Mirror state into the URL whenever it changes (after the initial seed).
  const serialized = serializeParams(params);
  useEffect(() => {
    if (!hydrated) return;
    const url = serialized ? `${window.location.pathname}?${serialized}` : window.location.pathname;
    window.history.replaceState(null, "", url);
  }, [hydrated, serialized]);

  return hydrated;
}

function serializeParams(params: Record<string, string | readonly string[] | undefined>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    if (value == null) continue;
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item) parts.push(`${key}=${encodeURIComponent(item)}`);
    }
  }
  return parts.join("&");
}
