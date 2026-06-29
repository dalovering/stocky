import type { ReactNode } from "react";
import Link from "next/link";
import { Button, Container, Flex, Heading } from "@radix-ui/themes";

/** A ghost link button used in page headers (e.g. "Home", "Exit"). */
export function BackLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href}>
      <Button variant="ghost" color="gray">
        {children}
      </Button>
    </Link>
  );
}

/** The page title row shared by the public pages: a large heading plus an optional action. */
export function PageHeader({ title, action }: { title: ReactNode; action?: ReactNode }) {
  return (
    <Flex justify="between" align="center" mb="4">
      <Heading size="7">{title}</Heading>
      {action}
    </Flex>
  );
}

/**
 * The shell for the public (non-admin) pages — a centered container with a {@link PageHeader}.
 * Mirrors how `app/admin/layout.tsx` gives the admin pages one consistent shell, so /inventory
 * and friends share the same width, padding, and title styling.
 */
export function PublicShell({
  title,
  action,
  size = "4",
  children,
}: {
  title: ReactNode;
  action?: ReactNode;
  size?: "1" | "2" | "3" | "4";
  children: ReactNode;
}) {
  return (
    <Container size={size} p="5">
      <PageHeader title={title} action={action} />
      {children}
    </Container>
  );
}
