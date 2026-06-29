"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Button,
  Callout,
  Dialog,
  Flex,
  Grid,
  Heading,
  Select,
  Separator,
  Text,
  TextArea,
  TextField,
} from "@radix-ui/themes";
import { EyeOpenIcon, IdCardIcon, Pencil1Icon, PlusIcon, TrashIcon } from "@radix-ui/react-icons";

import { AppShell } from "@/components/AppShell";
import { BarcodeLabelDialog } from "@/components/BarcodeLabelDialog";
import { ConfirmButton, ConfirmDialog, DialogFooter, DialogHeader } from "@/components/Dialogs";
import { Field, isModified } from "@/components/Field";
import { GroupedTable, type GroupNode } from "@/components/GroupedTable";
import { HistoryList, StatusBadge } from "@/components/HistoryList";
import { PassiveSelect } from "@/components/PassiveSelect";
import { api, ApiError } from "@/lib/api";
import type { Item, ItemEvent, ItemType } from "@/lib/types";

const ADD_NEW_TYPE = "__add_new_type__";

// Client-side item barcode, matching the backend format (`I` + 10 digits, see
// backend/app/services/barcode.py). Pre-filled when opening the new-item modal so the admin
// has a value to print right away; the backend still guarantees uniqueness on save and falls
// back to generating one if the field is cleared.
function generateItemBarcode(): string {
  let digits = "";
  for (let i = 0; i < 10; i++) digits += Math.floor(Math.random() * 10);
  return `I${digits}`;
}

type DeleteTarget = { kind: "item" | "type"; id: string; name: string };

export default function InventoryAdminPage() {
  const [types, setTypes] = useState<ItemType[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [manufacturers, setManufacturers] = useState<string[]>([]);
  const [q, setQ] = useState("");

  const [editType, setEditType] = useState<Partial<ItemType> | null>(null);
  const [editItem, setEditItem] = useState<Partial<Item> | null>(null);
  const [detailItem, setDetailItem] = useState<Item | null>(null);
  const [printItem, setPrintItem] = useState<Item | null>(null);
  const [del, setDel] = useState<DeleteTarget | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    const [t, l, m] = await Promise.all([api.itemTypes(), api.locations(), api.manufacturers()]);
    setTypes(t);
    setLocations(l);
    setManufacturers(m);
  }, []);

  const loadItems = useCallback(async () => {
    setItems(await api.adminItems());
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);
  useEffect(() => {
    loadItems();
  }, [loadItems]);

  // One group per item type, with its items beneath (name-filtered client-side so the type
  // headers stay stable while searching).
  const groupNodes = useMemo<GroupNode<Item>[]>(() => {
    const needle = q.trim().toLowerCase();
    const byType = new Map<string, Item[]>();
    for (const i of items) {
      if (needle && !i.name.toLowerCase().includes(needle)) continue;
      const list = byType.get(i.item_type_id);
      if (list) list.push(i);
      else byType.set(i.item_type_id, [i]);
    }
    return types.map((t) => {
      const rows = byType.get(t.id) ?? [];
      return {
        id: t.id,
        title: t.name,
        meta: `${rows.length} ${rows.length === 1 ? "item" : "items"}`,
        actions: [
          {
            icon: <PlusIcon />,
            label: "Add item of this type",
            onClick: () => setEditItem({ item_type_id: t.id }),
          },
          { icon: <Pencil1Icon />, label: "Edit type", onClick: () => setEditType(t) },
          {
            icon: <TrashIcon />,
            label: "Delete type",
            color: "red",
            onClick: () => setDel({ kind: "type", id: t.id, name: t.name }),
          },
        ],
        children: [],
        rows,
      };
    });
  }, [types, items, q]);

  async function confirmDelete() {
    if (!del) return;
    const target = del;
    setDel(null);
    try {
      if (target.kind === "item") await api.deleteItem(target.id);
      else await api.deleteItemType(target.id);
      loadItems();
      loadAll();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed.");
    }
  }

  return (
    <AppShell>
      <Flex mb="3" gap="3" justify="between" align="center" wrap="wrap">
        <TextField.Root
          placeholder="Search items…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ minWidth: 220 }}
        />
        <Flex gap="3">
          <Button variant="soft" onClick={() => setEditType({})}>
            <PlusIcon /> Add item type
          </Button>
          <Button onClick={() => setEditItem({})}>
            <PlusIcon /> Add item
          </Button>
        </Flex>
      </Flex>

      {error && (
        <Callout.Root color="red" mb="3" role="alert">
          <Callout.Text>{error}</Callout.Text>
        </Callout.Root>
      )}

      <GroupedTable
        groups={groupNodes}
        rowKey={(i) => i.id}
        empty="No item types yet."
        columns={[
          { header: "Name", cell: (i) => i.name },
          { header: "Location", cell: (i) => i.location ?? "—" },
          { header: "Condition", cell: (i) => i.condition },
          { header: "Status", cell: (i) => <StatusBadge status={i.status} /> },
        ]}
        rowActions={(i) => [
          { icon: <EyeOpenIcon />, label: "View", onClick: () => setDetailItem(i) },
          { icon: <Pencil1Icon />, label: "Edit", onClick: () => setEditItem(i) },
          { icon: <IdCardIcon />, label: "Print tag", onClick: () => setPrintItem(i) },
          {
            icon: <TrashIcon />,
            label: "Delete",
            color: "red",
            onClick: () => setDel({ kind: "item", id: i.id, name: i.name }),
          },
        ]}
      />

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

      {printItem && (
        <BarcodeLabelDialog
          open
          onOpenChange={(o) => !o && setPrintItem(null)}
          kind="Item tag"
          title={printItem.name}
          subtitle={printItem.item_type_name}
          barcodeValue={printItem.barcode}
          svgUrl={api.itemBarcodeSvg(printItem.id)}
        />
      )}

      <ConfirmDialog
        open={del !== null}
        onOpenChange={(o) => !o && setDel(null)}
        title={del ? `Delete ${del.name}?` : ""}
        description={
          del?.kind === "type"
            ? "This deletes the item type. It must have no items first."
            : "This removes the item and its history. This cannot be undone."
        }
        onConfirm={confirmDelete}
      />
    </AppShell>
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
            <Field label="Author" hint="(optional)">
              <TextField.Root value={form.author} onChange={(e) => set("author", e.target.value)} />
            </Field>
            <Field label="Publish date" hint="(optional)">
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
        <DialogFooter onCancel={onClose} onSave={save} saveDisabled={busy || !form.name} />
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
  // Barcode is generated once for new items so it's visible/printable; editing keeps the existing one.
  const [initialBarcode] = useState(() => item.barcode ?? (isEdit ? "" : generateItemBarcode()));
  const [form, setForm] = useState({
    item_type_id: item.item_type_id ?? "",
    name: item.name ?? "",
    location: item.location ?? null,
    condition: item.condition ?? "New",
    purchase_price: item.purchase_price ?? "",
    purchase_date: item.purchase_date ?? "",
    description: item.description ?? "",
    barcode: initialBarcode,
  });
  const [busy, setBusy] = useState(false);
  // Whether the admin has overridden the auto-filled name / description. Until then we keep them in
  // sync with the selected type so picking a type fills sensible, overridable defaults.
  const [nameTouched, setNameTouched] = useState(isEdit || Boolean(item.name));
  const [descTouched, setDescTouched] = useState(isEdit || Boolean(item.description));
  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  // Only fields with a *program-derived* default get change-tracking, and only for new items:
  //   • name        → "{type name} {existing count + 1}"
  //   • description  → the selected type's description (blank if none)
  //   • barcode      → the generated value
  // Free-text / blank / constant fields (type, location, condition, price, date) have no logical
  // default, so they aren't tracked. The name/description defaults only become meaningful once a
  // type is picked; until then they mirror the current value so nothing reads as "changed".
  const selectedType = types.find((t) => t.id === form.item_type_id);
  const defaults = isEdit
    ? null
    : {
        name: selectedType ? `${selectedType.name} ${selectedType.item_count + 1}` : form.name,
        description: selectedType ? (selectedType.description ?? "") : form.description,
        barcode: initialBarcode,
      };

  // Choosing a type: open the new-type form for the sentinel, otherwise select it and (unless the
  // admin has overridden them) fill the name and description defaults from that type.
  function selectType(typeId: string) {
    const t = types.find((x) => x.id === typeId);
    setForm((f) => ({
      ...f,
      item_type_id: typeId,
      name: !nameTouched && t ? `${t.name} ${t.item_count + 1}` : f.name,
      description: !descTouched && t ? (t.description ?? "") : f.description,
    }));
  }

  function editName(value: string) {
    setNameTouched(true);
    set("name", value);
  }

  function editDescription(value: string) {
    setDescTouched(true);
    set("description", value);
  }

  // Restore a tracked field to its default, re-enabling the type-driven auto-fill for name/description.
  function reset(key: "name" | "description" | "barcode") {
    if (!defaults) return;
    if (key === "name") setNameTouched(false);
    if (key === "description") setDescTouched(false);
    set(key, defaults[key]);
  }

  async function save() {
    setBusy(true);
    try {
      // When the description still matches the type's (the untouched default), store null so the
      // item keeps inheriting from the type rather than freezing a denormalized copy.
      const description =
        defaults && form.description === defaults.description ? null : form.description || null;
      const payload = {
        item_type_id: form.item_type_id,
        name: form.name,
        location: form.location || null,
        condition: form.condition,
        purchase_price: form.purchase_price === "" ? null : form.purchase_price,
        purchase_date: form.purchase_date || null,
        description,
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
              onValueChange={(v) => (v === ADD_NEW_TYPE ? onAddType() : selectType(v))}
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
          <Field
            label="Name"
            modified={!!defaults && isModified(form.name, defaults.name)}
            onReset={() => reset("name")}
          >
            <TextField.Root
              value={form.name}
              onChange={(e) => editName(e.target.value)}
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
          <Field
            label="Description"
            hint="(defaults to type)"
            modified={!!defaults && isModified(form.description, defaults.description)}
            onReset={() => reset("description")}
          >
            <TextArea
              value={form.description}
              onChange={(e) => editDescription(e.target.value)}
            />
          </Field>
          {!isEdit && (
            <Field
              label="Barcode"
              hint="(blank = auto-generate)"
              modified={!!defaults && isModified(form.barcode, defaults.barcode)}
              onReset={() => reset("barcode")}
            >
              <TextField.Root
                value={form.barcode}
                onChange={(e) => set("barcode", e.target.value)}
              />
            </Field>
          )}
        </Flex>
        <DialogFooter
          onCancel={onClose}
          onSave={save}
          saveDisabled={busy || !form.name || !form.item_type_id}
        />
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
    await api.deleteItem(item.id);
    onDeleted();
  }

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="560px">
        <DialogHeader title={item.name} />
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
          <ConfirmButton
            label="Delete"
            title={`Delete ${item.name}?`}
            description="This removes the item and its history. This cannot be undone."
            onConfirm={remove}
          />
        </Flex>

        <Separator my="4" size="4" />
        <Heading size="3" mb="2">
          History
        </Heading>
        <HistoryList events={events} subject="item" />

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
