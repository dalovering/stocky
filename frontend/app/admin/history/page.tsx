"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Flex, Select, Text, TextField } from "@radix-ui/themes";

import { AppShell } from "@/components/AppShell";
import { DataTable, type Column } from "@/components/DataTable";
import { EventBadge, EVENT_TYPE_OPTIONS } from "@/components/HistoryList";
import { api } from "@/lib/api";
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

  const load = useCallback(async () => {
    const result = await api.adminEvents({
      q: q || undefined,
      event_type: eventType === ALL ? undefined : eventType,
      date_from: dateFrom || undefined,
      // Make the end date inclusive of the whole day.
      date_to: dateTo ? `${dateTo}T23:59:59` : undefined,
      limit: PAGE_SIZE,
      offset,
    });
    setPage(result);
  }, [q, eventType, dateFrom, dateTo, offset]);

  // Reset to the first page whenever a filter changes.
  useEffect(() => {
    setOffset(0);
  }, [q, eventType, dateFrom, dateTo]);

  useEffect(() => {
    load();
  }, [load]);

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
      <Flex mb="3" gap="3" align="center" wrap="wrap">
        <TextField.Root
          placeholder="Search notes, items, users…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ minWidth: 240 }}
        />
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
          <TextField.Root type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </Flex>
      </Flex>

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
