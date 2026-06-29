"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Card,
  Dialog,
  Flex,
  Grid,
  Heading,
  IconButton,
  SegmentedControl,
  Select,
  Separator,
  Text,
  TextField,
} from "@radix-ui/themes";
import { PlusIcon } from "@radix-ui/react-icons";

import { AdminNav, AppShell, LogoutButton } from "@/components/AppShell";
import { BarcodeLabelDialog } from "@/components/BarcodeLabelDialog";
import { DataTable } from "@/components/DataTable";
import { ConfirmButton, DialogFooter, DialogHeader } from "@/components/Dialogs";
import { Field } from "@/components/Field";
import { HistoryList } from "@/components/HistoryList";
import { api } from "@/lib/api";
import type { Group, GroupTree, ItemEvent, UserDetail, UserRead } from "@/lib/types";

export default function UsersPage() {
  const [tree, setTree] = useState<GroupTree[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [view, setView] = useState<"table" | "cards">("table");
  const [q, setQ] = useState("");

  const [editUser, setEditUser] = useState<Partial<UserRead> | null>(null);
  const [detailUser, setDetailUser] = useState<UserDetail | null>(null);
  const [addGroupOpen, setAddGroupOpen] = useState(false);

  const loadGroups = useCallback(async () => {
    setTree(await api.groupTree());
    setGroups(await api.groups());
  }, []);

  const loadUsers = useCallback(async () => {
    setUsers(await api.users({ group_id: selectedGroup ?? undefined, q: q || undefined }));
  }, [selectedGroup, q]);

  useEffect(() => {
    loadGroups();
  }, [loadGroups]);
  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  return (
    <AppShell nav={<AdminNav />} actions={<LogoutButton />} title="Users &amp; Groups">
    <Grid columns={{ initial: "1", md: "260px 1fr" }} gap="5">
      {/* Group tree sidebar */}
      <Card>
        <Flex justify="between" align="center" mb="2">
          <Heading size="3">Groups</Heading>
          <IconButton size="1" variant="soft" onClick={() => setAddGroupOpen(true)}>
            <PlusIcon />
          </IconButton>
        </Flex>
        <Box>
          <GroupRow
            label="All users"
            active={selectedGroup === null}
            depth={0}
            onClick={() => setSelectedGroup(null)}
          />
          {tree.map((g) => (
            <GroupTreeNode
              key={g.id}
              node={g}
              depth={0}
              selected={selectedGroup}
              onSelect={setSelectedGroup}
            />
          ))}
        </Box>
      </Card>

      {/* Users panel */}
      <Box>
        <Flex justify="between" align="center" mb="3" gap="3" wrap="wrap">
          <TextField.Root
            placeholder="Search users…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ minWidth: 220 }}
          />
          <Flex gap="3" align="center">
            <SegmentedControl.Root
              value={view}
              onValueChange={(v) => setView(v as "table" | "cards")}
            >
              <SegmentedControl.Item value="table">Table</SegmentedControl.Item>
              <SegmentedControl.Item value="cards">Cards</SegmentedControl.Item>
            </SegmentedControl.Root>
            <Button onClick={() => setEditUser({ group_id: selectedGroup })}>
              <PlusIcon /> Add user
            </Button>
          </Flex>
        </Flex>

        {users.length === 0 ? (
          <Text color="gray">No users yet.</Text>
        ) : view === "table" ? (
          <UserTable users={users} onOpen={async (u) => setDetailUser(await api.user(u.id))} />
        ) : (
          <UserCards users={users} onOpen={async (u) => setDetailUser(await api.user(u.id))} />
        )}
      </Box>

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
          groups={groups}
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

      {addGroupOpen && (
        <GroupDialog
          groups={groups}
          defaultParent={selectedGroup}
          onClose={() => setAddGroupOpen(false)}
          onSaved={() => {
            setAddGroupOpen(false);
            loadGroups();
          }}
        />
      )}
    </Grid>
    </AppShell>
  );
}

function GroupRow({
  label,
  active,
  depth,
  count,
  onClick,
}: {
  label: string;
  active: boolean;
  depth: number;
  count?: number;
  onClick: () => void;
}) {
  return (
    <Flex
      className="clickable"
      align="center"
      justify="between"
      py="1"
      px="2"
      onClick={onClick}
      style={{
        paddingLeft: 8 + depth * 16,
        borderRadius: 6,
        background: active ? "var(--accent-4)" : undefined,
      }}
    >
      <Text size="2">{label}</Text>
      {count != null && (
        <Badge variant="soft" color="gray">
          {count}
        </Badge>
      )}
    </Flex>
  );
}

function GroupTreeNode({
  node,
  depth,
  selected,
  onSelect,
}: {
  node: GroupTree;
  depth: number;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <>
      <GroupRow
        label={node.name}
        active={selected === node.id}
        depth={depth}
        count={node.user_count}
        onClick={() => onSelect(node.id)}
      />
      {node.children.map((c) => (
        <GroupTreeNode
          key={c.id}
          node={c}
          depth={depth + 1}
          selected={selected}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}

function UserTable({ users, onOpen }: { users: UserRead[]; onOpen: (u: UserRead) => void }) {
  return (
    <DataTable
      rows={users}
      rowKey={(u) => u.id}
      onRowClick={onOpen}
      empty="No users yet."
      columns={[
        { header: "Name", cell: (u) => u.name },
        { header: "Group", cell: (u) => u.group_name ?? "—" },
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
    />
  );
}

function UserCards({ users, onOpen }: { users: UserRead[]; onOpen: (u: UserRead) => void }) {
  return (
    <Grid columns={{ initial: "1", sm: "2", lg: "3" }} gap="3">
      {users.map((u) => (
        <Card key={u.id} className="clickable" onClick={() => onOpen(u)}>
          <Heading size="3">{u.name}</Heading>
          <Text size="2" color="gray">
            {u.group_name ?? "No group"}
          </Text>
          <Flex mt="2" justify="between" align="center">
            <Text size="1" color="gray">
              {u.barcode}
            </Text>
            <Badge color={u.loan_count > 0 ? "blue" : "gray"}>{u.loan_count} on loan</Badge>
          </Flex>
        </Card>
      ))}
    </Grid>
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
  groups: Group[];
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
  groups,
  defaultParent,
  onClose,
  onSaved,
}: {
  groups: Group[];
  defaultParent: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState<string | null>(defaultParent);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      await api.createGroup({ name, parent_id: parentId });
      onSaved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="420px">
        <Dialog.Title>Add group</Dialog.Title>
        <Flex direction="column" gap="3" mt="2">
          <TextField.Root
            placeholder="Group name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
          <label>
            <Text size="2">Parent group</Text>
            <Select.Root
              value={parentId ?? "none"}
              onValueChange={(v) => setParentId(v === "none" ? null : v)}
            >
              <Select.Trigger style={{ width: "100%" }} />
              <Select.Content>
                <Select.Item value="none">Top level</Select.Item>
                {groups.map((g) => (
                  <Select.Item key={g.id} value={g.id}>
                    {g.name}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </label>
        </Flex>
        <DialogFooter onCancel={onClose} onSave={save} saveDisabled={busy || !name} />
      </Dialog.Content>
    </Dialog.Root>
  );
}
