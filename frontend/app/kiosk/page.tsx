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
  Text,
  TextField,
} from "@radix-ui/themes";

import { AppShell } from "@/components/AppShell";
import { BarcodeScannerProvider } from "@/components/BarcodeScannerProvider";
import { StatusBadge } from "@/components/HistoryList";
import { api, ApiError } from "@/lib/api";
import type { Item, UserDetail } from "@/lib/types";

// Auto-logout after this many ms of inactivity at the kiosk.
const IDLE_MS = 60_000;

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
    setModalItem(null);
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
    if (userRef.current) setUser(await api.kioskUser(userRef.current.id));
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
    [flash, refreshUser, resetIdle],
  );

  useEffect(() => {
    resetIdle();
    return () => {
      if (idleTimer.current) clearTimeout(idleTimer.current);
    };
  }, [resetIdle, user]);

  return (
    <AppShell title="Check-in / Check-out" containerSize="3">
      {/* Global scanner — works with no input focused. */}
      <BarcodeScannerProvider onScan={handleScan} />

      {!user ? (
        <IdlePrompt manual={manual} setManual={setManual} onSubmit={handleScan} toast={toast} />
      ) : (
        <UserPanel
          user={user}
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
  toast,
  onOpenItem,
  onComplete,
}: {
  user: UserDetail;
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
              <Flex justify="between" align="center">
                <Box>
                  <Heading size="3">{i.name}</Heading>
                  <Text size="2" color="gray">
                    {i.item_type_name} {i.location ? `· ${i.location}` : ""}
                  </Text>
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

        <Flex direction="column" gap="2" mt="2">
          {!item.holder_user_id && item.status === "Available" && (
            <Button
              disabled={busy}
              onClick={() => run(() => api.kioskCheckout(item.id, user.id), `Checked out ${item.name}.`)}
            >
              Check out to {user.name}
            </Button>
          )}
          {heldByThisUser && (
            <Button
              disabled={busy}
              onClick={() => run(() => api.kioskCheckin(item.id, user.id), `Checked in ${item.name}.`)}
            >
              Check in
            </Button>
          )}
          {heldByOther && (
            <Button
              disabled={busy}
              color="amber"
              onClick={() =>
                run(() => api.kioskCheckin(item.id, item.holder_user_id!), `Checked in ${item.name}.`)
              }
            >
              Force check-in (return for {item.holder_name})
            </Button>
          )}
          <Button
            disabled={busy}
            variant="soft"
            color="orange"
            onClick={() =>
              run(() => api.kioskReportDamage(item.id, user.id), `Reported ${item.name} damaged.`)
            }
          >
            Report damage
          </Button>
          <Button
            disabled={busy}
            variant="soft"
            color="red"
            onClick={() =>
              run(() => api.kioskReportLoss(item.id, user.id), `Reported ${item.name} lost.`)
            }
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
      </Dialog.Content>
    </Dialog.Root>
  );
}
