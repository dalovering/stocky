"use client";

import { Button, Flex, Text } from "@radix-ui/themes";
import { Pencil1Icon, TrashIcon } from "@radix-ui/react-icons";

import { PrintMenuButton } from "./PrintMenu";

/**
 * The contextual "N selected · Edit · Print · Delete · Clear" bar shown above the admin tables
 * when rows are selected. Identical on the users and inventory pages; only the print label and
 * the callbacks differ. When `onPrintToPrinter` is provided (label printer configured and
 * enabled), the print button becomes a destination menu; otherwise it stays a plain button.
 */
export function SelectionBar({
  count,
  onEdit,
  onPrint,
  onPrintToPrinter,
  printLabel = "Print",
  onDelete,
  onClear,
}: {
  count: number;
  onEdit: () => void;
  onPrint: () => void;
  onPrintToPrinter?: () => void;
  printLabel?: string;
  onDelete: () => void;
  onClear: () => void;
}) {
  if (count === 0) return null;
  return (
    <Flex
      mb="3"
      p="2"
      px="3"
      gap="3"
      align="center"
      style={{ background: "var(--accent-3)", borderRadius: 6 }}
    >
      <Text size="2" weight="medium">
        {count} selected
      </Text>
      <Button size="1" variant="soft" onClick={onEdit}>
        <Pencil1Icon /> Edit
      </Button>
      <PrintMenuButton
        label={printLabel}
        items={
          onPrintToPrinter
            ? [
                { label: "Print to label printer", onClick: onPrintToPrinter },
                { label: "Download PDF", onClick: onPrint },
              ]
            : [{ label: printLabel, onClick: onPrint }]
        }
      />
      <Button size="1" variant="soft" color="red" onClick={onDelete}>
        <TrashIcon /> Delete
      </Button>
      <Button size="1" variant="ghost" color="gray" onClick={onClear}>
        Clear
      </Button>
    </Flex>
  );
}
