"use client";

// A select for free-text lookup values (location, manufacturer) that supports passively
// creating a new value: choosing "+ Add new…" swaps the dropdown for a text input, so the
// user can type a value that doesn't exist yet without leaving the form.

import { useState } from "react";
import { Button, Flex, Select, TextField } from "@radix-ui/themes";

const ADD_NEW = "__add_new__";
const NONE = "__none__";

interface Props {
  value: string | null;
  options: string[];
  onChange: (value: string | null) => void;
  placeholder?: string;
  allowNone?: boolean;
}

export function PassiveSelect({
  value,
  options,
  onChange,
  placeholder = "Type a new value",
  allowNone = true,
}: Props) {
  // Free-typing mode is active when the current value isn't one of the known options.
  const [typing, setTyping] = useState(value != null && !options.includes(value));

  if (typing) {
    return (
      <Flex gap="2" align="center">
        <TextField.Root
          style={{ flex: 1 }}
          placeholder={placeholder}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value || null)}
          autoFocus
        />
        <Button
          type="button"
          variant="soft"
          color="gray"
          onClick={() => {
            setTyping(false);
            onChange(null);
          }}
        >
          Pick existing
        </Button>
      </Flex>
    );
  }

  return (
    <Select.Root
      value={value ?? NONE}
      onValueChange={(v) => {
        if (v === ADD_NEW) {
          setTyping(true);
          onChange(null);
        } else if (v === NONE) {
          onChange(null);
        } else {
          onChange(v);
        }
      }}
    >
      <Select.Trigger style={{ width: "100%" }} placeholder="Select…" />
      <Select.Content>
        {allowNone && <Select.Item value={NONE}>None</Select.Item>}
        {options.map((o) => (
          <Select.Item key={o} value={o}>
            {o}
          </Select.Item>
        ))}
        <Select.Separator />
        <Select.Item value={ADD_NEW}>+ Add new…</Select.Item>
      </Select.Content>
    </Select.Root>
  );
}
