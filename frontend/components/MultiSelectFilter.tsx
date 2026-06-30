"use client";

import type { ReactNode } from "react";
import { Button, DropdownMenu } from "@radix-ui/themes";

/**
 * A multi-value filter for an enum/categorical field: a button that opens a checkbox menu. The
 * selected Set is the filter. Shared by the admin tables so every filter behaves the same.
 *
 * Two conventions for "show everything":
 *  - default: the Set holds every option that should be shown (seed it to the full enum). An empty
 *    Set means "show none".
 *  - `emptyMeansAll`: an **empty** Set means "no filter / show all" — use this for filters whose
 *    option universe is dynamic (Type, Location), so newly-added values are never silently hidden.
 *
 * `renderOption` maps an option to a display label (e.g. a null-location sentinel → "(No location)").
 */
export function MultiSelectFilter<T extends string>({
  label,
  options,
  selected,
  onChange,
  emptyMeansAll = false,
  renderOption,
}: {
  label: string;
  options: readonly T[];
  selected: Set<T>;
  onChange: (next: Set<T>) => void;
  emptyMeansAll?: boolean;
  renderOption?: (option: T) => ReactNode;
}) {
  const renderLabel = renderOption ?? ((option: T) => option as ReactNode);
  const showsAll = selected.size === options.length || (emptyMeansAll && selected.size === 0);
  const summary: ReactNode = showsAll
    ? "All"
    : selected.size === 0
      ? "None"
      : selected.size === 1
        ? renderLabel([...selected][0])
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
        {/* Quick actions. `emptyMeansAll` filters have no meaningful "None" (empty = all). */}
        <DropdownMenu.Item
          onSelect={(e) => {
            e.preventDefault();
            onChange(emptyMeansAll ? new Set<T>() : new Set(options));
          }}
        >
          All
        </DropdownMenu.Item>
        {!emptyMeansAll && (
          <DropdownMenu.Item
            onSelect={(e) => {
              e.preventDefault();
              onChange(new Set<T>());
            }}
          >
            None
          </DropdownMenu.Item>
        )}
        <DropdownMenu.Separator />
        {options.map((option) => (
          <DropdownMenu.CheckboxItem
            key={option}
            checked={selected.has(option)}
            // Keep the menu open while toggling several values.
            onSelect={(e) => e.preventDefault()}
            onCheckedChange={(checked) => toggle(option, checked)}
          >
            {renderLabel(option)}
          </DropdownMenu.CheckboxItem>
        ))}
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  );
}
