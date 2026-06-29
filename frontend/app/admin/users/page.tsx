"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Callout, Dialog, Flex, Heading, Select, Separator, Text, TextField } from "@radix-ui/themes";
import { EyeOpenIcon, IdCardIcon, Pencil1Icon, PlusIcon, TrashIcon } from "@radix-ui/react-icons";

import { AdminNav, AppShell, LogoutButton } from "@/components/AppShell";
import { BarcodeLabelDialog } from "@/components/BarcodeLabelDialog";
import { ConfirmButton, ConfirmDialog, DialogFooter, DialogHeader } from "@/components/Dialogs";
import { Field } from "@/components/Field";
import { GroupedTable, type GroupNode } from "@/components/GroupedTable";
import { HistoryList } from "@/components/HistoryList";
import { api, ApiError } from "@/lib/api";
import type { Group, GroupTree, ItemEvent, UserDetail, UserRead } from "@/lib/types";

const UNGROUPED = "__ungrouped__";

type DeleteTarget = { kind: "user" | "group"; id: string; name: string };

export default function UsersPage() {
  const [tree, setTree] = useState<GroupTree[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [q, setQ] = useState("");

  const [editUser, setEditUser] = useState<Partial<UserRead> | null>(null);
  const [detailUser, setDetailUser] = useState<UserDetail | null>(null);
  const [editGroup, setEditGroup] = useState<Partial<Group> | null>(null);
  const [printUser, setPrintUser] = useState<UserRead | null>(null);
  const [del, setDel] = useState<DeleteTarget | null>(null);
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

  // Bucket the (name-filtered) users by their group, then nest them into the group tree. The
  // backend's group filter is exact (no rollup), so the nesting and rolled-up counts are derived
  // here from the full user list + the tree.
  const usersByGroup = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const m = new Map<string, UserRead[]>();
    for (const u of users) {
      if (needle && !u.name.toLowerCase().includes(needle)) continue;
      const key = u.group_id ?? UNGROUPED;
      const list = m.get(key);
      if (list) list.push(u);
      else m.set(key, [u]);
    }
    return m;
  }, [users, q]);

  const groupNodes = useMemo<GroupNode<UserRead>[]>(() => {
    const rollup = (node: GroupTree): number =>
      (usersByGroup.get(node.id)?.length ?? 0) + node.children.reduce((s, c) => s + rollup(c), 0);

    const toNode = (node: GroupTree): GroupNode<UserRead> => ({
      id: node.id,
      title: node.name,
      meta: `${rollup(node)} users`,
      actions: [
        {
          icon: <PlusIcon />,
          label: "Add subgroup",
          onClick: () => setEditGroup({ parent_id: node.id }),
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
      nodes.push({ id: UNGROUPED, title: "Ungrouped", meta: `${ungrouped.length} users`, rows: ungrouped, children: [] });
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

  return (
    <AppShell
      nav={<AdminNav />}
      actions={<LogoutButton />}
      title="Users &amp; Groups"
      action={
        <Flex gap="3">
          <Button variant="soft" onClick={() => setEditGroup({})}>
            <PlusIcon /> Add group
          </Button>
          <Button onClick={() => setEditUser({})}>
            <PlusIcon /> Add user
          </Button>
        </Flex>
      }
    >
      <Flex mb="3" gap="3" wrap="wrap">
        <TextField.Root
          placeholder="Search users…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ minWidth: 220 }}
        />
      </Flex>

      {error && (
        <Callout.Root color="red" mb="3" role="alert">
          <Callout.Text>{error}</Callout.Text>
        </Callout.Root>
      )}

      <GroupedTable
        groups={groupNodes}
        rowKey={(u) => u.id}
        empty="No groups or users yet."
        columns={[
          { header: "Name", cell: (u) => u.name },
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
          { icon: <IdCardIcon />, label: "Print ID card", onClick: () => setPrintUser(u) },
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

      {printUser && (
        <BarcodeLabelDialog
          open
          onOpenChange={(o) => !o && setPrintUser(null)}
          kind="ID card"
          title={printUser.name}
          subtitle={printUser.group_name}
          barcodeValue={printUser.barcode}
          svgUrl={api.userBarcodeSvg(printUser.id)}
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
    </AppShell>
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
  const [barcode, setBarcode] = useState(user.barcode ?? "");
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      if (isEdit) {
        await api.updateUser(user.id!, {
          name,
          group_id: groupId,
          ...(barcode ? { barcode } : {}),
        });
      } else {
        await api.createUser({ name, group_id: groupId, barcode: barcode || null });
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
}: {
  user: UserDetail;
  onClose: () => void;
  onChanged: (u: UserDetail) => void;
  onEdit: (u: UserRead) => void;
}) {
  const [events, setEvents] = useState<ItemEvent[]>([]);
  const [printOpen, setPrintOpen] = useState(false);

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
        <Text size="2" color="gray">
          {user.group_name ?? "No group"} · {user.barcode}
        </Text>

        <Flex gap="2" mt="3" wrap="wrap">
          <Button size="1" variant="soft" onClick={() => onEdit(user)}>
            Edit
          </Button>
          <Button size="1" variant="soft" onClick={() => setPrintOpen(true)}>
            Print ID card
          </Button>
          <Button size="1" variant="soft" onClick={regenerate}>
            Regenerate barcode
          </Button>
          <ConfirmButton
            label="Delete"
            title={`Delete ${user.name}?`}
            description="This removes the user and their history. This cannot be undone."
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
        <HistoryList events={events} />

        <BarcodeLabelDialog
          open={printOpen}
          onOpenChange={setPrintOpen}
          kind="ID card"
          title={user.name}
          subtitle={user.group_name}
          barcodeValue={user.barcode}
          svgUrl={api.userBarcodeSvg(user.id)}
        />
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
