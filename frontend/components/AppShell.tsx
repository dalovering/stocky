"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Box, Button, Container, Flex, Heading, Tabs } from "@radix-ui/themes";

import { api } from "@/lib/api";

/** A ghost link button used as a page action (e.g. "Home", "Exit"). */
export function BackLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href}>
      <Button variant="ghost" color="gray">
        {children}
      </Button>
    </Link>
  );
}

/**
 * The single application shell shared by the admin and public pages: a consistent top bar
 * (the "Stocky" brand, an optional `nav` slot, and an optional right-aligned `actions` slot) above
 * a centered content container with a section header (`title` + optional `action`). Replaces the
 * previously divergent admin layout and public PageShell so every page looks the same.
 */
export function AppShell({
  nav,
  actions,
  title,
  action,
  containerSize = "4",
  children,
}: {
  nav?: ReactNode;
  actions?: ReactNode;
  title: ReactNode;
  action?: ReactNode;
  containerSize?: "1" | "2" | "3" | "4";
  children: ReactNode;
}) {
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
          {nav}
        </Flex>
        {actions && <Flex align="center" gap="3">{actions}</Flex>}
      </Flex>
      <Container size={containerSize} p="5">
        <Flex justify="between" align="center" mb="4" gap="3" wrap="wrap">
          <Heading size="7">{title}</Heading>
          {action}
        </Flex>
        {children}
      </Container>
    </Box>
  );
}

/** The admin section tabs, highlighting the active route. Used as the AppShell `nav` on admin pages. */
export function AdminNav() {
  const pathname = usePathname();
  const tab = pathname.startsWith("/admin/inventory")
    ? "inventory"
    : pathname.startsWith("/admin/export")
      ? "export"
      : "users";
  return (
    <Tabs.Root value={tab}>
      <Tabs.List>
        <Link href="/admin/users">
          <Tabs.Trigger value="users">Users &amp; Groups</Tabs.Trigger>
        </Link>
        <Link href="/admin/inventory">
          <Tabs.Trigger value="inventory">Inventory</Tabs.Trigger>
        </Link>
        <Link href="/admin/export">
          <Tabs.Trigger value="export">Export</Tabs.Trigger>
        </Link>
      </Tabs.List>
    </Tabs.Root>
  );
}

/** Logs the admin out and returns to the login page. Used as an AppShell `actions` entry. */
export function LogoutButton() {
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
