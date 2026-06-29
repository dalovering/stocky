"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Box,
  Button,
  Callout,
  Card,
  Dialog,
  Flex,
  Grid,
  Heading,
  Separator,
  Text,
  TextArea,
  TextField,
} from "@radix-ui/themes";

import { AppShell } from "@/components/AppShell";
import { BarcodeScannerProvider } from "@/components/BarcodeScannerProvider";
import { HistoryList, StatusBadge } from "@/components/HistoryList";
import { api, ApiError } from "@/lib/api";
import type { Item, ItemEvent, UserDetail } from "@/lib/types";

// Auto-logout after this many ms of inactivity at the kiosk.
const IDLE_MS = 60_000;

/** A rough "how long ago" label for a checkout timestamp (e.g. "3 days", "2 hours"). */
function loanDuration(since: string): string {
  const mins = Math.floor((Date.now() - new Date(since).getTime()) / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"}`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"}`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"}`;
}

type Toast = { kind: "info" | "error"; text: string } | null;

/** A compact transient banner for scan results; sized to sit inline within a header row. */
function ToastCallout({ toast }: { toast: NonNullable<Toast> }) {
  return (
    <Callout.Root size="1" color={toast.kind === "error" ? "red" : "teal"}>
      <Callout.Text>{toast.text}</Callout.Text>
    </Callout.Root>
  );
}

export default function KioskPage() {
  const [user, setUser] = useState<UserDetail | null>(null);
  const [events, setEvents] = useState<ItemEvent[]>([]);
  const [toast, setToast] = useState<Toast>(null);
  const [modalItem, setModalItem] = useState<Item | null>(null);
  const [manual, setManual] = useState("");

  const userRef = useRef<UserDetail | null>(null);
  useEffect(() => {
    userRef.current = user;
  });
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flash = useCallback((t: Toast) => {
    setToast(t);
    if (t) setTimeout(() => setToast(null), 3500);
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setEvents([]);
    setModalItem(null);
  }, []);

  const loadEvents = useCallback(async (id: string) => {
    setEvents(await api.kioskUserEvents(id));
  }, []);

  const resetIdle = useCallback(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => {
      if (userRef.current) {
        logout();
        flash({ kind: "info", text: "Logged out due to inactivity." });
      }
    }, IDLE_MS);
  }, [logout, flash]);

  const refreshUser = useCallback(async () => {
    const id = userRef.current?.id;
    if (!id) return;
    const [u, ev] = await Promise.all([api.kioskUser(id), api.kioskUserEvents(id)]);
    setUser(u);
    setEvents(ev);
  }, []);

  const handleScan = useCallback(
    async (code: string) => {
      resetIdle();
      try {
        const resp = await api.scan(code, userRef.current?.id ?? null);
        switch (resp.action) {
          case "login":
            setUser(resp.user);
            setModalItem(null);
            flash({ kind: "info", text: resp.message });
            if (resp.user) await loadEvents(resp.user.id);
            break;
          case "checked_out":
          case "checked_in":
            flash({ kind: "info", text: resp.message });
            await refreshUser();
            break;
          case "open_modal":
            if (resp.item) setModalItem(resp.item);
            flash({ kind: "info", text: resp.message });
            break;
          case "unknown":
            flash({ kind: "error", text: resp.message });
            break;
        }
      } catch (err) {
        flash({ kind: "error", text: err instanceof ApiError ? err.message : "Scan failed." });
      }
    },
    [flash, loadEvents, refreshUser, resetIdle],
  );

  useEffect(() => {
    resetIdle();
    return () => {
      if (idleTimer.current) clearTimeout(idleTimer.current);
    };
  }, [resetIdle, user]);

  return (
    <AppShell containerSize="3">
      {/* Global scanner — works with no input focused. */}
      <BarcodeScannerProvider onScan={handleScan} />

      {!user ? (
        <IdlePrompt manual={manual} setManual={setManual} onSubmit={handleScan} toast={toast} />
      ) : (
        <UserPanel
          user={user}
          events={events}
          toast={toast}
          onOpenItem={setModalItem}
          onComplete={() => {
            logout();
            flash({ kind: "info", text: "Session complete." });
          }}
        />
      )}

      {modalItem && user && (
        <ItemActionModal
          item={modalItem}
          user={user}
          onClose={() => setModalItem(null)}
          onActed={async (msg) => {
            setModalItem(null);
            flash({ kind: "info", text: msg });
            await refreshUser();
          }}
          onError={(msg) => flash({ kind: "error", text: msg })}
        />
      )}
    </AppShell>
  );
}

function IdlePrompt({
  manual,
  setManual,
  onSubmit,
  toast,
}: {
  manual: string;
  setManual: (v: string) => void;
  onSubmit: (code: string) => void;
  toast: Toast;
}) {
  return (
    <Card size="4">
      <Flex direction="column" align="center" gap="4" py="6">
        <Heading size="6">Scan your ID card to begin</Heading>
        {toast && <ToastCallout toast={toast} />}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (manual.trim()) {
              onSubmit(manual.trim());
              setManual("");
            }
          }}
        >
          <Flex gap="2">
            <TextField.Root
              placeholder="…or type your ID number"
              value={manual}
              onChange={(e) => setManual(e.target.value)}
              style={{ minWidth: 280 }}
            />
            <Button type="submit">Go</Button>
          </Flex>
        </form>
      </Flex>
    </Card>
  );
}

function UserPanel({
  user,
  events,
  toast,
  onOpenItem,
  onComplete,
}: {
  user: UserDetail;
  events: ItemEvent[];
  toast: Toast;
  onOpenItem: (i: Item) => void;
  onComplete: () => void;
}) {
  return (
    <Box>
      {/* The username sits left, Complete sits right; the toast pops up in the centered gap so a
          scan result doesn't shift the items list below it. */}
      <Flex justify="between" align="center" mb="3" gap="3">
        <Box>
          <Heading size="6">{user.name}</Heading>
          <Text color="gray">{user.group_name ?? "No group"}</Text>
        </Box>
        {toast && <ToastCallout toast={toast} />}
        <Button size="3" onClick={onComplete}>
          Complete
        </Button>
      </Flex>

      <Heading size="4" mb="2">
        Items on loan ({user.current_loans.length})
      </Heading>
      {user.current_loans.length === 0 ? (
        <Callout.Root color="gray">
          <Callout.Text>
            Nothing checked out. Scan an item to check it out, or scan another ID to switch users.
          </Callout.Text>
        </Callout.Root>
      ) : (
        <Grid columns={{ initial: "1", sm: "2" }} gap="3">
          {user.current_loans.map((i) => (
            <Card key={i.id} className="clickable" onClick={() => onOpenItem(i)}>
              <Flex justify="between" align="start" gap="2">
                <Box>
                  <Heading size="3">{i.name}</Heading>
                  <Text size="2" color="gray" as="div">
                    {i.item_type_name} {i.location ? `· ${i.location}` : ""}
                  </Text>
                  {i.checked_out_at && (
                    <Text size="1" color="gray" as="div" mt="1">
                      On loan {loanDuration(i.checked_out_at)} · since{" "}
                      {new Date(i.checked_out_at).toLocaleString()}
                    </Text>
                  )}
                </Box>
                <StatusBadge status={i.status} />
              </Flex>
            </Card>
          ))}
        </Grid>
      )}

      <Text size="2" color="gray" mt="4" as="p">
        Scan an item barcode to check it in or out automatically.
      </Text>

      <Separator my="4" size="4" />
      <Heading size="4" mb="2">
        History
      </Heading>
      {/* Already sorted most-recent-first by the backend. */}
      <HistoryList events={events} subject="user" />
    </Box>
  );
}

function ItemActionModal({
  item,
  user,
  onClose,
  onActed,
  onError,
}: {
  item: Item;
  user: UserDetail;
  onClose: () => void;
  onActed: (message: string) => void;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  // When set, the modal shows a note field to accompany a damage/loss report.
  const [reporting, setReporting] = useState<"damage" | "loss" | null>(null);
  const [note, setNote] = useState("");
  const heldByThisUser = item.holder_user_id === user.id;
  const heldByOther = item.holder_user_id != null && !heldByThisUser;

  async function run(fn: () => Promise<unknown>, message: string) {
    setBusy(true);
    try {
      await fn();
      onActed(message);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content maxWidth="440px">
        <Dialog.Title>{item.name}</Dialog.Title>
        <Flex gap="2" align="center" mb="2">
          <StatusBadge status={item.status} />
          <Text size="2" color="gray">
            {item.item_type_name} · {item.barcode}
          </Text>
        </Flex>
        {heldByOther && (
          <Callout.Root color="orange" mb="2">
            <Callout.Text>Currently checked out by {item.holder_name}.</Callout.Text>
          </Callout.Root>
        )}

        {reporting ? (
          <Flex direction="column" gap="3" mt="2">
            <Text size="2" weight="medium">
              {reporting === "loss" ? "Report this item lost" : "Report this item damaged"}
            </Text>
            <TextArea
              placeholder="Add a note (optional) — e.g. screen cracked, left on the bus…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              autoFocus
            />
            <Flex justify="end" gap="2">
              <Button
                variant="soft"
                color="gray"
                disabled={busy}
                onClick={() => {
                  setReporting(null);
                  setNote("");
                }}
              >
                Back
              </Button>
              <Button
                disabled={busy}
                color={reporting === "loss" ? "red" : "orange"}
                onClick={() =>
                  run(
                    () =>
                      reporting === "loss"
                        ? api.kioskReportLoss(item.id, user.id, note.trim() || undefined)
                        : api.kioskReportDamage(item.id, user.id, note.trim() || undefined),
                    reporting === "loss"
                      ? `Reported ${item.name} lost.`
                      : `Reported ${item.name} damaged.`,
                  )
                }
              >
                {reporting === "loss" ? "Report loss" : "Report damage"}
              </Button>
            </Flex>
          </Flex>
        ) : (
          <>
            <Flex direction="column" gap="2" mt="2">
              {!item.holder_user_id && item.status === "Available" && (
                <Button
                  disabled={busy}
                  onClick={() =>
                    run(() => api.kioskCheckout(item.id, user.id), `Checked out ${item.name}.`)
                  }
                >
                  Check out to {user.name}
                </Button>
              )}
              {heldByThisUser && (
                <Button
                  disabled={busy}
                  onClick={() =>
                    run(() => api.kioskCheckin(item.id, user.id), `Checked in ${item.name}.`)
                  }
                >
                  Check in
                </Button>
              )}
              {heldByOther && (
                <Button
                  disabled={busy}
                  color="amber"
                  onClick={() =>
                    run(
                      () => api.kioskCheckin(item.id, item.holder_user_id!),
                      `Checked in ${item.name}.`,
                    )
                  }
                >
                  Force check-in (return for {item.holder_name})
                </Button>
              )}
              <Button
                disabled={busy}
                variant="soft"
                color="orange"
                onClick={() => setReporting("damage")}
              >
                Report damage
              </Button>
              <Button
                disabled={busy}
                variant="soft"
                color="red"
                onClick={() => setReporting("loss")}
              >
                Report loss
              </Button>
            </Flex>

            <Flex justify="end" mt="4">
              <Dialog.Close>
                <Button variant="soft" color="gray">
                  Close
                </Button>
              </Dialog.Close>
            </Flex>
          </>
        )}
      </Dialog.Content>
    </Dialog.Root>
  );
}
