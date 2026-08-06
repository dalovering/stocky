"use client";

import type { ReactNode } from "react";
import { Button, DropdownMenu } from "@radix-ui/themes";
import { IdCardIcon } from "@radix-ui/react-icons";

/** One destination in a print menu ("Print to label printer", "Download PDF", …). */
export type PrintMenuItem = { label: string; onClick: () => void };

/**
 * The shared print control. With a single destination it renders the plain soft button
 * the app has always had (no visual change when the label printer is off/absent); with
 * several it renders the same button as a destination dropdown.
 */
export function PrintMenuButton({
  label,
  items,
  icon = <IdCardIcon />,
}: {
  label: string;
  items: PrintMenuItem[];
  icon?: ReactNode;
}) {
  if (items.length === 1) {
    return (
      <Button size="1" variant="soft" onClick={items[0].onClick}>
        {icon} {label}
      </Button>
    );
  }
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger>
        <Button size="1" variant="soft">
          {icon} {label}
          <DropdownMenu.TriggerIcon />
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Content size="1">
        {items.map((item) => (
          <DropdownMenu.Item key={item.label} onSelect={item.onClick}>
            {item.label}
          </DropdownMenu.Item>
        ))}
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  );
}
