"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Flex, Select, Text, TextField } from "@radix-ui/themes";
import { DownloadIcon } from "@radix-ui/react-icons";

import { AppShell } from "@/components/AppShell";
import { DataTable, type Column } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { EventBadge, EVENT_TYPE_OPTIONS } from "@/components/HistoryList";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useUrlFilters } from "@/hooks/useUrlFilters";
import { api, ApiError, downloadBlob } from "@/lib/api";
import type { ItemEvent, Page } from "@/lib/types";

const PAGE_SIZE = 50;
const ALL = "__all__";

export default function HistoryPage() {
  const [q, setQ] = useState("");
  const [eventType, setEventType] = useState<string>(ALL);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Page<ItemEvent>>({
    items: [],
    total: 0,
    limit: PAGE_SIZE,
    offset: 0,
  });

  const debouncedQ = useDebouncedValue(q);

  const load = useCallback(async () => {
    const result = await api.adminEvents({
      q: debouncedQ || undefined,
      event_type: eventType === ALL ? undefined : eventType,
      date_from: dateFrom || undefined,
      // Make the end date inclusive of the whole day.
      date_to: dateTo ? `${dateTo}T23:59:59` : undefined,
      limit: PAGE_SIZE,
      offset,
    });
    setPage(result);
  }, [debouncedQ, eventType, dateFrom, dateTo, offset]);

  const hydrated = useUrlFilters({
    decode: (sp) => {
      const qp = sp.get("q");
      if (qp) setQ(qp);
      const et = sp.get("event_type");
      if (et) setEventType(et);
      const df = sp.get("date_from");
      if (df) setDateFrom(df);
      const dt = sp.get("date_to");
      if (dt) setDateTo(dt);
    },
    params: {
      q: q || undefined,
      event_type: eventType === ALL ? undefined : eventType,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    },
  });

  // Reset to the first page whenever a filter changes.
  useEffect(() => {
    setOffset(0);
  }, [debouncedQ, eventType, dateFrom, dateTo]);

  useEffect(() => {
    if (hydrated) load();
  }, [hydrated, load]);

  const dirty = q !== "" || eventType !== ALL || dateFrom !== "" || dateTo !== "";

  function reset() {
    setQ("");
    setEventType(ALL);
    setDateFrom("");
    setDateTo("");
  }

  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Export whatever the filters currently show — unfiltered, that's the entire history
  // (the xlsx endpoint has no pagination and no 90-day default window).
  async function download() {
    setDownloadError(null);
    try {
      const blob = await api.eventsXlsx({
        q: debouncedQ || undefined,
        event_type: eventType === ALL ? undefined : eventType,
        date_from: dateFrom || undefined,
        date_to: dateTo ? `${dateTo}T23:59:59` : undefined,
      });
      downloadBlob(blob, "stocky-history.xlsx");
    } catch (e) {
      setDownloadError(e instanceof ApiError ? e.message : "Download failed.");
    }
  }

  const columns: Column<ItemEvent>[] = [
    {
      header: "When",
      cell: (e) => (
        <Text size="1" color="gray" style={{ whiteSpace: "nowrap" }}>
          {new Date(e.created_at).toLocaleString()}
        </Text>
      ),
    },
    { header: "Action", cell: (e) => <EventBadge type={e.event_type} /> },
    { header: "Item", cell: (e) => e.item_name ?? "—" },
    { header: "User", cell: (e) => e.user_name ?? "—" },
    {
      header: "Note",
      cell: (e) => (
        <Text size="2" color="gray">
          {e.note ?? "—"}
        </Text>
      ),
    },
  ];

  const from = page.total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, page.total);

  return (
    <AppShell>
      <Flex mb="3" justify="between" align="center" wrap="wrap">
        <FilterBar
          search={{ value: q, onChange: setQ, placeholder: "Search notes, items, users…" }}
          dirty={dirty}
          onReset={reset}
        >
          <Select.Root value={eventType} onValueChange={setEventType}>
            <Select.Trigger placeholder="Action" />
            <Select.Content>
              <Select.Item value={ALL}>All actions</Select.Item>
              {EVENT_TYPE_OPTIONS.map((o) => (
                <Select.Item key={o.value} value={o.value}>
                  {o.label}
                </Select.Item>
              ))}
            </Select.Content>
          </Select.Root>
          <Flex gap="1" align="center">
            <Text size="1" color="gray">
              From
            </Text>
            <TextField.Root
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
            <Text size="1" color="gray">
              to
            </Text>
            <TextField.Root
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </Flex>
        </FilterBar>
        <Button variant="soft" color="gray" onClick={download}>
          <DownloadIcon /> .xlsx
        </Button>
      </Flex>

      {downloadError && (
        <Text size="2" color="red" mb="2" as="p">
          {downloadError}
        </Text>
      )}

      <DataTable
        rows={page.items}
        rowKey={(e) => e.id}
        columns={columns}
        empty="No events match."
      />

      <Flex mt="3" gap="3" align="center" justify="between">
        <Text size="2" color="gray">
          {page.total === 0 ? "No events" : `Showing ${from}–${to} of ${page.total}`}
        </Text>
        <Flex gap="2">
          <Button
            variant="soft"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </Button>
          <Button
            variant="soft"
            disabled={offset + PAGE_SIZE >= page.total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </Button>
        </Flex>
      </Flex>
    </AppShell>
  );
}
