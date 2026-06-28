import Link from "next/link";
import { Box, Card, Container, Flex, Heading, Text } from "@radix-ui/themes";

const VIEWS = [
  {
    href: "/kiosk",
    title: "Check-in / Check-out",
    desc: "Scan a student ID, then scan items to borrow or return them.",
  },
  {
    href: "/inventory",
    title: "Inventory",
    desc: "Browse items, locations, and quantities. Read-only.",
  },
  {
    href: "/admin",
    title: "Administration",
    desc: "Manage users, groups, and inventory. Requires admin login.",
  },
];

export default function Home() {
  return (
    <Container size="2" p="6">
      <Heading size="8" mb="1">
        Stocky
      </Heading>
      <Text color="gray" size="3">
        Classroom inventory management
      </Text>
      <Flex direction="column" gap="3" mt="5">
        {VIEWS.map((v) => (
          <Link key={v.href} href={v.href} style={{ textDecoration: "none" }}>
            <Card className="clickable" size="3">
              <Box>
                <Heading size="4">{v.title}</Heading>
                <Text color="gray">{v.desc}</Text>
              </Box>
            </Card>
          </Link>
        ))}
      </Flex>
    </Container>
  );
}
