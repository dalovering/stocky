"use client";

import { Badge, Button, Dialog, Flex, Heading, Separator, Text } from "@radix-ui/themes";

import { DialogHeader } from "@/components/Dialogs";
import type { ImportResult } from "@/lib/types";

/** Summarizes an xlsx import: per-action counts plus any per-row errors. */
export function ImportResultDialog({
  result,
  subject,
  onClose,
}: {
  result: ImportResult;
  subject: string;
  onClose: () => void;
}) {
  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="480px">
        <DialogHeader title={`Imported ${subject}`} />
        <Flex gap="2" mt="2" wrap="wrap">
          <Badge color="green">{result.created} created</Badge>
          <Badge color="blue">{result.updated} updated</Badge>
          <Badge color="red">{result.deleted} deleted</Badge>
          <Badge color="gray">{result.skipped} skipped</Badge>
        </Flex>
        {result.errors.length > 0 && (
          <>
            <Separator my="3" size="4" />
            <Heading size="2" mb="2" color="red">
              {result.errors.length} {result.errors.length === 1 ? "error" : "errors"}
            </Heading>
            <Flex direction="column" gap="1" style={{ maxHeight: 240, overflowY: "auto" }}>
              {result.errors.map((e, i) => (
                <Text key={i} size="1" color="gray">
                  Row {e.row}: {e.message}
                </Text>
              ))}
            </Flex>
          </>
        )}
        <Flex justify="end" mt="4">
          <Button onClick={onClose}>Done</Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
