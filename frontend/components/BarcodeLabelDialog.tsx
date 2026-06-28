"use client";

// A dialog that previews a printable barcode label (user ID card or item tag) and prints it.
// The .print-area class (see globals.css) ensures only the label prints.

import { Button, Dialog, Flex, Text } from "@radix-ui/themes";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  subtitle?: string | null;
  barcodeValue: string;
  svgUrl: string;
  kind: "ID card" | "Item tag";
}

export function BarcodeLabelDialog({
  open,
  onOpenChange,
  title,
  subtitle,
  barcodeValue,
  svgUrl,
  kind,
}: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content maxWidth="420px">
        <Dialog.Title>{kind}</Dialog.Title>
        <div className="print-area">
          <Flex
            direction="column"
            align="center"
            gap="2"
            p="4"
            style={{ border: "1px solid var(--gray-6)", borderRadius: 8 }}
          >
            <Text size="5" weight="bold">
              {title}
            </Text>
            {subtitle && (
              <Text size="2" color="gray">
                {subtitle}
              </Text>
            )}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={svgUrl} alt={`Barcode ${barcodeValue}`} style={{ maxWidth: "100%" }} />
            <Text size="1" color="gray">
              {barcodeValue}
            </Text>
          </Flex>
        </div>
        <Flex gap="3" mt="4" justify="end" className="no-print">
          <Dialog.Close>
            <Button variant="soft" color="gray">
              Close
            </Button>
          </Dialog.Close>
          <Button onClick={() => window.print()}>Print</Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
