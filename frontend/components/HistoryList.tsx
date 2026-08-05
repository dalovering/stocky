"use client";

// Renders an item's (or user's) event history as a table.

import { Badge, Text } from "@radix-ui/themes";

import { DataTable, type Column } from "@/components/DataTable";
import type { EventType, ItemEvent } from "@/lib/types";

const LABEL: Record<EventType, string> = {
  create: "Created",
  checkout: "Checked out",
  checkin: "Checked in",
  damage_report: "Damage reported",
  loss_report: "Reported lost",
  discard: "Discarded",
  repair: "Repaired",
  mark_unavailable: "Marked unavailable",
  restore: "Restored",
};

const COLOR: Record<EventType, "gray" | "green" | "blue" | "orange" | "red"> = {
  create: "gray",
  checkout: "blue",
  checkin: "green",
  damage_report: "orange",
  loss_report: "red",
  discard: "red",
  repair: "green",
  mark_unavailable: "orange",
  restore: "green",
};

export const EVENT_TYPE_OPTIONS = (Object.keys(LABEL) as EventType[]).map((value) => ({
  value,
  label: LABEL[value],
}));

/** The coloured badge for one event type — reused by item/user history and the admin history log. */
export function EventBadge({ type }: { type: EventType }) {
  return <Badge color={COLOR[type]}>{LABEL[type]}</Badge>;
}

/**
 * The event history of one `subject`. When it's a user's history every row shares that user, so we
 * show the *item* column and drop the redundant user column; for an item's history it's the
 * reverse. Note/When are always shown.
 */
export function HistoryList({
  events,
  subject,
}: {
  events: ItemEvent[];
  subject: "user" | "item";
}) {
  const columns: Column<ItemEvent>[] = [
    {
      header: "Action",
      cell: (e) => <EventBadge type={e.event_type} />,
    },
    subject === "user"
      ? { header: "Item", cell: (e) => e.item_name ?? "—" }
      : { header: "User", cell: (e) => e.user_name ?? "—" },
    {
      header: "Note",
      cell: (e) => (
        <Text size="2" color="gray">
          {e.note ?? "—"}
        </Text>
      ),
    },
    {
      header: "When",
      cell: (e) => (
        <Text size="1" color="gray" style={{ whiteSpace: "nowrap" }}>
          {new Date(e.created_at).toLocaleString()}
        </Text>
      ),
    },
  ];
  return <DataTable rows={events} rowKey={(e) => e.id} empty="No history yet." columns={columns} />;
}

const STATUS_COLOR: Record<string, "green" | "blue" | "orange" | "red" | "gray"> = {
  // Item statuses
  Available: "green",
  "Checked out": "blue",
  Unavailable: "orange",
  Lost: "red",
  Discarded: "gray",
  // User statuses
  Active: "green",
  Inactive: "gray",
};

/** Coloured badge for an item or user status. */
export function StatusBadge({ status }: { status: string }) {
  return <Badge color={STATUS_COLOR[status] ?? "gray"}>{status}</Badge>;
}

/** The "needs review" flag shown on flagged items. */
export function ReviewBadge() {
  return (
    <Badge color="orange" variant="soft">
      review
    </Badge>
  );
}
