"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Card,
  Dialog,
  Flex,
  Grid,
  Heading,
  IconButton,
  SegmentedControl,
  Select,
  Separator,
  Text,
  TextArea,
  TextField,
} from "@radix-ui/themes";
import { Cross2Icon, PlusIcon } from "@radix-ui/react-icons";

import { BarcodeLabelDialog } from "@/components/BarcodeLabelDialog";
import { HistoryList, StatusBadge } from "@/components/HistoryList";
import { PassiveSelect } from "@/components/PassiveSelect";
import { api } from "@/lib/api";
import type { Item, ItemEvent, ItemType } from "@/lib/types";

const ADD_NEW_TYPE = "__add_new_type__";

export default function InventoryAdminPage() {
  const [tab, setTab] = useState<"items" | "types">("items");
  const [types, setTypes] = useState<ItemType[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [manufacturers, setManufacturers] = useState<string[]>([]);
  const [q, setQ] = useState("");

  const [editType, setEditType] = useState<Partial<ItemType> | null>(null);
  const [editItem, setEditItem] = useState<Partial<Item> | null>(null);
  const [detailItem, setDetailItem] = useState<Item | null>(null);

  const loadAll = useCallback(async () => {
    const [t, l, m] = await Promise.all([api.itemTypes(), api.locations(), api.manufacturers()]);
    setTypes(t);
    setLocations(l);
    setManufacturers(m);
  }, []);

  const loadItems = useCallback(async () => {
    setItems(await api.adminItems({ q: q || undefined }));
  }, [q]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);
  useEffect(() => {
    loadItems();
  }, [loadItems]);

  return (
    <Box>
      <Flex justify="between" align="center" mb="4" gap="3" wrap="wrap">
        <SegmentedControl.Root value={tab} onValueChange={(v) => setTab(v as "items" | "types")}>
          <SegmentedControl.Item value="items">Items</SegmentedControl.Item>
          <SegmentedControl.Item value="types">Item types</SegmentedControl.Item>
        </SegmentedControl.Root>
        <Flex gap="3" align="center">
          {tab === "items" && (
            <TextField.Root
              placeholder="Search items…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              style={{ minWidth: 220 }}
            />
          )}
          {tab === "items" ? (
            <Button onClick={() => setEditItem({})}>
              <PlusIcon /> Add item
            </Button>
          ) : (
            <Button onClick={() => setEditType({})}>
              <PlusIcon /> Add item type
            </Button>
          )}
        </Flex>
      </Flex>

      {tab === "items" ? (
        <Card>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left" }}>
                <Th>Name</Th>
                <Th>Type</Th>
                <Th>Location</Th>
                <Th>Condition</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr
                  key={i.id}
                  className="clickable"
                  onClick={() => setDetailItem(i)}
                  style={{ borderTop: "1px solid var(--gray-4)" }}
                >
                  <Td>{i.name}</Td>
                  <Td>{i.item_type_name}</Td>
                  <Td>{i.location ?? "—"}</Td>
                  <Td>{i.condition}</Td>
                  <Td>
                    <StatusBadge status={i.status} />
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && (
            <Box p="3">
              <Text color="gray">No items yet.</Text>
            </Box>
          )}
        </Card>
      ) : (
        <Grid columns={{ initial: "1", sm: "2", lg: "3" }} gap="3">
          {types.map((t) => (
            <Card key={t.id} className="clickable" onClick={() => setEditType(t)}>
              <Flex justify="between">
                <Heading size="3">{t.name}</Heading>
                <Badge variant="soft" color="gray">
                  {t.item_count} items
                </Badge>
              </Flex>
              <Text size="2" color="gray">
                {t.manufacturer ?? "—"}
                {t.author ? ` · ${t.author}` : ""}
              </Text>
              {t.description && (
                <Text size="2" mt="1">
                  {t.description}
                </Text>
              )}
            </Card>
          ))}
          {types.length === 0 && <Text color="gray">No item types yet.</Text>}
        </Grid>
      )}

      {editType && (
        <ItemTypeDialog
          type={editType}
          manufacturers={manufacturers}
          onClose={() => setEditType(null)}
          onSaved={() => {
            setEditType(null);
            loadAll();
          }}
        />
      )}

      {editItem && (
        <ItemDialog
          item={editItem}
          types={types}
          locations={locations}
          onClose={() => setEditItem(null)}
          onAddType={() => setEditType({})}
          onSaved={() => {
            setEditItem(null);
            loadItems();
            loadAll();
          }}
        />
      )}

      {detailItem && (
        <ItemDetailDialog
          item={detailItem}
          onClose={() => setDetailItem(null)}
          onEdit={(i) => {
            setDetailItem(null);
            setEditItem(i);
          }}
          onDeleted={() => {
            setDetailItem(null);
            loadItems();
            loadAll();
          }}
        />
      )}
    </Box>
  );
}

function ItemTypeDialog({
  type,
  manufacturers,
  onClose,
  onSaved,
}: {
  type: Partial<ItemType>;
  manufacturers: string[];
  onClose: () => void;
  onSaved: (created?: ItemType) => void;
}) {
  const isEdit = Boolean(type.id);
  const [form, setForm] = useState({
    name: type.name ?? "",
    manufacturer: type.manufacturer ?? null,
    author: type.author ?? "",
    publish_date: type.publish_date ?? "",
    description: type.description ?? "",
    url: type.url ?? "",
    cost: type.cost ?? "",
    upc_isbn: type.upc_isbn ?? "",
    photo_url: type.photo_url ?? "",
  });
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  async function save() {
    setBusy(true);
    try {
      const payload = {
        name: form.name,
        manufacturer: form.manufacturer || null,
        author: form.author || null,
        publish_date: form.publish_date || null,
        description: form.description || null,
        url: form.url || null,
        cost: form.cost === "" ? null : form.cost,
        upc_isbn: form.upc_isbn || null,
        photo_url: form.photo_url || null,
      };
      const result = isEdit
        ? await api.updateItemType(type.id!, payload)
        : await api.createItemType(payload);
      onSaved(result);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="520px">
        <Dialog.Title>{isEdit ? "Edit item type" : "New item type"}</Dialog.Title>
        <Flex direction="column" gap="3" mt="2">
          <Field label="Name">
            <TextField.Root value={form.name} onChange={(e) => set("name", e.target.value)} />
          </Field>
          <Field label="Manufacturer / Brand">
            <PassiveSelect
              value={form.manufacturer}
              options={manufacturers}
              onChange={(v) => set("manufacturer", v)}
            />
          </Field>
          <Grid columns="2" gap="3">
            <Field label="Author (optional)">
              <TextField.Root value={form.author} onChange={(e) => set("author", e.target.value)} />
            </Field>
            <Field label="Publish date (optional)">
              <TextField.Root
                type="date"
                value={form.publish_date}
                onChange={(e) => set("publish_date", e.target.value)}
              />
            </Field>
          </Grid>
          <Field label="Description">
            <TextArea
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
            />
          </Field>
          <Grid columns="2" gap="3">
            <Field label="Cost">
              <TextField.Root
                type="number"
                value={String(form.cost)}
                onChange={(e) => set("cost", e.target.value)}
              />
            </Field>
            <Field label="UPC / ISBN">
              <TextField.Root
                value={form.upc_isbn}
                onChange={(e) => set("upc_isbn", e.target.value)}
              />
            </Field>
          </Grid>
          <Field label="Photo URL">
            <TextField.Root value={form.photo_url} onChange={(e) => set("photo_url", e.target.value)} />
          </Field>
          <Field label="URL">
            <TextField.Root value={form.url} onChange={(e) => set("url", e.target.value)} />
          </Field>
        </Flex>
        <Flex gap="3" mt="4" justify="end">
          <Button variant="soft" color="gray" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={busy || !form.name} onClick={save}>
            Save
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

function ItemDialog({
  item,
  types,
  locations,
  onClose,
  onSaved,
  onAddType,
}: {
  item: Partial<Item>;
  types: ItemType[];
  locations: string[];
  onClose: () => void;
  onSaved: () => void;
  onAddType: () => void;
}) {
  const isEdit = Boolean(item.id);
  const [form, setForm] = useState({
    item_type_id: item.item_type_id ?? "",
    name: item.name ?? "",
    location: item.location ?? null,
    condition: item.condition ?? "New",
    purchase_price: item.purchase_price ?? "",
    purchase_date: item.purchase_date ?? "",
    description: item.description ?? "",
    barcode: item.barcode ?? "",
  });
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  async function save() {
    setBusy(true);
    try {
      const payload = {
        item_type_id: form.item_type_id,
        name: form.name,
        location: form.location || null,
        condition: form.condition,
        purchase_price: form.purchase_price === "" ? null : form.purchase_price,
        purchase_date: form.purchase_date || null,
        description: form.description || null,
      };
      if (isEdit) {
        await api.updateItem(item.id!, payload);
      } else {
        await api.createItem({ ...payload, barcode: form.barcode || null });
      }
      onSaved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="520px">
        <Dialog.Title>{isEdit ? "Edit item" : "New item"}</Dialog.Title>
        <Flex direction="column" gap="3" mt="2">
          <Field label="Item type">
            {/* Passive creation: choosing "+ Add new type…" opens the item-type form. */}
            <Select.Root
              value={form.item_type_id || undefined}
              onValueChange={(v) => (v === ADD_NEW_TYPE ? onAddType() : set("item_type_id", v))}
            >
              <Select.Trigger style={{ width: "100%" }} placeholder="Select a type…" />
              <Select.Content>
                {types.map((t) => (
                  <Select.Item key={t.id} value={t.id}>
                    {t.name}
                  </Select.Item>
                ))}
                <Select.Separator />
                <Select.Item value={ADD_NEW_TYPE}>+ Add new type…</Select.Item>
              </Select.Content>
            </Select.Root>
          </Field>
          <Field label="Name">
            <TextField.Root
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="e.g. Calculator #3"
            />
          </Field>
          <Grid columns="2" gap="3">
            <Field label="Location">
              <PassiveSelect
                value={form.location}
                options={locations}
                onChange={(v) => set("location", v)}
              />
            </Field>
            <Field label="Condition">
              <Select.Root value={form.condition} onValueChange={(v) => set("condition", v)}>
                <Select.Trigger style={{ width: "100%" }} />
                <Select.Content>
                  {["New", "Used", "Lost", "Damaged", "Discarded"].map((c) => (
                    <Select.Item key={c} value={c}>
                      {c}
                    </Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
            </Field>
          </Grid>
          <Grid columns="2" gap="3">
            <Field label="Purchase price">
              <TextField.Root
                type="number"
                value={String(form.purchase_price)}
                onChange={(e) => set("purchase_price", e.target.value)}
              />
            </Field>
            <Field label="Purchase date">
              <TextField.Root
                type="date"
                value={form.purchase_date}
                onChange={(e) => set("purchase_date", e.target.value)}
              />
            </Field>
          </Grid>
          <Field label="Description (defaults to type)">
            <TextArea
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
            />
          </Field>
          {!isEdit && (
            <Field label="Barcode (blank = auto-generate)">
              <TextField.Root
                value={form.barcode}
                onChange={(e) => set("barcode", e.target.value)}
              />
            </Field>
          )}
        </Flex>
        <Flex gap="3" mt="4" justify="end">
          <Button variant="soft" color="gray" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={busy || !form.name || !form.item_type_id} onClick={save}>
            Save
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

function ItemDetailDialog({
  item,
  onClose,
  onEdit,
  onDeleted,
}: {
  item: Item;
  onClose: () => void;
  onEdit: (i: Item) => void;
  onDeleted: () => void;
}) {
  const [events, setEvents] = useState<ItemEvent[]>([]);
  const [printOpen, setPrintOpen] = useState(false);

  useEffect(() => {
    api.adminItemEvents(item.id).then(setEvents);
  }, [item.id]);

  async function remove() {
    if (!confirm(`Delete ${item.name}? This removes its history too.`)) return;
    await api.deleteItem(item.id);
    onDeleted();
  }

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="560px">
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
            {item.item_type_name} · {item.location ?? "no location"} · {item.barcode}
          </Text>
        </Flex>
        {item.holder_name && (
          <Text size="2" mt="1">
            Currently with <strong>{item.holder_name}</strong>
          </Text>
        )}

        <Flex gap="2" mt="3" wrap="wrap">
          <Button size="1" variant="soft" onClick={() => onEdit(item)}>
            Edit
          </Button>
          <Button size="1" variant="soft" onClick={() => setPrintOpen(true)}>
            Print tag
          </Button>
          <Button size="1" variant="soft" color="red" onClick={remove}>
            Delete
          </Button>
        </Flex>

        <Separator my="4" size="4" />
        <Heading size="3" mb="2">
          History
        </Heading>
        <HistoryList events={events} />

        <BarcodeLabelDialog
          open={printOpen}
          onOpenChange={setPrintOpen}
          kind="Item tag"
          title={item.name}
          subtitle={item.item_type_name}
          barcodeValue={item.barcode}
          svgUrl={api.itemBarcodeSvg(item.id)}
        />
      </Dialog.Content>
    </Dialog.Root>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label>
      <Text size="2" as="div" mb="1">
        {label}
      </Text>
      {children}
    </label>
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
