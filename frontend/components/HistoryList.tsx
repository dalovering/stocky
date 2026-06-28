"use client";

// Renders an item's (or user's) event history as a simple timeline.

import { Badge, Flex, Text } from "@radix-ui/themes";

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

export function HistoryList({ events }: { events: ItemEvent[] }) {
  if (events.length === 0) {
    return (
      <Text color="gray" size="2">
        No history yet.
      </Text>
    );
  }
  return (
    <Flex direction="column" gap="2">
      {events.map((e) => (
        <Flex key={e.id} align="center" gap="3" justify="between">
          <Flex align="center" gap="2">
            <Badge color={COLOR[e.event_type]}>{LABEL[e.event_type]}</Badge>
            {e.user_name && <Text size="2">{e.user_name}</Text>}
            {e.note && (
              <Text size="2" color="gray">
                — {e.note}
              </Text>
            )}
          </Flex>
          <Text size="1" color="gray">
            {new Date(e.created_at).toLocaleString()}
          </Text>
        </Flex>
      ))}
    </Flex>
  );
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
