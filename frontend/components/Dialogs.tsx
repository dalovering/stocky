"use client";

import type { ReactNode } from "react";
import { AlertDialog, Button, Dialog, Flex, IconButton } from "@radix-ui/themes";
import { Cross2Icon } from "@radix-ui/react-icons";

/** A dialog title row with a ghost close (✕) button, as used by every detail dialog. */
export function DialogHeader({ title }: { title: ReactNode }) {
  return (
    <Flex justify="between" align="start">
      <Dialog.Title>{title}</Dialog.Title>
      <Dialog.Close>
        <IconButton variant="ghost" color="gray">
          <Cross2Icon />
        </IconButton>
      </Dialog.Close>
    </Flex>
  );
}

/** The standard Cancel / Save footer for edit dialogs. */
export function DialogFooter({
  onCancel,
  onSave,
  saveDisabled,
  saveLabel = "Save",
}: {
  onCancel: () => void;
  onSave: () => void;
  saveDisabled?: boolean;
  saveLabel?: string;
}) {
  return (
    <Flex gap="3" mt="4" justify="end">
      <Button variant="soft" color="gray" onClick={onCancel}>
        Cancel
      </Button>
      <Button disabled={saveDisabled} onClick={onSave}>
        {saveLabel}
      </Button>
    </Flex>
  );
}

/**
 * A button that asks for confirmation via a Radix `AlertDialog` before running `onConfirm`.
 * Replaces native `window.confirm` so destructive actions use the same styled, scroll-locked
 * (no page shift) dialog as the rest of the app.
 */
export function ConfirmButton({
  label,
  title,
  description,
  confirmLabel = "Delete",
  onConfirm,
}: {
  label: string;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog.Root>
      <AlertDialog.Trigger>
        <Button size="1" variant="soft" color="red">
          {label}
        </Button>
      </AlertDialog.Trigger>
      <AlertDialog.Content maxWidth="420px">
        <AlertDialog.Title>{title}</AlertDialog.Title>
        <AlertDialog.Description size="2">{description}</AlertDialog.Description>
        <Flex gap="3" mt="4" justify="end">
          <AlertDialog.Cancel>
            <Button variant="soft" color="gray">
              Cancel
            </Button>
          </AlertDialog.Cancel>
          <AlertDialog.Action>
            <Button color="red" onClick={onConfirm}>
              {confirmLabel}
            </Button>
          </AlertDialog.Action>
        </Flex>
      </AlertDialog.Content>
    </AlertDialog.Root>
  );
}
