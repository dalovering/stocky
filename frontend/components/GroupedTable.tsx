"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Box, Flex, IconButton, Table, Text, Tooltip } from "@radix-ui/themes";
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
}: {
  columns: Column<T>[];
  groups: GroupNode<T>[];
  rowKey: (row: T) => string | number;
  rowActions?: (row: T) => RowAction[];
  onRowClick?: (row: T) => void;
  defaultExpanded?: boolean;
  empty?: ReactNode;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(() =>
    defaultExpanded ? collectIds(groups, new Set()) : new Set(),
  );

  // Whether any group anywhere defines actions (per-row actions add the same trailing column).
  const hasGroupActions = useMemo(() => {
    const any = (gs: GroupNode<T>[]): boolean =>
      gs.some((g) => (g.actions?.length ?? 0) > 0 || (g.children ? any(g.children) : false));
    return any(groups);
  }, [groups]);
  const hasActions = Boolean(rowActions) || hasGroupActions;
  const totalColumns = columns.length + (hasActions ? 1 : 0);

  function toggle(id: string) {
    setExpanded((prev) => {
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

  function renderGroup(node: GroupNode<T>, depth: number): ReactNode {
    const isOpen = expanded.has(node.id);
    return (
      <FragmentRow key={`g-${node.id}`}>
        <Table.Row style={{ background: "var(--gray-2)" }}>
          <Table.Cell colSpan={totalColumns}>
            <Flex align="center" gap="2" style={{ paddingLeft: depth * 20 }}>
              <IconButton
                size="1"
                variant="ghost"
                color="gray"
                aria-label={isOpen ? "Collapse" : "Expand"}
                onClick={() => toggle(node.id)}
              >
                {isOpen ? <ChevronDownIcon /> : <ChevronRightIcon />}
              </IconButton>
              <Text weight="medium">{node.title}</Text>
              {node.meta != null && (
                <Text size="2" color="gray">
                  {node.meta}
                </Text>
              )}
              {node.actions && node.actions.length > 0 && (
                <Box flexGrow="1">
                  <ActionCluster actions={node.actions} />
                </Box>
              )}
            </Flex>
          </Table.Cell>
        </Table.Row>

        {isOpen && (
          <>
            {node.children?.map((child) => renderGroup(child, depth + 1))}
            {node.rows.map((row) => (
              <Table.Row
                key={`r-${rowKey(row)}`}
                className={onRowClick ? "clickable" : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((c, i) => (
                  <Table.Cell
                    key={i}
                    style={i === 0 ? { paddingLeft: (depth + 1) * 20 + 8 } : undefined}
                  >
                    {c.cell(row)}
                  </Table.Cell>
                ))}
                {hasActions && (
                  <Table.Cell>{rowActions && <ActionCluster actions={rowActions(row)} />}</Table.Cell>
                )}
              </Table.Row>
            ))}
          </>
        )}
      </FragmentRow>
    );
  }

  return (
    <Table.Root variant="surface">
      <Table.Header>
        <Table.Row>
          {columns.map((c, i) => (
            <Table.ColumnHeaderCell key={i}>{c.header}</Table.ColumnHeaderCell>
          ))}
          {hasActions && <Table.ColumnHeaderCell aria-label="Actions" />}
        </Table.Row>
      </Table.Header>
      <Table.Body>{groups.map((g) => renderGroup(g, 0))}</Table.Body>
    </Table.Root>
  );
}

/** A keyed fragment so a group header and its descendant rows share one React key. */
function FragmentRow({ children }: { key?: string; children: ReactNode }) {
  return <>{children}</>;
}
