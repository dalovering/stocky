"use client";

import { IconButton, TextField } from "@radix-ui/themes";
import { Cross2Icon, MagnifyingGlassIcon } from "@radix-ui/react-icons";

/**
 * The shared search input for the admin/inventory filter bars: a Radix TextField with a leading
 * magnifier and a trailing clear (×) button when non-empty. Controlled — the page owns the value
 * (so Reset/URL-sync are trivial); debounce filtering with `useDebouncedValue`, not here.
 */
export function SearchField({
  value,
  onChange,
  placeholder = "Search…",
  minWidth = 240,
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  minWidth?: number;
}) {
  return (
    <TextField.Root
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{ minWidth }}
    >
      <TextField.Slot>
        <MagnifyingGlassIcon height="16" width="16" />
      </TextField.Slot>
      {value && (
        <TextField.Slot side="right">
          <IconButton
            size="1"
            variant="ghost"
            color="gray"
            onClick={() => onChange("")}
            aria-label="Clear search"
          >
            <Cross2Icon height="14" width="14" />
          </IconButton>
        </TextField.Slot>
      )}
    </TextField.Root>
  );
}
