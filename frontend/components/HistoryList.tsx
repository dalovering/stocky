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
};

const COLOR: Record<EventType, "gray" | "green" | "blue" | "orange" | "red"> = {
  create: "gray",
  checkout: "blue",
  checkin: "green",
  damage_report: "orange",
  loss_report: "red",
  discard: "red",
  repair: "green",
};

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
      cell: (e) => <Badge color={COLOR[e.event_type]}>{LABEL[e.event_type]}</Badge>,
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

export function StatusBadge({ status }: { status: string }) {
  const color =
    status === "Available"
      ? "green"
      : status === "On loan"
        ? "blue"
        : status === "Damaged"
          ? "orange"
          : "red";
  return <Badge color={color}>{status}</Badge>;
}
