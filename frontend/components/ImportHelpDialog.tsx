"use client";

import { useState } from "react";
import { Code, Dialog, Flex, IconButton, Table, Text, Tooltip } from "@radix-ui/themes";
import { QuestionMarkCircledIcon } from "@radix-ui/react-icons";

import { DialogHeader } from "@/components/Dialogs";

/**
 * The one place the spreadsheet import/export format is explained to admins. The copy mirrors
 * the backend's `services/spreadsheet.py` semantics — if that module changes (headers, action
 * behavior, matching rules), update this dialog in the same PR.
 */

const HEADERS: Record<"users" | "items", string> = {
  users: "action, id, barcode, name, group, status",
  items: "action, id, barcode, name, item_type, location, condition, needs_review",
};

const ACTIONS: { code: string; name: string; description: string }[] = [
  {
    code: "",
    name: "(blank)",
    description: "Row is ignored. Exports leave the column blank, so re-uploading changes nothing.",
  },
  {
    code: "C",
    name: "Create",
    description:
      "Creates a new record. Name is required; leave id blank. A blank barcode is auto-generated.",
  },
  {
    code: "U",
    name: "Update",
    description:
      "Updates the record matched by id (or barcode if id is blank). Only filled-in cells are " +
      "applied — except group/location, which are cleared when the column is present but empty.",
  },
  {
    code: "D",
    name: "Delete",
    description:
      "Deletes the record matched by id (or barcode). Deleting a user keeps their history, " +
      "without the name; deleting an item removes its history too.",
  },
];

export function ImportHelpDialog({ entity }: { entity: "users" | "items" }) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Tooltip content="How import/export works">
        <Dialog.Trigger>
          <IconButton variant="ghost" color="gray" aria-label="How import/export works">
            <QuestionMarkCircledIcon />
          </IconButton>
        </Dialog.Trigger>
      </Tooltip>
      <Dialog.Content maxWidth="560px">
        <DialogHeader title="Spreadsheet import & export" />
        <Flex direction="column" gap="3">
          <Text size="2">
            The download and the import use the same file format, so the workflow is: download,
            edit in Excel, set the <Code>action</Code> column on the rows you changed, and upload
            the file back. Columns for {entity}:
          </Text>
          <Code size="2">{HEADERS[entity]}</Code>

          <Table.Root size="1" variant="surface">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeaderCell style={{ width: 80 }}>action</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>What happens</Table.ColumnHeaderCell>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {ACTIONS.map((a) => (
                <Table.Row key={a.name}>
                  <Table.Cell>
                    <Text weight="medium">{a.code || "—"}</Text>
                  </Table.Cell>
                  <Table.Cell>
                    <Text size="1">
                      <Text weight="medium">{a.name}.</Text> {a.description}
                    </Text>
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>

          <Text size="1" color="gray">
            {entity === "users"
              ? "group and status are matched by name (e.g. an existing group's name, Active/Inactive)."
              : "item_type is matched by name and must already exist; condition accepts On order, " +
                "New, Good, Fair, Worn, Damaged; needs_review accepts true/false."}{" "}
            Any row that cannot be applied is reported with its spreadsheet row number after the
            upload — the other rows still go through. History and full-database downloads are
            export-only (no action column) and cannot be re-uploaded; their timestamps are in the
            configured app time zone.
          </Text>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
