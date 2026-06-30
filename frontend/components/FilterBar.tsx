"use client";

import type { ReactNode } from "react";
import { Button, Flex, Text } from "@radix-ui/themes";
import { Cross2Icon } from "@radix-ui/react-icons";

import { SearchField } from "./SearchField";

/**
 * The shared left-hand toolbar cluster for the filtered admin/inventory tables: a SearchField, the
 * page's own filter controls (`children` — MultiSelectFilters, toggles…), a Reset button that
 * appears only when filters deviate from their defaults, and a live result count. Sits inside the
 * page's existing `Flex justify="between"` row so the right-hand action buttons are untouched.
 */
export function FilterBar({
  search,
  dirty,
  onReset,
  shown,
  total,
  noun = "item",
  children,
}: {
  search: { value: string; onChange: (next: string) => void; placeholder?: string };
  dirty: boolean;
  onReset: () => void;
  shown?: number;
  total?: number;
  noun?: string;
  children?: ReactNode;
}) {
  // Pages with their own count (e.g. paginated History) omit `shown` to hide the inline count.
  let count: string | null = null;
  if (shown != null) {
    const n = total ?? shown;
    const label = `${noun}${n === 1 ? "" : "s"}`;
    count =
      total == null || shown === total ? `${n} ${label}` : `Showing ${shown} of ${total} ${label}`;
  }
  return (
    <Flex gap="2" align="center" wrap="wrap">
      <SearchField
        value={search.value}
        onChange={search.onChange}
        placeholder={search.placeholder}
      />
      {children}
      {dirty && (
        <Button variant="ghost" color="gray" onClick={onReset}>
          <Cross2Icon /> Reset
        </Button>
      )}
      {count && (
        <Text size="1" color="gray" style={{ whiteSpace: "nowrap" }}>
          {count}
        </Text>
      )}
    </Flex>
  );
}
