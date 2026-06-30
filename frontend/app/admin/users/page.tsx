"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Button,
  Callout,
  Dialog,
  Flex,
  Heading,
  Select,
  Separator,
  Text,
  TextField,
} from "@radix-ui/themes";
import { EyeOpenIcon, IdCardIcon, Pencil1Icon, PlusIcon, TrashIcon } from "@radix-ui/react-icons";

import { AppShell } from "@/components/AppShell";
import { ConfirmButton, ConfirmDialog, DialogFooter, DialogHeader } from "@/components/Dialogs";
import { Field } from "@/components/Field";
import { GroupedTable, type GroupNode } from "@/components/GroupedTable";
import { HistoryList, StatusBadge } from "@/components/HistoryList";
import { ImportExportButtons } from "@/components/ImportExportButtons";
import { ImportResultDialog } from "@/components/ImportResultDialog";
import { MultiSelectFilter } from "@/components/MultiSelectFilter";
import { SelectionBar } from "@/components/SelectionBar";
import { useSelection } from "@/hooks/useSelection";
import { api, ApiError, downloadBlob } from "@/lib/api";
import { USER_STATUSES } from "@/lib/types";
import type {
  Group,
  GroupTree,
  ImportResult,
  ItemEvent,
  UserDetail,
  UserRead,
  UserStatus,
} from "@/lib/types";

const UNGROUPED = "__ungrouped__";
const UNCHANGED = "__unchanged__";
const NONE = "__none__";
const NEW_GROUP = "__new_group__";

const plural = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;

type DeleteTarget = { kind: "user" | "group"; id: string; name: string };

export default function UsersPage() {
  const [tree, setTree] = useState<GroupTree[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [q, setQ] = useState("");
  const [statusSel, setStatusSel] = useState<Set<UserStatus>>(new Set(["Active"]));

  const { selected, toggleOne, toggleMany, clear: clearSelection } = useSelection();
  const [editUser, setEditUser] = useState<Partial<UserRead> | null>(null);
  const [detailUser, setDetailUser] = useState<UserDetail | null>(null);
  const [editGroup, setEditGroup] = useState<Partial<Group> | null>(null);
  const [batchOpen, setBatchOpen] = useState(false);
  const [del, setDel] = useState<DeleteTarget | null>(null);
  const [batchDelete, setBatchDelete] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadGroups = useCallback(async () => {
    setTree(await api.groupTree());
    setGroups(await api.groups());
  }, []);
  const loadUsers = useCallback(async () => {
    setUsers(await api.users());
  }, []);

  useEffect(() => {
    loadGroups();
  }, [loadGroups]);
  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const openDetail = async (u: UserRead) => setDetailUser(await api.user(u.id));

  async function download(blobPromise: Promise<Blob>, filename: string) {
    try {
      downloadBlob(await blobPromise, filename);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Download failed.");
    }
  }

  // Bucket the (filtered) users by their group, then nest into the group tree.
  const usersByGroup = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const m = new Map<string, UserRead[]>();
    for (const u of users) {
      if (!statusSel.has(u.status)) continue;
      if (needle) {
        const hay = `${u.name} ${u.group_name ?? ""} ${u.barcode}`;
        if (!hay.toLowerCase().includes(needle)) continue;
      }
      const key = u.group_id ?? UNGROUPED;
      const list = m.get(key);
      if (list) list.push(u);
      else m.set(key, [u]);
    }
    return m;
  }, [users, q, statusSel]);

  const groupNodes = useMemo<GroupNode<UserRead>[]>(() => {
    const rollup = (node: GroupTree): number =>
      (usersByGroup.get(node.id)?.length ?? 0) + node.children.reduce((s, c) => s + rollup(c), 0);

    const toNode = (node: GroupTree): GroupNode<UserRead> => ({
      id: node.id,
      title: node.name,
      meta: plural(rollup(node), "user"),
      actions: [
        {
          icon: <PlusIcon />,
          label: "Add subgroup",
          onClick: () => setEditGroup({ parent_id: node.id }),
        },
        {
          icon: <IdCardIcon />,
          label: "Print all ID cards",
          onClick: () => download(api.groupIdCardsPdf(node.id), `id-cards-${node.name}.pdf`),
        },
        { icon: <Pencil1Icon />, label: "Edit group", onClick: () => setEditGroup(node) },
        {
          icon: <TrashIcon />,
          label: "Delete group",
          color: "red",
          onClick: () => setDel({ kind: "group", id: node.id, name: node.name }),
        },
      ],
      children: node.children.map(toNode),
      rows: usersByGroup.get(node.id) ?? [],
    });

    const nodes = tree.map(toNode);
    const ungrouped = usersByGroup.get(UNGROUPED) ?? [];
    if (ungrouped.length > 0) {
      nodes.push({
        id: UNGROUPED,
        title: "Ungrouped",
        meta: plural(ungrouped.length, "user"),
        rows: ungrouped,
        children: [],
      });
    }
    return nodes;
  }, [tree, usersByGroup]);

  async function confirmDelete() {
    if (!del) return;
    const target = del;
    setDel(null);
    try {
      if (target.kind === "user") await api.deleteUser(target.id);
      else await api.deleteGroup(target.id);
      loadUsers();
      loadGroups();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed.");
    }
  }

  async function confirmBatchDelete() {
    setBatchDelete(false);
    try {
      await api.batchDeleteUsers([...selected]);
      clearSelection();
      loadUsers();
      loadGroups();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed.");
    }
  }

  return (
    <AppShell>
      <Flex mb="3" gap="3" justify="between" align="center" wrap="wrap">
        <Flex gap="2" align="center" wrap="wrap">
          <TextField.Root
            placeholder="Search name, group, barcode…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ minWidth: 240 }}
          />
          <MultiSelectFilter
            label="Status"
            options={USER_STATUSES}
            selected={statusSel}
            onChange={setStatusSel}
          />
        </Flex>
        <Flex gap="2" wrap="wrap">
          <ImportExportButtons
            exportName="stocky-users.xlsx"
            onExport={api.usersXlsx}
            onImport={api.importUsers}
            onImported={(r) => {
              setImportResult(r);
              loadUsers();
              loadGroups();
            }}
            onError={setError}
          />
          <Button variant="soft" onClick={() => setEditGroup({})}>
            <PlusIcon /> Group
          </Button>
          <Button onClick={() => setEditUser({})}>
            <PlusIcon /> User
          </Button>
        </Flex>
      </Flex>

      {error && (
        <Callout.Root color="red" mb="3" role="alert">
          <Callout.Text>{error}</Callout.Text>
        </Callout.Root>
      )}

      <SelectionBar
        count={selected.size}
        onEdit={() => setBatchOpen(true)}
        onPrint={() => download(api.usersIdCardsPdf([...selected]), "id-cards.pdf")}
        printLabel="Print ID cards"
        onDelete={() => setBatchDelete(true)}
        onClear={clearSelection}
      />

      <GroupedTable
        groups={groupNodes}
        rowKey={(u) => u.id}
        empty="No groups or users yet."
        selectable
        selectedIds={selected}
        onToggle={toggleOne}
        onToggleMany={toggleMany}
        columns={[
          { header: "Name", cell: (u) => u.name },
          { header: "Status", cell: (u) => <StatusBadge status={u.status} /> },
          {
            header: "Barcode",
            cell: (u) => (
              <Text size="1" color="gray">
                {u.barcode}
              </Text>
            ),
          },
          { header: "On loan", cell: (u) => u.loan_count },
        ]}
        rowActions={(u) => [
          { icon: <EyeOpenIcon />, label: "View", onClick: () => openDetail(u) },
          { icon: <Pencil1Icon />, label: "Edit", onClick: () => setEditUser(u) },
          {
            icon: <IdCardIcon />,
            label: "Print ID card",
            onClick: () => download(api.userIdCardPdf(u.id), `id-card-${u.barcode}.pdf`),
          },
          {
            icon: <TrashIcon />,
            label: "Delete",
            color: "red",
            onClick: () => setDel({ kind: "user", id: u.id, name: u.name }),
          },
        ]}
      />

      {editUser && (
        <UserDialog
          user={editUser}
          groups={groups}
          onClose={() => setEditUser(null)}
          onSaved={() => {
            setEditUser(null);
            loadUsers();
            loadGroups();
          }}
        />
      )}

      {detailUser && (
        <UserDetailDialog
          user={detailUser}
          onClose={() => setDetailUser(null)}
          onChanged={(u) => {
            setDetailUser(u);
            loadUsers();
          }}
          onEdit={(u) => {
            setDetailUser(null);
            setEditUser(u);
          }}
          onPrint={() =>
            download(api.userIdCardPdf(detailUser.id), `id-card-${detailUser.barcode}.pdf`)
          }
        />
      )}

      {editGroup && (
        <GroupDialog
          group={editGroup}
          groups={groups}
          onClose={() => setEditGroup(null)}
          onSaved={() => {
            setEditGroup(null);
            loadGroups();
          }}
        />
      )}

      {batchOpen && (
        <UserBatchDialog
          ids={[...selected]}
          groups={groups}
          onClose={() => setBatchOpen(false)}
          onSaved={() => {
            setBatchOpen(false);
            clearSelection();
            loadUsers();
            loadGroups();
          }}
        />
      )}

      {importResult && (
        <ImportResultDialog
          result={importResult}
          subject="users"
          onClose={() => setImportResult(null)}
        />
      )}

      <ConfirmDialog
        open={del !== null}
        onOpenChange={(o) => !o && setDel(null)}
        title={del ? `Delete ${del.name}?` : ""}
        description={
          del?.kind === "group"
            ? "This deletes the group. It must have no subgroups or members first."
            : "This removes the user and their history. This cannot be undone."
        }
        onConfirm={confirmDelete}
      />

      <ConfirmDialog
        open={batchDelete}
        onOpenChange={(o) => !o && setBatchDelete(false)}
        title={`Delete ${selected.size} ${selected.size === 1 ? "user" : "users"}?`}
        description="This removes the selected users. Their history is preserved without a name."
        onConfirm={confirmBatchDelete}
      />
    </AppShell>
  );
}

function UserBatchDialog({
  ids,
  groups,
  onClose,
  onSaved,
}: {
  ids: string[];
  groups: Group[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [groupChoice, setGroupChoice] = useState(UNCHANGED);
  const [newGroupName, setNewGroupName] = useState("");
  const [status, setStatus] = useState<string>(UNCHANGED);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const patch: { group_id?: string | null; status?: UserStatus } = {};
      if (groupChoice === NEW_GROUP) {
        const group = await api.createGroup({ name: newGroupName });
        patch.group_id = group.id;
      } else if (groupChoice === NONE) {
        patch.group_id = null;
      } else if (groupChoice !== UNCHANGED) {
        patch.group_id = groupChoice;
      }
      if (status !== UNCHANGED) patch.status = status as UserStatus;
      if (Object.keys(patch).length > 0) await api.batchUpdateUsers(ids, patch);
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not apply changes.");
    } finally {
      setBusy(false);
    }
  }

  const needsName = groupChoice === NEW_GROUP && !newGroupName.trim();

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="440px">
        <Dialog.Title>
          Edit {ids.length} {ids.length === 1 ? "user" : "users"}
        </Dialog.Title>
        <Text size="2" color="gray">
          Only the fields you change are applied to every selected user.
        </Text>
        {error && (
          <Callout.Root color="red" mt="3" role="alert">
            <Callout.Text>{error}</Callout.Text>
          </Callout.Root>
        )}
        <Flex direction="column" gap="3" mt="3">
          <Field label="Move to group">
            <Select.Root value={groupChoice} onValueChange={setGroupChoice}>
              <Select.Trigger style={{ width: "100%" }} />
              <Select.Content>
                <Select.Item value={UNCHANGED}>Leave unchanged</Select.Item>
                <Select.Item value={NONE}>No group</Select.Item>
                {groups.map((g) => (
                  <Select.Item key={g.id} value={g.id}>
                    {g.name}
                  </Select.Item>
                ))}
                <Select.Separator />
                <Select.Item value={NEW_GROUP}>+ New group…</Select.Item>
              </Select.Content>
            </Select.Root>
          </Field>
          {groupChoice === NEW_GROUP && (
            <Field label="New group name">
              <TextField.Root
                value={newGroupName}
                onChange={(e) => setNewGroupName(e.target.value)}
                placeholder="e.g. Room 7"
                autoFocus
              />
            </Field>
          )}
          <Field label="Set status">
            <Select.Root value={status} onValueChange={setStatus}>
              <Select.Trigger style={{ width: "100%" }} />
              <Select.Content>
                <Select.Item value={UNCHANGED}>Leave unchanged</Select.Item>
                <Select.Item value="Active">Active</Select.Item>
                <Select.Item value="Inactive">Inactive</Select.Item>
              </Select.Content>
            </Select.Root>
          </Field>
        </Flex>
        <DialogFooter
          onCancel={onClose}
          onSave={save}
          saveDisabled={busy || needsName}
          saveLabel="Apply"
        />
      </Dialog.Content>
    </Dialog.Root>
  );
}

function UserDialog({
  user,
  groups,
  onClose,
  onSaved,
}: {
  user: Partial<UserRead>;
  groups: Group[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = Boolean(user.id);
  const [name, setName] = useState(user.name ?? "");
  const [groupId, setGroupId] = useState<string | null>(user.group_id ?? null);
  const [status, setStatus] = useState<UserStatus>(user.status ?? "Active");
  const [barcode, setBarcode] = useState(user.barcode ?? "");
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      if (isEdit) {
        await api.updateUser(user.id!, {
          name,
          group_id: groupId,
          status,
          ...(barcode ? { barcode } : {}),
        });
      } else {
        await api.createUser({ name, group_id: groupId, status, barcode: barcode || null });
      }
      onSaved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="440px">
        <Dialog.Title>{isEdit ? "Edit user" : "Add user"}</Dialog.Title>
        <Flex direction="column" gap="3" mt="2">
          <Field label="Name">
            <TextField.Root value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </Field>
          <Field label="Group">
            <Select.Root
              value={groupId ?? "none"}
              onValueChange={(v) => setGroupId(v === "none" ? null : v)}
            >
              <Select.Trigger style={{ width: "100%" }} />
              <Select.Content>
                <Select.Item value="none">No group</Select.Item>
                {groups.map((g) => (
                  <Select.Item key={g.id} value={g.id}>
                    {g.name}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </Field>
          <Field label="Status">
            <Select.Root value={status} onValueChange={(v) => setStatus(v as UserStatus)}>
              <Select.Trigger style={{ width: "100%" }} />
              <Select.Content>
                <Select.Item value="Active">Active</Select.Item>
                <Select.Item value="Inactive">Inactive</Select.Item>
              </Select.Content>
            </Select.Root>
          </Field>
          <Field label="Barcode" hint={isEdit ? undefined : "(blank = auto-generate)"}>
            <TextField.Root
              value={barcode}
              onChange={(e) => setBarcode(e.target.value)}
              placeholder="Scan or type to register an existing card"
            />
          </Field>
        </Flex>
        <DialogFooter onCancel={onClose} onSave={save} saveDisabled={busy || !name} />
      </Dialog.Content>
    </Dialog.Root>
  );
}

function UserDetailDialog({
  user,
  onClose,
  onChanged,
  onEdit,
  onPrint,
}: {
  user: UserDetail;
  onClose: () => void;
  onChanged: (u: UserDetail) => void;
  onEdit: (u: UserRead) => void;
  onPrint: () => void;
}) {
  const [events, setEvents] = useState<ItemEvent[]>([]);

  useEffect(() => {
    api.userEvents(user.id).then(setEvents);
  }, [user.id]);

  async function regenerate() {
    onChanged(await api.regenerateUserBarcode(user.id));
  }

  async function remove() {
    await api.deleteUser(user.id);
    onClose();
  }

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="560px">
        <DialogHeader title={user.name} />
        <Flex gap="2" align="center">
          <StatusBadge status={user.status} />
          <Text size="2" color="gray">
            {user.group_name ?? "No group"} · {user.barcode}
          </Text>
        </Flex>

        <Flex gap="2" mt="3" wrap="wrap">
          <Button size="1" variant="soft" onClick={() => onEdit(user)}>
            Edit
          </Button>
          <Button size="1" variant="soft" onClick={onPrint}>
            Print ID card
          </Button>
          <Button size="1" variant="soft" onClick={regenerate}>
            Regenerate barcode
          </Button>
          <ConfirmButton
            label="Delete"
            title={`Delete ${user.name}?`}
            description="This removes the user. Their history is preserved without a name."
            onConfirm={remove}
          />
        </Flex>

        <Separator my="4" size="4" />
        <Heading size="3" mb="2">
          Current loans ({user.current_loans.length})
        </Heading>
        {user.current_loans.length === 0 ? (
          <Text color="gray" size="2">
            Nothing checked out.
          </Text>
        ) : (
          <Flex direction="column" gap="1">
            {user.current_loans.map((i) => (
              <Text key={i.id} size="2">
                • {i.name} {i.location ? `(${i.location})` : ""}
              </Text>
            ))}
          </Flex>
        )}

        <Separator my="4" size="4" />
        <Heading size="3" mb="2">
          History
        </Heading>
        <HistoryList events={events} subject="user" />
      </Dialog.Content>
    </Dialog.Root>
  );
}

function GroupDialog({
  group,
  groups,
  onClose,
  onSaved,
}: {
  group: Partial<Group>;
  groups: Group[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = Boolean(group.id);
  const [name, setName] = useState(group.name ?? "");
  const [parentId, setParentId] = useState<string | null>(group.parent_id ?? null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      if (isEdit) await api.updateGroup(group.id!, { name, parent_id: parentId });
      else await api.createGroup({ name, parent_id: parentId });
      onSaved();
    } finally {
      setBusy(false);
    }
  }

  // A group can't be its own parent; exclude self from the options when editing.
  const parentOptions = groups.filter((g) => g.id !== group.id);

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="420px">
        <Dialog.Title>{isEdit ? "Edit group" : "Add group"}</Dialog.Title>
        <Flex direction="column" gap="3" mt="2">
          <Field label="Name">
            <TextField.Root value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </Field>
          <Field label="Parent group">
            <Select.Root
              value={parentId ?? "none"}
              onValueChange={(v) => setParentId(v === "none" ? null : v)}
            >
              <Select.Trigger style={{ width: "100%" }} />
              <Select.Content>
                <Select.Item value="none">Top level</Select.Item>
                {parentOptions.map((g) => (
                  <Select.Item key={g.id} value={g.id}>
                    {g.name}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </Field>
        </Flex>
        <DialogFooter onCancel={onClose} onSave={save} saveDisabled={busy || !name} />
      </Dialog.Content>
    </Dialog.Root>
  );
}
