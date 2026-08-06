import { redirect } from "next/navigation";

// The kiosk is the homescreen: the device this runs on is a scan station first.
// Admin and inventory are one tap away in the shell's main nav.
export default function Home() {
  redirect("/kiosk");
}
