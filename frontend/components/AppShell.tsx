"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Box, Button, Container, Flex, Heading, Tabs } from "@radix-ui/themes";

import { api } from "@/lib/api";

// The primary destinations, shown in the top bar on EVERY page. The brand ("Stocky") links home,
// so these plus the brand are all the navigation any page needs — pages never render their own
// back-links or nav.
const MAIN_NAV = [
  { href: "/kiosk", label: "Kiosk" },
  { href: "/inventory", label: "Inventory" },
  { href: "/admin", label: "Admin" },
];

// The admin sub-sections, shown as a second-level nav row on /admin/* pages only.
const ADMIN_NAV = [
  { href: "/admin/users", label: "Users & Groups" },
  { href: "/admin/inventory", label: "Inventory" },
  { href: "/admin/export", label: "Export" },
];

/** A row of route tabs that highlights whichever entry matches the current path. */
function NavTabs({ items, active }: { items: { href: string; label: string }[]; active: string }) {
  return (
    <Tabs.Root value={active}>
      <Tabs.List>
        {items.map((n) => (
          <Link key={n.href} href={n.href}>
            <Tabs.Trigger value={n.href}>{n.label}</Tabs.Trigger>
          </Link>
        ))}
      </Tabs.List>
    </Tabs.Root>
  );
}

/** Logs the admin out and returns to the login page. Rendered automatically on admin pages. */
function LogoutButton() {
  const router = useRouter();
  return (
    <Button
      variant="soft"
      onClick={async () => {
        await api.logout();
        router.replace("/login");
      }}
    >
      Log out
    </Button>
  );
}

/**
 * The single application shell EVERY page renders: a consistent top bar (the "Stocky" brand + the
 * primary nav, plus an automatic "Log out" on admin pages) above a centered content container with
 * an optional section header (`title` + optional `action`). Navigation is owned entirely by the
 * shell — pages pass only their own `title`/`action` and never wire up nav or back-links — so the
 * interface is identical across kiosk, inventory, admin, home, and login.
 */
export function AppShell({
  title,
  action,
  containerSize = "4",
  children,
}: {
  title?: ReactNode;
  action?: ReactNode;
  containerSize?: "1" | "2" | "3" | "4";
  children: ReactNode;
}) {
  const pathname = usePathname();
  const isAdmin = pathname.startsWith("/admin");

  // Highlight the main-nav entry whose route is the current path or a parent of it.
  const mainActive =
    MAIN_NAV.find((n) => pathname === n.href || pathname.startsWith(n.href + "/"))?.href ?? "";
  const adminActive = ADMIN_NAV.find((n) => pathname.startsWith(n.href))?.href ?? "/admin/users";

  return (
    <Box>
      <Flex
        className="no-print"
        align="center"
        justify="between"
        px="5"
        py="3"
        gap="5"
        style={{ borderBottom: "1px solid var(--gray-5)" }}
      >
        <Flex align="center" gap="5">
          <Heading size="5">
            <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>
              Stocky
            </Link>
          </Heading>
          <NavTabs items={MAIN_NAV} active={mainActive} />
        </Flex>
        {isAdmin && (
          <Flex align="center" gap="3">
            <LogoutButton />
          </Flex>
        )}
      </Flex>

      {isAdmin && (
        <Flex
          className="no-print"
          px="5"
          py="2"
          style={{ borderBottom: "1px solid var(--gray-4)" }}
        >
          <NavTabs items={ADMIN_NAV} active={adminActive} />
        </Flex>
      )}

      <Container size={containerSize} p="5">
        {title != null && (
          <Flex justify="between" align="center" mb="4" gap="3" wrap="wrap">
            <Heading size="7">{title}</Heading>
            {action}
          </Flex>
        )}
        {children}
      </Container>
    </Box>
  );
}
