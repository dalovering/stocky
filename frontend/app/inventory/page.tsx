"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Card,
  Container,
  Dialog,
  Flex,
  Grid,
  Heading,
  SegmentedControl,
  Select,
  Separator,
  Text,
  TextField,
} from "@radix-ui/themes";

import { DataTable } from "@/components/DataTable";
import { DialogHeader } from "@/components/Dialogs";
import { HistoryList, StatusBadge } from "@/components/HistoryList";
import { api } from "@/lib/api";
import type { InventorySummaryRow, Item, ItemEvent } from "@/lib/types";

export default function InventoryPage() {
  const [view, setView] = useState<"items" | "summary">("items");
  const [items, setItems] = useState<Item[]>([]);
  const [summary, setSummary] = useState<InventorySummaryRow[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [location, setLocation] = useState<string | null>(null);
  const [detail, setDetail] = useState<Item | null>(null);

  const load = useCallback(async () => {
    const [it, sum, locs] = await Promise.all([
      api.inventoryItems({ q: q || undefined, location: location ?? undefined }),
      api.inventorySummary(),
      api.inventoryLocations(),
    ]);
    setItems(it);
    setSummary(sum);
    setLocations(locs);
  }, [q, location]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Container size="4" p="5">
      <Flex justify="between" align="center" mb="4">
        <Heading size="7">Inventory</Heading>
        <Link href="/">
          <Button variant="ghost" color="gray">
            Home
          </Button>
        </Link>
      </Flex>

      <Flex justify="between" align="center" mb="3" gap="3" wrap="wrap">
        <Flex gap="3" align="center" wrap="wrap">
          <TextField.Root
            placeholder="Search items…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ minWidth: 220 }}
          />
          <Select.Root
            value={location ?? "all"}
            onValueChange={(v) => setLocation(v === "all" ? null : v)}
          >
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
        <SegmentedControl.Root
          value={view}
          onValueChange={(v) => setView(v as "items" | "summary")}
        >
          <SegmentedControl.Item value="items">Items</SegmentedControl.Item>
          <SegmentedControl.Item value="summary">By type</SegmentedControl.Item>
        </SegmentedControl.Root>
      </Flex>

      {view === "items" ? (
        <Grid columns={{ initial: "1", sm: "2", lg: "3" }} gap="3">
          {items.map((i) => (
            <Card
              key={i.id}
              className="clickable"
              onDoubleClick={() => setDetail(i)}
              onClick={() => setDetail(i)}
            >
              <Flex justify="between" align="start">
                <Box>
                  <Heading size="3">{i.name}</Heading>
                  <Text size="2" color="gray">
                    {i.item_type_name}
                  </Text>
                </Box>
                <StatusBadge status={i.status} />
              </Flex>
              <Flex mt="2" justify="between">
                <Text size="2" color="gray">
                  {i.location ?? "—"}
                </Text>
                <Badge variant="soft" color="gray">
                  {i.condition}
                </Badge>
              </Flex>
            </Card>
          ))}
          {items.length === 0 && <Text color="gray">No items found.</Text>}
        </Grid>
      ) : (
        <DataTable
          rows={summary}
          rowKey={(_, idx) => idx}
          empty="No items found."
          columns={[
            { header: "Item type", cell: (r) => r.item_type_name },
            { header: "Location", cell: (r) => r.location ?? "—" },
            { header: "Total", cell: (r) => r.total },
            { header: "Available", cell: (r) => <Text color="green">{r.available}</Text> },
            { header: "On loan", cell: (r) => <Text color="blue">{r.on_loan}</Text> },
          ]}
        />
      )}

      {detail && <ItemDetail item={detail} onClose={() => setDetail(null)} />}
    </Container>
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
        <HistoryList events={events} />
      </Dialog.Content>
    </Dialog.Root>
  );
}
