"use client";

import type { ReactNode } from "react";
import { Box, Table, Text } from "@radix-ui/themes";

export type Column<T> = {
  header: ReactNode;
  cell: (row: T) => ReactNode;
};

/**
 * The one table used across the app (admin items, admin users, inventory summary). Wraps the
 * Radix `Table` primitive so every list shares the same surface, spacing, and hover/row-click
 * behavior — define columns once, pass rows, optionally make rows clickable.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  empty = "Nothing here yet.",
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string | number;
  onRowClick?: (row: T) => void;
  empty?: ReactNode;
}) {
  if (rows.length === 0) {
    return (
      <Box p="3">
        <Text color="gray">{empty}</Text>
      </Box>
    );
  }
  return (
    <Table.Root variant="surface">
      <Table.Header>
        <Table.Row>
          {columns.map((c, i) => (
            <Table.ColumnHeaderCell key={i}>{c.header}</Table.ColumnHeaderCell>
          ))}
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {rows.map((row, index) => (
          <Table.Row
            key={rowKey(row, index)}
            className={onRowClick ? "clickable" : undefined}
            onClick={onRowClick ? () => onRowClick(row) : undefined}
          >
            {columns.map((c, i) => (
              <Table.Cell key={i}>{c.cell(row)}</Table.Cell>
            ))}
          </Table.Row>
        ))}
      </Table.Body>
    </Table.Root>
  );
}
