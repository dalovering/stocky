"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Button,
  Callout,
  Checkbox,
  Dialog,
  Flex,
  Grid,
  Heading,
  SegmentedControl,
  Select,
  Separator,
  Text,
  TextArea,
  TextField,
} from "@radix-ui/themes";
import {
  DownloadIcon,
  ExclamationTriangleIcon,
  EyeOpenIcon,
  IdCardIcon,
  Pencil1Icon,
  PlusIcon,
  TrashIcon,
} from "@radix-ui/react-icons";

import { AppShell } from "@/components/AppShell";
import { ConfirmButton, ConfirmDialog, DialogFooter, DialogHeader } from "@/components/Dialogs";
import { Field, isModified } from "@/components/Field";
import { FilterBar } from "@/components/FilterBar";
import { GroupedTable, type GroupNode } from "@/components/GroupedTable";
import { HistoryList, ReviewBadge, StatusBadge } from "@/components/HistoryList";
import { ImportExportButtons } from "@/components/ImportExportButtons";
import { ImportResultDialog } from "@/components/ImportResultDialog";
import { MultiSelectFilter } from "@/components/MultiSelectFilter";
import { PassiveSelect } from "@/components/PassiveSelect";
import { PrintMenuButton, type PrintMenuItem } from "@/components/PrintMenu";
import { SelectionBar } from "@/components/SelectionBar";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { usePrinter } from "@/hooks/usePrinter";
import { useSelection } from "@/hooks/useSelection";
import { useUrlFilters } from "@/hooks/useUrlFilters";
import { api, ApiError, downloadBlob } from "@/lib/api";
import {
  ACTIVE_ITEM_STATUSES,
  CONDITIONS,
  ITEM_STATUSES,
  SETTABLE_STATUSES,
  type Condition,
  type ImportResult,
  type Item,
  type ItemEvent,
  type ItemStatus,
  type ItemType,
  type PrintResult,
} from "@/lib/types";

const ADD_NEW_TYPE = "__add_new_type__";
const UNCHANGED = "__unchanged__";
// Filter sentinel for items with no location (matches the backend's queries.NO_LOCATION).
const NO_LOCATION = "__none__";

type ReviewFilter = "all" | "only" | "exclude";

/** True when a Set holds exactly the given values (order-independent) — for default detection. */
function setsEqual<T>(set: Set<T>, values: readonly T[]): boolean {
  return set.size === values.length && values.every((v) => set.has(v));
}

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

type ItemPatch = {
  item_type_id?: string;
  location?: string | null;
  condition?: Condition;
  needs_review?: boolean;
};

export default function InventoryAdminPage() {
  const [types, setTypes] = useState<ItemType[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [manufacturers, setManufacturers] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [needsReviewCount, setNeedsReviewCount] = useState(0);
  const [loading, setLoading] = useState(false);

  // Filters (server-side; synced to the URL). Status/Condition use the "Set holds the shown values"
  // convention; Type/Location use "empty Set = all" since their option universe is dynamic.
  const [q, setQ] = useState("");
  const [statusSel, setStatusSel] = useState<Set<ItemStatus>>(() => new Set(ACTIVE_ITEM_STATUSES));
  const [conditionSel, setConditionSel] = useState<Set<Condition>>(() => new Set(CONDITIONS));
  const [typeSel, setTypeSel] = useState<Set<string>>(() => new Set());
  const [locationSel, setLocationSel] = useState<Set<string>>(() => new Set());
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("all");

  const { selected, toggleOne, toggleMany, clear: clearSelection } = useSelection();
  const [editType, setEditType] = useState<Partial<ItemType> | null>(null);
  const [editItem, setEditItem] = useState<Partial<Item> | null>(null);
  const [detailItem, setDetailItem] = useState<Item | null>(null);
  const [batchOpen, setBatchOpen] = useState(false);
  const [del, setDel] = useState<DeleteTarget | null>(null);
  const [batchDelete, setBatchDelete] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const printer = usePrinter();

  const loadAll = useCallback(async () => {
    const [t, l, m] = await Promise.all([api.itemTypes(), api.locations(), api.manufacturers()]);
    setTypes(t);
    setLocations(l);
    setManufacturers(m);
  }, []);

  // Global, filter-independent counts (total items + items needing review) for the toolbar/banner.
  const loadStats = useCallback(async () => {
    const s = await api.itemStats();
    setTotal(s.total);
    setNeedsReviewCount(s.needs_review);
  }, []);

  const debouncedQ = useDebouncedValue(q);

  const loadItems = useCallback(async () => {
    // An empty Status/Condition selection means "show nothing"; short-circuit, since the server
    // treats an omitted param as "all" — the opposite of what an empty selection should do.
    if (statusSel.size === 0 || conditionSel.size === 0) {
      setItems([]);
      return;
    }
    setLoading(true);
    try {
      setItems(
        await api.adminItems({
          q: debouncedQ || undefined,
          status: [...statusSel],
          condition: [...conditionSel],
          type_id: typeSel.size ? [...typeSel] : undefined,
          location: locationSel.size ? [...locationSel] : undefined,
          needs_review: reviewFilter === "all" ? undefined : reviewFilter === "only",
        }),
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load items.");
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, statusSel, conditionSel, typeSel, locationSel, reviewFilter]);

  // Seed filters from the URL on mount, then keep the URL in sync. `hydrated` gates the first fetch
  // so the page queries once with the URL's filters rather than twice (defaults, then URL).
  const hydrated = useUrlFilters({
    decode: (sp) => {
      const qp = sp.get("q");
      if (qp) setQ(qp);
      const st = sp.getAll("status");
      if (st.length) setStatusSel(new Set(st as ItemStatus[]));
      const co = sp.getAll("condition");
      if (co.length) setConditionSel(new Set(co as Condition[]));
      const ty = sp.getAll("type");
      if (ty.length) setTypeSel(new Set(ty));
      const lo = sp.getAll("location");
      if (lo.length) setLocationSel(new Set(lo));
      const rv = sp.get("review");
      if (rv === "only" || rv === "exclude") setReviewFilter(rv);
    },
    params: {
      q: q || undefined,
      status: setsEqual(statusSel, ACTIVE_ITEM_STATUSES) ? undefined : [...statusSel],
      condition: setsEqual(conditionSel, CONDITIONS) ? undefined : [...conditionSel],
      type: [...typeSel],
      location: [...locationSel],
      review: reviewFilter === "all" ? undefined : reviewFilter,
    },
  });

  useEffect(() => {
    loadAll();
    loadStats();
  }, [loadAll, loadStats]);
  useEffect(() => {
    if (hydrated) loadItems();
  }, [hydrated, loadItems]);

  // Re-fetch the items and refresh the global counts after a mutation.
  const refresh = useCallback(async () => {
    await Promise.all([loadItems(), loadStats()]);
  }, [loadItems, loadStats]);

  async function download(blobPromise: Promise<Blob>, filename: string) {
    try {
      downloadBlob(await blobPromise, filename);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Download failed.");
    }
  }

  // Print to the thermal label printer; success (and any partial-failure warnings) land
  // in the green callout, failures in the red one — a print has no download to signal it.
  async function printLabels(resultPromise: Promise<PrintResult>) {
    try {
      const r = await resultPromise;
      const message = `Printed ${r.printed} label${r.printed === 1 ? "" : "s"}.`;
      setNotice(r.warnings.length ? `${message} ${r.warnings.join(" ")}` : message);
      setError(null);
    } catch (e) {
      setNotice(null);
      setError(e instanceof ApiError ? e.message : "Printing failed.");
    }
  }

  // Open the exact raster the printer will produce in a new tab.
  async function previewLabel(blobPromise: Promise<Blob>) {
    try {
      const url = URL.createObjectURL(await blobPromise);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Preview failed.");
    }
  }

  // Menu for a single item's print action (plain PDF button when no printer).
  function itemPrintMenu(id: string, barcode: string): PrintMenuItem[] | undefined {
    if (!printer.available) return undefined;
    return [
      { label: "Print to label printer", onClick: () => printLabels(api.printItems([id])) },
      { label: "Download PDF", onClick: () => download(api.itemTagPdf(id), `tag-${barcode}.pdf`) },
      { label: "Preview label", onClick: () => previewLabel(api.itemLabelPreview(id)) },
    ];
  }

  const dirty =
    q.trim() !== "" ||
    !setsEqual(statusSel, ACTIVE_ITEM_STATUSES) ||
    !setsEqual(conditionSel, CONDITIONS) ||
    typeSel.size > 0 ||
    locationSel.size > 0 ||
    reviewFilter !== "all";

  function reset() {
    setQ("");
    setStatusSel(new Set(ACTIVE_ITEM_STATUSES));
    setConditionSel(new Set(CONDITIONS));
    setTypeSel(new Set());
    setLocationSel(new Set());
    setReviewFilter("all");
  }

  // The orange banner is a one-way preset: show every flagged item, widening the other filters so
  // none is hidden (e.g. a flagged Lost one). The Reset that then appears is the single way back.
  function showAllFlagged() {
    setQ("");
    setStatusSel(new Set(ITEM_STATUSES));
    setConditionSel(new Set(CONDITIONS));
    setTypeSel(new Set());
    setLocationSel(new Set());
    setReviewFilter("only");
  }

  const typeName = useMemo(() => new Map(types.map((t) => [t.id, t.name])), [types]);
  const typeOptions = useMemo(() => types.map((t) => t.id), [types]);
  // Distinct server locations plus a "(No location)" option for null-location items.
  const locationOptions = useMemo(() => [NO_LOCATION, ...locations], [locations]);

  // The server already filtered the items; bucket them by type for display. Empty type groups show
  // in the default view (so you can still manage/add to a type) but are hidden while filtering.
  const groupNodes = useMemo<GroupNode<Item>[]>(() => {
    const byType = new Map<string, Item[]>();
    for (const i of items) {
      const list = byType.get(i.item_type_id);
      if (list) list.push(i);
      else byType.set(i.item_type_id, [i]);
    }
    const nodes: GroupNode<Item>[] = types.map((t) => {
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
          {
            icon: <IdCardIcon />,
            label: "Print all tags",
            onClick: () => download(api.itemTypeTagsPdf(t.id), `tags-${t.name}.pdf`),
            menu: printer.available
              ? [
                  {
                    label: "Print to label printer",
                    onClick: () => printLabels(api.printItemTypes([t.id])),
                  },
                  {
                    label: "Download PDF",
                    onClick: () => download(api.itemTypeTagsPdf(t.id), `tags-${t.name}.pdf`),
                  },
                ]
              : undefined,
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
    return dirty ? nodes.filter((n) => n.rows.length > 0) : nodes;
     
  }, [types, items, dirty, printer.available]);

  async function confirmDelete() {
    if (!del) return;
    const target = del;
    setDel(null);
    try {
      if (target.kind === "item") await api.deleteItem(target.id);
      else await api.deleteItemType(target.id);
      refresh();
      loadAll();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed.");
    }
  }

  async function confirmBatchDelete() {
    setBatchDelete(false);
    try {
      await api.batchDeleteItems([...selected]);
      clearSelection();
      refresh();
      loadAll();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed.");
    }
  }

  return (
    <AppShell>
      <Flex mb="3" gap="3" justify="between" align="center" wrap="wrap">
        <FilterBar
          search={{
            value: q,
            onChange: setQ,
            placeholder: "Search name, type, location, barcode…",
          }}
          dirty={dirty}
          onReset={reset}
          shown={items.length}
          total={total}
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
            label="Type"
            options={typeOptions}
            selected={typeSel}
            onChange={setTypeSel}
            emptyMeansAll
            renderOption={(id) => typeName.get(id) ?? id}
          />
          <MultiSelectFilter
            label="Location"
            options={locationOptions}
            selected={locationSel}
            onChange={setLocationSel}
            emptyMeansAll
            renderOption={(loc) => (loc === NO_LOCATION ? "(No location)" : loc)}
          />
          <Flex align="center" gap="1">
            <Text size="1" color="gray">
              Review
            </Text>
            <SegmentedControl.Root
              size="1"
              value={reviewFilter}
              onValueChange={(v) => setReviewFilter(v as ReviewFilter)}
            >
              <SegmentedControl.Item value="all">All</SegmentedControl.Item>
              <SegmentedControl.Item value="only">Flagged</SegmentedControl.Item>
              <SegmentedControl.Item value="exclude">Unflagged</SegmentedControl.Item>
            </SegmentedControl.Root>
          </Flex>
        </FilterBar>
        <Flex gap="2" wrap="wrap">
          <ImportExportButtons
            entity="items"
            exportName="stocky-items.xlsx"
            onExport={api.itemsXlsx}
            onImport={api.importItems}
            onImported={(r) => {
              setImportResult(r);
              refresh();
              loadAll();
            }}
            onError={setError}
          />
          <Button variant="soft" onClick={() => setEditType({})}>
            <PlusIcon /> Type
          </Button>
          <Button onClick={() => setEditItem({})}>
            <PlusIcon /> Item
          </Button>
        </Flex>
      </Flex>

      {error && (
        <Callout.Root color="red" mb="3" role="alert">
          <Callout.Text>{error}</Callout.Text>
        </Callout.Root>
      )}

      {notice && (
        <Callout.Root
          color="green"
          mb="3"
          role="status"
          onClick={() => setNotice(null)}
          style={{ cursor: "pointer" }}
        >
          <Callout.Text>{notice}</Callout.Text>
        </Callout.Root>
      )}

      {needsReviewCount > 0 && (
        <Callout.Root color="orange" mb="3" onClick={showAllFlagged} style={{ cursor: "pointer" }}>
          <Callout.Icon>
            <ExclamationTriangleIcon />
          </Callout.Icon>
          <Callout.Text>
            {needsReviewCount} {needsReviewCount === 1 ? "item needs" : "items need"} review. Click
            to view {needsReviewCount === 1 ? "it" : "them"}.
          </Callout.Text>
        </Callout.Root>
      )}

      <SelectionBar
        count={selected.size}
        onEdit={() => setBatchOpen(true)}
        onPrint={() => download(api.itemsTagsPdf([...selected]), "item-tags.pdf")}
        onPrintToPrinter={
          printer.available ? () => printLabels(api.printItems([...selected])) : undefined
        }
        printLabel="Print tags"
        onDelete={() => setBatchDelete(true)}
        onClear={clearSelection}
      />

      <GroupedTable
        groups={groupNodes}
        rowKey={(i) => i.id}
        empty={
          loading
            ? "Loading…"
            : types.length === 0
              ? "No item types yet."
              : "No items match your filters."
        }
        selectable
        selectedIds={selected}
        onToggle={toggleOne}
        onToggleMany={toggleMany}
        columns={[
          { header: "Name", cell: (i) => i.name },
          { header: "Location", cell: (i) => i.location ?? "—" },
          { header: "Condition", cell: (i) => i.condition },
          {
            header: "Status",
            cell: (i) => (
              <Flex gap="1" align="center">
                <StatusBadge status={i.status} />
                {i.needs_review && <ReviewBadge />}
              </Flex>
            ),
          },
        ]}
        rowActions={(i) => [
          { icon: <EyeOpenIcon />, label: "View", onClick: () => setDetailItem(i) },
          { icon: <Pencil1Icon />, label: "Edit", onClick: () => setEditItem(i) },
          {
            icon: <IdCardIcon />,
            label: "Print tag",
            onClick: () => download(api.itemTagPdf(i.id), `tag-${i.barcode}.pdf`),
            menu: itemPrintMenu(i.id, i.barcode),
          },
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
            refresh();
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
          onChanged={(i) => {
            setDetailItem(i);
            refresh();
          }}
          onDeleted={() => {
            setDetailItem(null);
            refresh();
            loadAll();
          }}
          printItems={
            itemPrintMenu(detailItem.id, detailItem.barcode) ?? [
              {
                label: "Print tag",
                onClick: () =>
                  download(api.itemTagPdf(detailItem.id), `tag-${detailItem.barcode}.pdf`),
              },
            ]
          }
        />
      )}

      {batchOpen && (
        <ItemBatchDialog
          count={selected.size}
          types={types}
          locations={locations}
          onClose={() => setBatchOpen(false)}
          onSaved={() => {
            setBatchOpen(false);
            clearSelection();
            refresh();
            loadAll();
          }}
          apply={async (patch, status) => {
            const ids = [...selected];
            if (Object.keys(patch).length > 0) await api.batchUpdateItems(ids, patch);
            if (status) await api.batchItemStatus(ids, status);
          }}
        />
      )}

      {importResult && (
        <ImportResultDialog
          result={importResult}
          subject="items"
          onClose={() => setImportResult(null)}
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

      <ConfirmDialog
        open={batchDelete}
        onOpenChange={(o) => !o && setBatchDelete(false)}
        title={`Delete ${selected.size} ${selected.size === 1 ? "item" : "items"}?`}
        description="This removes the selected items and their history. This cannot be undone."
        onConfirm={confirmBatchDelete}
      />
    </AppShell>
  );
}

function ItemBatchDialog({
  count,
  types,
  locations,
  onClose,
  onSaved,
  apply,
}: {
  count: number;
  types: ItemType[];
  locations: string[];
  onClose: () => void;
  onSaved: () => void;
  apply: (patch: ItemPatch, status: ItemStatus | undefined) => Promise<void>;
}) {
  const [typeId, setTypeId] = useState(UNCHANGED);
  const [condition, setCondition] = useState<string>(UNCHANGED);
  const [status, setStatus] = useState<string>(UNCHANGED);
  const [changeLocation, setChangeLocation] = useState(false);
  const [location, setLocation] = useState<string | null>(null);
  const [clearReview, setClearReview] = useState(false);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const patch: ItemPatch = {};
      if (typeId !== UNCHANGED) patch.item_type_id = typeId;
      if (condition !== UNCHANGED) patch.condition = condition as Condition;
      if (changeLocation) patch.location = location;
      if (clearReview) patch.needs_review = false;
      await apply(patch, status === UNCHANGED ? undefined : (status as ItemStatus));
      onSaved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="460px">
        <Dialog.Title>
          Edit {count} {count === 1 ? "item" : "items"}
        </Dialog.Title>
        <Text size="2" color="gray">
          Only the fields you change are applied to every selected item.
        </Text>
        <Flex direction="column" gap="3" mt="3">
          <Field label="Move to item type">
            <Select.Root value={typeId} onValueChange={setTypeId}>
              <Select.Trigger style={{ width: "100%" }} />
              <Select.Content>
                <Select.Item value={UNCHANGED}>Leave unchanged</Select.Item>
                {types.map((t) => (
                  <Select.Item key={t.id} value={t.id}>
                    {t.name}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </Field>
          <Field label="Set condition">
            <Select.Root value={condition} onValueChange={setCondition}>
              <Select.Trigger style={{ width: "100%" }} />
              <Select.Content>
                <Select.Item value={UNCHANGED}>Leave unchanged</Select.Item>
                {CONDITIONS.map((c) => (
                  <Select.Item key={c} value={c}>
                    {c}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </Field>
          <Field label="Set status">
            <Select.Root value={status} onValueChange={setStatus}>
              <Select.Trigger style={{ width: "100%" }} />
              <Select.Content>
                <Select.Item value={UNCHANGED}>Leave unchanged</Select.Item>
                {SETTABLE_STATUSES.map((s) => (
                  <Select.Item key={s} value={s}>
                    {s}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </Field>
          <label>
            <Flex gap="2" align="center" mb={changeLocation ? "2" : "0"}>
              <Checkbox
                checked={changeLocation}
                onCheckedChange={(c) => setChangeLocation(c === true)}
              />
              <Text size="2">Change location</Text>
            </Flex>
          </label>
          {changeLocation && (
            <PassiveSelect value={location} options={locations} onChange={setLocation} />
          )}
          <label>
            <Flex gap="2" align="center">
              <Checkbox checked={clearReview} onCheckedChange={(c) => setClearReview(c === true)} />
              <Text size="2">Clear “needs review” flag</Text>
            </Flex>
          </label>
        </Flex>
        <DialogFooter onCancel={onClose} onSave={save} saveDisabled={busy} saveLabel="Apply" />
      </Dialog.Content>
    </Dialog.Root>
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
            <TextField.Root
              value={form.photo_url}
              onChange={(e) => set("photo_url", e.target.value)}
            />
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
    needs_review: item.needs_review ?? false,
  });
  const [busy, setBusy] = useState(false);
  const [nameTouched, setNameTouched] = useState(isEdit || Boolean(item.name));
  const [descTouched, setDescTouched] = useState(isEdit || Boolean(item.description));
  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  const selectedType = types.find((t) => t.id === form.item_type_id);
  const defaults = isEdit
    ? null
    : {
        name: selectedType ? `${selectedType.name} ${selectedType.item_count + 1}` : form.name,
        description: selectedType ? (selectedType.description ?? "") : form.description,
        barcode: initialBarcode,
      };

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

  function reset(key: "name" | "description" | "barcode") {
    if (!defaults) return;
    if (key === "name") setNameTouched(false);
    if (key === "description") setDescTouched(false);
    set(key, defaults[key]);
  }

  async function save() {
    setBusy(true);
    try {
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
        await api.updateItem(item.id!, { ...payload, needs_review: form.needs_review });
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
                  {CONDITIONS.map((c) => (
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
            <TextArea value={form.description} onChange={(e) => editDescription(e.target.value)} />
          </Field>
          {isEdit && form.needs_review && (
            <label>
              <Flex
                gap="2"
                align="center"
                p="2"
                style={{ background: "var(--amber-2)", borderRadius: 6 }}
              >
                <Checkbox
                  checked={form.needs_review}
                  onCheckedChange={(c) => set("needs_review", c === true)}
                />
                <Text size="2">
                  Needs review — flagged by a damage/loss report. Uncheck to clear.
                </Text>
              </Flex>
            </label>
          )}
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
  onChanged,
  onDeleted,
  printItems,
}: {
  item: Item;
  onClose: () => void;
  onEdit: (i: Item) => void;
  onChanged: (i: Item) => void;
  onDeleted: () => void;
  printItems: PrintMenuItem[];
}) {
  const [events, setEvents] = useState<ItemEvent[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.adminItemEvents(item.id).then(setEvents);
  }, [item.id]);

  async function setStatus(status: ItemStatus) {
    setBusy(true);
    try {
      const updated = await api.setItemStatus(item.id, status);
      onChanged(updated);
      setEvents(await api.adminItemEvents(item.id));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    await api.deleteItem(item.id);
    onDeleted();
  }

  const statusActions: { status: ItemStatus; color?: "red" | "orange" }[] = [
    { status: "Available" },
    { status: "Unavailable", color: "orange" },
    { status: "Lost", color: "red" },
    { status: "Discarded", color: "red" },
  ];

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="560px">
        <DialogHeader title={item.name} />
        <Flex gap="2" align="center" wrap="wrap">
          <StatusBadge status={item.status} />
          {item.needs_review && <ReviewBadge />}
          <Text size="2" color="gray">
            {item.item_type_name} · {item.condition} · {item.location ?? "no location"} ·{" "}
            {item.barcode}
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
          <PrintMenuButton label="Print tag" items={printItems} />
          <ConfirmButton
            label="Delete"
            title={`Delete ${item.name}?`}
            description="This removes the item and its history. This cannot be undone."
            onConfirm={remove}
          />
        </Flex>

        <Separator my="3" size="4" />
        <Text size="2" weight="medium">
          Set status
        </Text>
        <Flex gap="2" mt="2" wrap="wrap">
          {statusActions.map((a) => (
            <Button
              key={a.status}
              size="1"
              variant={item.status === a.status ? "solid" : "soft"}
              color={a.color}
              disabled={busy || item.status === a.status}
              onClick={() => setStatus(a.status)}
            >
              {a.status}
            </Button>
          ))}
        </Flex>
        <Text size="1" color="gray" mt="1" as="p">
          Checked out / Available also follow check-in/out at the kiosk.
        </Text>

        <Separator my="3" size="4" />
        <Flex justify="between" align="center" mb="2">
          <Heading size="3">History</Heading>
          <Button
            size="1"
            variant="soft"
            color="gray"
            onClick={async () =>
              downloadBlob(
                await api.eventsXlsx({ item_id: item.id }),
                `stocky-history-${item.name}.xlsx`,
              )
            }
          >
            <DownloadIcon /> .xlsx
          </Button>
        </Flex>
        <HistoryList events={events} subject="item" />
      </Dialog.Content>
    </Dialog.Root>
  );
}
