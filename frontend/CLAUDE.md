# Stocky frontend — guide for Claude

Next.js 16.2 (App Router) + Radix UI, in TypeScript, managed with **npm**. Read the root
[../CLAUDE.md](../CLAUDE.md) first. This file covers frontend-specific conventions.

## Tooling — npm

- Use **npm** (not yarn/pnpm). Commit `package-lock.json`.
- `npm run dev` — dev server (:3000). `npm run build` — production build. `npm start` — serve build.
- `npm run lint` (eslint), `npm run format` (prettier), `npm test` (vitest).

## Stack & conventions

- **App Router** under `app/`. Routes: `/` (home), `/login`, `/admin/*`, `/kiosk`, `/inventory`.
- **Server vs Client components.** Default to Server Components. Add `"use client"` only where you
  need state, effects, or browser APIs (all the interactive pages and dialogs are client
  components). Keep data-only/layout pieces server-side where practical.
- **Radix UI, minimal styling.** Use `@radix-ui/themes` components (Button, Card, Dialog, Table
  primitives, Select, TextField, etc.) wrapped by `<Theme>` in `app/layout.tsx`. Prefer Radix
  props (`size`, `color`, `gap`, `mb`…) over custom CSS. Global CSS in `app/globals.css` is
  intentionally tiny (plus print styles); don't introduce a CSS framework.
- **Shared UI primitives — use these, don't hand-roll.** To keep the app uniform:
  - `components/AppShell.tsx` — the single shell **every** page renders (home, login, kiosk,
    inventory, and all admin pages), over a centered container with an optional section header
    (`title` + optional `action`). **Navigation is owned entirely by the shell** so it's identical
    everywhere: the top bar shows the "Stocky" brand (links home) + the primary nav tabs
    (Kiosk · Inventory · Admin), the shell auto-renders the admin sub-nav row + "Log out" on
    `/admin/*`, and it highlights the active route from `usePathname`. Pages pass only their own
    `title`/`action` — never nav, "Home"/"Exit" back-links, or per-page chrome. To add a top-level
    destination or admin sub-section, edit `MAIN_NAV` / `ADMIN_NAV` in `AppShell.tsx`; don't
    hand-roll a nav or a back-link in a page.
  - `components/DataTable.tsx` — the one flat list table (`columns` + `rows`, optional row click).
    Don't write raw `<table>` markup.
  - `components/GroupedTable.tsx` — the one grouped/nested table: `GroupNode<T>[]` (group headers
    with optional nested `children` + leaf `rows`) reusing `DataTable`'s `Column<T>`. Per-row /
    per-group `RowAction[]` render as icon buttons (view/edit/delete/add/print); omit them for a
    read-only table. Used by the users-by-group, items-by-type, and public inventory views.
  - `components/Dialogs.tsx` — `DialogHeader` (title + ✕), `DialogFooter` (Cancel/Save),
    `ConfirmButton` (inline confirm) and `ConfirmDialog` (controlled confirm for table row deletes).
    Never use native `window.confirm`.
- **API access.** All backend calls go through the typed client in `lib/api.ts`; it sends cookies
  (`credentials: "include"`) for the admin session. Don't call `fetch` directly from components.
  Keep `lib/types.ts` in sync with the backend `app/schemas`.
- **Auth.** `app/admin/layout.tsx` is a thin guard: it checks `api.authStatus()` and redirects to
  `/login` when not authenticated (the shared chrome lives in `AppShell`, rendered per page). Kiosk
  and inventory are public.

## The barcode scanner (key feature)

- USB scanners type fast and end with Enter. `lib/scanner.ts` holds the **pure** detection state
  machine (`feedKey`) — unit-tested in `lib/scanner.test.ts`. Keep logic there, not in components,
  so it stays testable.
- `components/BarcodeScannerProvider.tsx` attaches a global `keydown` listener so scans work
  **without focusing an input** (the core kiosk requirement). It ignores keystrokes while an
  input/textarea is focused. If you tweak timing thresholds, update the tests.

## Printing

- ID cards and item tags print via `components/BarcodeLabelDialog.tsx`. The `.print-area` /
  `.no-print` classes in `globals.css` control what appears on paper. Barcodes are SVGs served by
  the backend (`/api/admin/users/{id}/barcode.svg`, `/api/admin/items/{id}/barcode.svg`).
- The admin **Export data** page (`app/admin/export/page.tsx`) downloads one PDF with every user and
  item barcode in two sections. It fetches `/api/admin/labels.pdf` via `api.labelsPdf()` (a Blob —
  use `requestBlob`, not `request`, for binary responses) and triggers a client-side download.

## Testing & lint

- `npm test` runs vitest over `lib/**/*.test.ts` (pure logic — no DOM needed). Add tests for new
  pure helpers (especially anything scan/parsing related).
- `react-hooks/set-state-in-effect` is disabled in `eslint.config.mjs` (false positive on async
  fetch-on-mount); all other react-hooks rules are on. Update a ref's `.current` inside an effect,
  not during render.
