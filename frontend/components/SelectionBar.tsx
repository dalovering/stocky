"use client";

import { Button, Flex, Text } from "@radix-ui/themes";
import { IdCardIcon, Pencil1Icon, TrashIcon } from "@radix-ui/react-icons";

/**
 * The contextual "N selected · Edit · Print · Delete · Clear" bar shown above the admin tables
 * when rows are selected. Identical on the users and inventory pages; only the print label and
 * the callbacks differ.
 */
export function SelectionBar({
  count,
  onEdit,
  onPrint,
  printLabel = "Print",
  onDelete,
  onClear,
}: {
  count: number;
  onEdit: () => void;
  onPrint: () => void;
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
      <Button size="1" variant="soft" onClick={onPrint}>
        <IdCardIcon /> {printLabel}
      </Button>
      <Button size="1" variant="soft" color="red" onClick={onDelete}>
        <TrashIcon /> Delete
      </Button>
      <Button size="1" variant="ghost" color="gray" onClick={onClear}>
        Clear
      </Button>
    </Flex>
  );
}
