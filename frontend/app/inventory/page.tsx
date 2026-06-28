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
  IconButton,
  SegmentedControl,
  Select,
  Separator,
  Text,
  TextField,
} from "@radix-ui/themes";
import { Cross2Icon } from "@radix-ui/react-icons";

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
        <Card>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left" }}>
                <Th>Item type</Th>
                <Th>Location</Th>
                <Th>Total</Th>
                <Th>Available</Th>
                <Th>On loan</Th>
              </tr>
            </thead>
            <tbody>
              {summary.map((r, idx) => (
                <tr key={idx} style={{ borderTop: "1px solid var(--gray-4)" }}>
                  <Td>{r.item_type_name}</Td>
                  <Td>{r.location ?? "—"}</Td>
                  <Td>{r.total}</Td>
                  <Td>
                    <Text color="green">{r.available}</Text>
                  </Td>
                  <Td>
                    <Text color="blue">{r.on_loan}</Text>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
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
        <Flex justify="between" align="start">
          <Dialog.Title>{item.name}</Dialog.Title>
          <Dialog.Close>
            <IconButton variant="ghost" color="gray">
              <Cross2Icon />
            </IconButton>
          </Dialog.Close>
        </Flex>
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

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th style={{ padding: "8px 12px" }}>
      <Text size="1" color="gray" weight="medium">
        {children}
      </Text>
    </th>
  );
}

function Td({ children }: { children: React.ReactNode }) {
  return (
    <td style={{ padding: "8px 12px" }}>
      <Text size="2">{children}</Text>
    </td>
  );
}
