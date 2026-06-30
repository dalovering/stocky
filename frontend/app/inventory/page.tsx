"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Dialog, Flex, Heading, Separator, Text } from "@radix-ui/themes";

import { AppShell } from "@/components/AppShell";
import { DialogHeader } from "@/components/Dialogs";
import { FilterBar } from "@/components/FilterBar";
import { GroupedTable, type GroupNode } from "@/components/GroupedTable";
import { HistoryList, StatusBadge } from "@/components/HistoryList";
import { MultiSelectFilter } from "@/components/MultiSelectFilter";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useUrlFilters } from "@/hooks/useUrlFilters";
import { api } from "@/lib/api";
import {
  ACTIVE_ITEM_STATUSES,
  CONDITIONS,
  ITEM_STATUSES,
  type Condition,
  type Item,
  type ItemEvent,
  type ItemStatus,
} from "@/lib/types";

const NO_LOCATION = "__none__";

function setsEqual<T>(set: Set<T>, values: readonly T[]): boolean {
  return set.size === values.length && values.every((v) => set.has(v));
}

export default function InventoryPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [detail, setDetail] = useState<Item | null>(null);

  // Server-side filters (synced to the URL). Defaults hide Lost/Discarded items from the browse view.
  const [q, setQ] = useState("");
  const [statusSel, setStatusSel] = useState<Set<ItemStatus>>(() => new Set(ACTIVE_ITEM_STATUSES));
  const [conditionSel, setConditionSel] = useState<Set<Condition>>(() => new Set(CONDITIONS));
  const [locationSel, setLocationSel] = useState<Set<string>>(() => new Set());

  const debouncedQ = useDebouncedValue(q);

  const loadLocations = useCallback(async () => {
    setLocations(await api.inventoryLocations());
  }, []);

  const loadItems = useCallback(async () => {
    if (statusSel.size === 0 || conditionSel.size === 0) {
      setItems([]);
      return;
    }
    setItems(
      await api.inventoryItems({
        q: debouncedQ || undefined,
        status: [...statusSel],
        condition: [...conditionSel],
        location: locationSel.size ? [...locationSel] : undefined,
      }),
    );
  }, [debouncedQ, statusSel, conditionSel, locationSel]);

  const hydrated = useUrlFilters({
    decode: (sp) => {
      const qp = sp.get("q");
      if (qp) setQ(qp);
      const st = sp.getAll("status");
      if (st.length) setStatusSel(new Set(st as ItemStatus[]));
      const co = sp.getAll("condition");
      if (co.length) setConditionSel(new Set(co as Condition[]));
      const lo = sp.getAll("location");
      if (lo.length) setLocationSel(new Set(lo));
    },
    params: {
      q: q || undefined,
      status: setsEqual(statusSel, ACTIVE_ITEM_STATUSES) ? undefined : [...statusSel],
      condition: setsEqual(conditionSel, CONDITIONS) ? undefined : [...conditionSel],
      location: [...locationSel],
    },
  });

  useEffect(() => {
    loadLocations();
  }, [loadLocations]);
  useEffect(() => {
    if (hydrated) loadItems();
  }, [hydrated, loadItems]);

  const dirty =
    q.trim() !== "" ||
    !setsEqual(statusSel, ACTIVE_ITEM_STATUSES) ||
    !setsEqual(conditionSel, CONDITIONS) ||
    locationSel.size > 0;

  function reset() {
    setQ("");
    setStatusSel(new Set(ACTIVE_ITEM_STATUSES));
    setConditionSel(new Set(CONDITIONS));
    setLocationSel(new Set());
  }

  const locationOptions = useMemo(() => [NO_LOCATION, ...locations], [locations]);

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
        const onLoan = rows.filter((r) => r.status === "Checked out").length;
        return {
          id,
          title: name,
          meta: `${rows.length} total · ${available} available · ${onLoan} out`,
          children: [],
          rows,
        };
      });
  }, [items]);

  return (
    <AppShell>
      <Flex mb="3" justify="between" align="center" wrap="wrap">
        <FilterBar
          search={{ value: q, onChange: setQ, placeholder: "Search items…" }}
          dirty={dirty}
          onReset={reset}
          shown={items.length}
          noun="item"
        >
          <MultiSelectFilter
            label="Status"
            options={ITEM_STATUSES}
            selected={statusSel}
            onChange={setStatusSel}
          />
          <MultiSelectFilter
            label="Condition"
            options={CONDITIONS}
            selected={conditionSel}
            onChange={setConditionSel}
          />
          <MultiSelectFilter
            label="Location"
            options={locationOptions}
            selected={locationSel}
            onChange={setLocationSel}
            emptyMeansAll
            renderOption={(loc) => (loc === NO_LOCATION ? "(No location)" : loc)}
          />
        </FilterBar>
      </Flex>

      <GroupedTable
        groups={groupNodes}
        rowKey={(i) => i.id}
        onRowClick={setDetail}
        empty="No items match your filters."
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
