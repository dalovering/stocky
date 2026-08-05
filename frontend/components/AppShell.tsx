"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Box, Button, Container, Flex, Heading, SegmentedControl, TabNav } from "@radix-ui/themes";

import { api } from "@/lib/api";

// The primary destinations, shown in the top bar on EVERY page. The brand ("Stocky") links home,
// so these plus the brand are all the navigation any page needs — pages never render their own
// back-links or nav.
const MAIN_NAV = [
  { href: "/kiosk", label: "Kiosk" },
  { href: "/inventory", label: "Inventory" },
  { href: "/admin", label: "Admin" },
];

// The admin sub-sections, shown as a second-level switcher on /admin/* pages only.
const ADMIN_NAV = [
  { href: "/admin/users", label: "Users & Groups" },
  { href: "/admin/inventory", label: "Inventory" },
  { href: "/admin/history", label: "History" },
  { href: "/admin/export", label: "Export" },
  { href: "/admin/settings", label: "Settings" },
];

/**
 * Top-level sections. `TabNav` is the Radix Themes primitive for *navigation* (a real <nav> of
 * links with an active state) — distinct from `Tabs`, which is for in-page panel switching.
 */
function MainNav({ active }: { active: string }) {
  return (
    <TabNav.Root>
      {MAIN_NAV.map((n) => (
        <TabNav.Link key={n.href} asChild active={n.href === active}>
          <Link href={n.href}>{n.label}</Link>
        </TabNav.Link>
      ))}
    </TabNav.Root>
  );
}

/**
 * Admin sub-sections. A centered `SegmentedControl` deliberately differs from the top `TabNav`:
 * the segmented/pill look reads as "switch between sibling views" and visually separates the two
 * nav levels. It drives the router on change.
 */
function AdminSubNav({ active }: { active: string }) {
  const router = useRouter();
  return (
    <Flex
      className="no-print"
      justify="center"
      px="5"
      py="2"
      style={{ borderBottom: "1px solid var(--gray-4)" }}
    >
      <SegmentedControl.Root value={active} onValueChange={(v) => router.push(v)}>
        {ADMIN_NAV.map((n) => (
          <SegmentedControl.Item key={n.href} value={n.href}>
            {n.label}
          </SegmentedControl.Item>
        ))}
      </SegmentedControl.Root>
    </Flex>
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
 * primary nav, plus an automatic "Log out" on admin pages), an automatic centered sub-nav on
 * `/admin/*`, and a centered content container. Navigation is owned entirely by the shell — pages
 * never render their own page-name heading (the nav already shows where you are) and put their own
 * action toolbar (e.g. search + "Add" buttons) in the body. `title` is only for a landing page
 * like home.
 */
export function AppShell({
  title,
  containerSize = "4",
  children,
}: {
  title?: ReactNode;
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
          <MainNav active={mainActive} />
        </Flex>
        {isAdmin && (
          <Flex align="center" gap="3">
            <LogoutButton />
          </Flex>
        )}
      </Flex>

      {isAdmin && <AdminSubNav active={adminActive} />}

      <Container size={containerSize} p="5">
        {title != null && (
          <Heading size="7" mb="4">
            {title}
          </Heading>
        )}
        {children}
      </Container>
    </Box>
  );
}
