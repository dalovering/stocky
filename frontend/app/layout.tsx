import type { Metadata } from "next";
import { Theme } from "@radix-ui/themes";
import "@radix-ui/themes/styles.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stocky",
  description: "Classroom inventory management",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {/* Radix Themes provides the minimal-styling component system used throughout. */}
        <Theme accentColor="teal" grayColor="slate" radius="medium">
          {children}
        </Theme>
      </body>
    </html>
  );
}
