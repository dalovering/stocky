"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Box, Button, Flex, Heading, Spinner, Tabs } from "@radix-ui/themes";

import { api } from "@/lib/api";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    api
      .authStatus()
      .then((s) => {
        if (!s.authenticated) router.replace("/login");
        else setReady(true);
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  async function logout() {
    await api.logout();
    router.replace("/login");
  }

  if (!ready) {
    return (
      <Flex align="center" justify="center" style={{ height: "100vh" }}>
        <Spinner size="3" />
      </Flex>
    );
  }

  const tab = pathname.startsWith("/admin/inventory") ? "inventory" : "users";

  return (
    <Box>
      <Flex
        className="no-print"
        align="center"
        justify="between"
        px="5"
        py="3"
        style={{ borderBottom: "1px solid var(--gray-5)" }}
      >
        <Flex align="center" gap="5">
          <Heading size="5">
            <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>
              Stocky Admin
            </Link>
          </Heading>
          <Tabs.Root value={tab}>
            <Tabs.List>
              <Link href="/admin/users">
                <Tabs.Trigger value="users">Users &amp; Groups</Tabs.Trigger>
              </Link>
              <Link href="/admin/inventory">
                <Tabs.Trigger value="inventory">Inventory</Tabs.Trigger>
              </Link>
            </Tabs.List>
          </Tabs.Root>
        </Flex>
        <Button variant="soft" onClick={logout}>
          Log out
        </Button>
      </Flex>
      <Box p="5">{children}</Box>
    </Box>
  );
}
