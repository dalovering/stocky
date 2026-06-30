"use client";

import { Button, DropdownMenu } from "@radix-ui/themes";

/**
 * A multi-value filter for an enum field: a button that opens a checkbox menu. The selected Set is
 * the filter — only rows whose value is in it are shown. Shared by the admin tables so every enum
 * filter behaves the same.
 */
export function MultiSelectFilter<T extends string>({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: readonly T[];
  selected: Set<T>;
  onChange: (next: Set<T>) => void;
}) {
  const summary =
    selected.size === options.length
      ? "All"
      : selected.size === 0
        ? "None"
        : selected.size === 1
          ? [...selected][0]
          : `${selected.size} selected`;

  function toggle(option: T, checked: boolean) {
    const next = new Set(selected);
    if (checked) next.add(option);
    else next.delete(option);
    onChange(next);
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger>
        <Button variant="soft" color="gray">
          {label}: {summary}
          <DropdownMenu.TriggerIcon />
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Content>
        {options.map((option) => (
          <DropdownMenu.CheckboxItem
            key={option}
            checked={selected.has(option)}
            // Keep the menu open while toggling several values.
            onSelect={(e) => e.preventDefault()}
            onCheckedChange={(checked) => toggle(option, checked)}
          >
            {option}
          </DropdownMenu.CheckboxItem>
        ))}
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  );
}
