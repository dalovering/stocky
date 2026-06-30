"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Box, Checkbox, Flex, IconButton, Table, Text, Tooltip } from "@radix-ui/themes";
import { ChevronDownIcon, ChevronRightIcon } from "@radix-ui/react-icons";

import type { Column } from "./DataTable";

/** One icon button in a row/group action cluster (view, edit, delete, …). */
export type RowAction = {
  icon: ReactNode;
  label: string; // tooltip + aria-label
  onClick: () => void;
  color?: "gray" | "red" | "blue";
};

/**
 * A node in a {@link GroupedTable}: a group header with optional nested subgroups and a set of
 * leaf rows. Used for items-grouped-by-type (one level) and nestable user groups (N levels).
 */
export type GroupNode<T> = {
  id: string;
  title: ReactNode;
  meta?: ReactNode; // right-of-title text, e.g. "12 users" or availability counts
  actions?: RowAction[]; // group-level actions (edit, delete, add child…)
  children?: GroupNode<T>[];
  rows: T[];
};

function ActionCluster({ actions }: { actions: RowAction[] }) {
  return (
    <Flex gap="1" justify="end" onClick={(e) => e.stopPropagation()}>
      {actions.map((a) => (
        <Tooltip key={a.label} content={a.label}>
          <IconButton
            size="1"
            variant="ghost"
            color={a.color ?? "gray"}
            aria-label={a.label}
            onClick={a.onClick}
          >
            {a.icon}
          </IconButton>
        </Tooltip>
      ))}
    </Flex>
  );
}

function collectIds<T>(groups: GroupNode<T>[], acc: Set<string>): Set<string> {
  for (const g of groups) {
    acc.add(g.id);
    if (g.children) collectIds(g.children, acc);
  }
  return acc;
}

/** Every leaf row's key under a node (including nested children) — for per-group select-all. */
function collectRowKeys<T>(node: GroupNode<T>, rowKey: (row: T) => string): string[] {
  const keys = node.rows.map(rowKey);
  for (const child of node.children ?? []) keys.push(...collectRowKeys(child, rowKey));
  return keys;
}

/**
 * The one grouped/nested table used across the app. Renders group-header rows (with an
 * expand/collapse toggle and optional group actions) interleaved with their leaf rows, all in a
 * single Radix `Table`. Reuses {@link Column} so leaf columns are defined exactly like `DataTable`.
 * Omit `rowActions`/group `actions` for a read-only table (the public inventory view).
 */
export function GroupedTable<T>({
  columns,
  groups,
  rowKey,
  rowActions,
  onRowClick,
  defaultExpanded = true,
  empty = "Nothing here yet.",
  selectable = false,
  selectedIds,
  onToggle,
  onToggleMany,
}: {
  columns: Column<T>[];
  groups: GroupNode<T>[];
  rowKey: (row: T) => string | number;
  rowActions?: (row: T) => RowAction[];
  onRowClick?: (row: T) => void;
  defaultExpanded?: boolean;
  empty?: ReactNode;
  // Opt-in multi-select: a leading checkbox column on leaf rows + a select-all on each group.
  selectable?: boolean;
  selectedIds?: Set<string>;
  onToggle?: (id: string, checked: boolean) => void;
  onToggleMany?: (ids: string[], checked: boolean) => void;
}) {
  const keyOf = (row: T) => String(rowKey(row));
  const selected = selectedIds ?? new Set<string>();
  // Track which groups are *collapsed* rather than expanded: groups load asynchronously, so a
  // set of expanded ids built on first render (when `groups` is still empty) would leave
  // everything collapsed. With a collapsed set, any group — including ones that arrive later — is
  // open unless the user has explicitly collapsed it.
  const [collapsed, setCollapsed] = useState<Set<string>>(() =>
    defaultExpanded ? new Set() : collectIds(groups, new Set()),
  );

  // Whether any group anywhere defines actions (per-row actions add the same trailing column).
  const hasGroupActions = useMemo(() => {
    const any = (gs: GroupNode<T>[]): boolean =>
      gs.some((g) => (g.actions?.length ?? 0) > 0 || (g.children ? any(g.children) : false));
    return any(groups);
  }, [groups]);
  const hasActions = Boolean(rowActions) || hasGroupActions;
  const totalColumns = columns.length + (hasActions ? 1 : 0) + (selectable ? 1 : 0);

  function toggle(id: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (groups.length === 0) {
    return (
      <Box p="3">
        <Text color="gray">{empty}</Text>
      </Box>
    );
  }

  // Flatten the (visible) tree into one ordered list of rows. Emitting a single flat list of
  // <Table.Row> children — rather than nested React fragments inside <tbody> — keeps the DOM a
  // clean sequence of <tr>s, which browsers reconcile reliably when groups expand/collapse.
  type Entry =
    | { kind: "group"; key: string; node: GroupNode<T>; depth: number; open: boolean }
    | { kind: "leaf"; key: string; row: T; depth: number };

  const entries: Entry[] = [];
  const walk = (nodes: GroupNode<T>[], depth: number) => {
    for (const node of nodes) {
      const open = !collapsed.has(node.id);
      entries.push({ kind: "group", key: `g-${node.id}`, node, depth, open });
      if (!open) continue;
      if (node.children) walk(node.children, depth + 1);
      for (const row of node.rows) {
        entries.push({ kind: "leaf", key: `r-${rowKey(row)}`, row, depth: depth + 1 });
      }
    }
  };
  walk(groups, 0);

  return (
    <Table.Root variant="surface" className="grouped-table">
      <Table.Header>
        <Table.Row>
          {selectable && <Table.ColumnHeaderCell aria-label="Select" style={{ width: 36 }} />}
          {columns.map((c, i) => (
            <Table.ColumnHeaderCell key={i}>{c.header}</Table.ColumnHeaderCell>
          ))}
          {hasActions && <Table.ColumnHeaderCell aria-label="Actions" />}
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {entries.map((e) =>
          e.kind === "group" ? (
            <Table.Row key={e.key} style={{ background: "var(--gray-2)" }}>
              {selectable && (
                <Table.Cell onClick={(ev) => ev.stopPropagation()}>
                  {(() => {
                    const keys = collectRowKeys(e.node, keyOf);
                    const picked = keys.filter((k) => selected.has(k)).length;
                    const checked =
                      keys.length > 0 && picked === keys.length
                        ? true
                        : picked > 0
                          ? "indeterminate"
                          : false;
                    return (
                      <Checkbox
                        checked={checked}
                        disabled={keys.length === 0}
                        onCheckedChange={(c) => onToggleMany?.(keys, c === true)}
                      />
                    );
                  })()}
                </Table.Cell>
              )}
              <Table.Cell colSpan={selectable ? totalColumns - 1 : totalColumns}>
                <Flex align="center" gap="2" style={{ paddingLeft: e.depth * 20 }}>
                  <IconButton
                    size="1"
                    variant="ghost"
                    color="gray"
                    aria-label={e.open ? "Collapse" : "Expand"}
                    onClick={() => toggle(e.node.id)}
                  >
                    {e.open ? <ChevronDownIcon /> : <ChevronRightIcon />}
                  </IconButton>
                  <Text weight="medium">{e.node.title}</Text>
                  {e.node.meta != null && (
                    <Text size="2" color="gray">
                      {e.node.meta}
                    </Text>
                  )}
                  {e.node.actions && e.node.actions.length > 0 && (
                    <Box flexGrow="1">
                      <ActionCluster actions={e.node.actions} />
                    </Box>
                  )}
                </Flex>
              </Table.Cell>
            </Table.Row>
          ) : (
            <Table.Row
              key={e.key}
              className={onRowClick ? "clickable" : undefined}
              onClick={onRowClick ? () => onRowClick(e.row) : undefined}
            >
              {selectable && (
                <Table.Cell onClick={(ev) => ev.stopPropagation()}>
                  <Checkbox
                    checked={selected.has(keyOf(e.row))}
                    onCheckedChange={(c) => onToggle?.(keyOf(e.row), c === true)}
                  />
                </Table.Cell>
              )}
              {columns.map((c, i) => (
                <Table.Cell
                  key={i}
                  style={i === 0 ? { paddingLeft: e.depth * 20 + 8 } : undefined}
                >
                  {c.cell(e.row)}
                </Table.Cell>
              ))}
              {hasActions && (
                <Table.Cell>
                  {rowActions && <ActionCluster actions={rowActions(e.row)} />}
                </Table.Cell>
              )}
            </Table.Row>
          ),
        )}
      </Table.Body>
    </Table.Root>
  );
}
