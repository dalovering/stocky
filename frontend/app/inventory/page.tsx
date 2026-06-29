"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Dialog, Flex, Heading, Select, Separator, Text, TextField } from "@radix-ui/themes";

import { AppShell } from "@/components/AppShell";
import { DialogHeader } from "@/components/Dialogs";
import { GroupedTable, type GroupNode } from "@/components/GroupedTable";
import { HistoryList, StatusBadge } from "@/components/HistoryList";
import { api } from "@/lib/api";
import type { Item, ItemEvent } from "@/lib/types";

export default function InventoryPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [location, setLocation] = useState<string | null>(null);
  const [detail, setDetail] = useState<Item | null>(null);

  const load = useCallback(async () => {
    const [it, locs] = await Promise.all([
      api.inventoryItems({ q: q || undefined, location: location ?? undefined }),
      api.inventoryLocations(),
    ]);
    setItems(it);
    setLocations(locs);
  }, [q, location]);

  useEffect(() => {
    load();
  }, [load]);

  // Group items by type; the per-type availability counts in the header replace the old
  // "By type" summary view.
  const groupNodes = useMemo<GroupNode<Item>[]>(() => {
    const byType = new Map<string, { name: string; rows: Item[] }>();
    for (const i of items) {
      const g = byType.get(i.item_type_id);
      if (g) g.rows.push(i);
      else byType.set(i.item_type_id, { name: i.item_type_name ?? "—", rows: [i] });
    }
    return [...byType.entries()]
      .sort((a, b) => a[1].name.localeCompare(b[1].name))
      .map(([id, { name, rows }]) => {
        const available = rows.filter((r) => r.status === "Available").length;
        const onLoan = rows.filter((r) => r.status === "On loan").length;
        return {
          id,
          title: name,
          meta: `${rows.length} total · ${available} available · ${onLoan} on loan`,
          children: [],
          rows,
        };
      });
  }, [items]);

  return (
    <AppShell>
      <Flex mb="3" gap="3" align="center" wrap="wrap">
        <TextField.Root
          placeholder="Search items…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ minWidth: 220 }}
        />
        <Select.Root value={location ?? "all"} onValueChange={(v) => setLocation(v === "all" ? null : v)}>
          <Select.Trigger placeholder="Location" />
          <Select.Content>
            <Select.Item value="all">All locations</Select.Item>
            {locations.map((l) => (
              <Select.Item key={l} value={l}>
                {l}
              </Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Flex>

      <GroupedTable
        groups={groupNodes}
        rowKey={(i) => i.id}
        onRowClick={setDetail}
        empty="No items found."
        columns={[
          { header: "Name", cell: (i) => i.name },
          { header: "Location", cell: (i) => i.location ?? "—" },
          { header: "Condition", cell: (i) => i.condition },
          { header: "Status", cell: (i) => <StatusBadge status={i.status} /> },
        ]}
      />

      {detail && <ItemDetail item={detail} onClose={() => setDetail(null)} />}
    </AppShell>
  );
}

function ItemDetail({ item, onClose }: { item: Item; onClose: () => void }) {
  const [events, setEvents] = useState<ItemEvent[]>([]);
  useEffect(() => {
    api.inventoryItemEvents(item.id).then(setEvents);
  }, [item.id]);

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="540px">
        <DialogHeader title={item.name} />
        <Flex gap="2" align="center">
          <StatusBadge status={item.status} />
          <Text size="2" color="gray">
            {item.item_type_name} · {item.location ?? "no location"} · {item.condition}
          </Text>
        </Flex>
        {item.holder_name && (
          <Text size="2" mt="1">
            Currently with <strong>{item.holder_name}</strong>
          </Text>
        )}
        {item.description && (
          <Text size="2" mt="2" as="p">
            {item.description}
          </Text>
        )}

        <Separator my="4" size="4" />
        <Heading size="3" mb="2">
          History
        </Heading>
        <HistoryList events={events} subject="item" />
      </Dialog.Content>
    </Dialog.Root>
  );
}
