# Stocky frontend — guide for Claude

Next.js 16.2 (App Router) + Radix UI, in TypeScript, managed with **npm**. Read the root
[../CLAUDE.md](../CLAUDE.md) first. This file covers frontend-specific conventions.

## Tooling — npm

- Use **npm** (not yarn/pnpm). Commit `package-lock.json`.
- `npm run dev` — dev server (:3000). `npm run build` — production build. `npm start` — serve build.
- `npm run lint` (eslint), `npm run format` (prettier), `npm test` (vitest).

## Stack & conventions

- **App Router** under `app/`. Routes: `/` (redirects to the kiosk — the homescreen is the scan
  station), `/login`, `/setup` (first-launch admin password creation), `/admin/*`, `/kiosk`,
  `/inventory`.
- **Server vs Client components.** Default to Server Components. Add `"use client"` only where you
  need state, effects, or browser APIs (all the interactive pages and dialogs are client
  components). Keep data-only/layout pieces server-side where practical.
- **Radix UI, minimal styling.** Use `@radix-ui/themes` components (Button, Card, Dialog, Table
  primitives, Select, TextField, etc.) wrapped by `<Theme>` in `app/layout.tsx`. Prefer Radix
  props (`size`, `color`, `gap`, `mb`…) over custom CSS. Global CSS in `app/globals.css` is
  intentionally tiny (plus print styles); don't introduce a CSS framework.
- **Shared UI primitives — use these, don't hand-roll.** To keep the app uniform:
  - `components/AppShell.tsx` — the single shell **every** page renders (login, kiosk, inventory,
    and all admin pages), over a centered content container. **Navigation is owned entirely by the
    shell** so it's identical
    everywhere: the top bar shows the "Stocky" brand (links home) + the primary section nav
    (Kiosk · Inventory · Admin) as a **`TabNav`** (the Radix Themes navigation primitive — real
    `<nav>` links with an active state, _not_ `Tabs`, which is for in-page panels). On `/admin/*`
    the shell auto-renders a centered **`SegmentedControl`** sub-nav (Users · Inventory · History ·
    Export · Settings) —
    the pill/segmented look deliberately differentiates the second nav level from the top tabs.
    While an admin session is active (per `useAuth()`), the shell shades the top bar **red** with
    an "Admin" badge on *every* page (kiosk included) and shows the "Log out" button — logging out
    from a non-admin page just clears the bar; admin pages also navigate to `/login`. Active state
    is derived from `usePathname`. **Don't render a page-name heading in a page** — the nav
    already shows where you are. A page puts its own action
    toolbar (search + "Add" buttons, in one `Flex justify="between"` row — don't stack them) in the
    body; the only AppShell prop is `containerSize`. To add a destination, edit `MAIN_NAV` /
    `ADMIN_NAV` in `AppShell.tsx`; never hand-roll a nav, a back-link, or a redundant page title in
    a page.
  - `components/DataTable.tsx` — the one flat list table (`columns` + `rows`, optional row click).
    Don't write raw `<table>` markup.
  - `components/GroupedTable.tsx` — the one grouped/nested table: `GroupNode<T>[]` (group headers
    with optional nested `children` + leaf `rows`) reusing `DataTable`'s `Column<T>`. Per-row /
    per-group `RowAction[]` render as icon buttons (view/edit/delete/add/print); omit them for a
    read-only table. Used by the users-by-group, items-by-type, and public inventory views.
  - `components/Dialogs.tsx` — `DialogHeader` (title + ✕), `DialogFooter` (Cancel/Save),
    `ConfirmButton` (inline confirm) and `ConfirmDialog` (controlled confirm for table row deletes).
    Never use native `window.confirm`.
  - `components/HistoryList.tsx` — the event-history table plus `StatusBadge` (item _and_ user
    status), `EventBadge`, and `ReviewBadge`. Use these badges; don't hand-roll a `<Badge>`.
  - **Admin multi-select / batch / IO / filters** (shared by the Users and Inventory tabs, so they
    behave identically): the `useSelection` hook (`hooks/useSelection.ts`),
    `components/SelectionBar.tsx` (the "N selected · Edit · Print · Delete · Clear" bar),
    `components/ImportExportButtons.tsx` (Download `.xlsx` + Import), `components/ImportResultDialog.tsx`,
    and `components/MultiSelectFilter.tsx` (the multi-value checkbox dropdown used for *every* enum
    filter — don't build single-value enum `Select` filters). Pass `selectable` +
    `selectedIds`/`onToggle`/`onToggleMany` to `GroupedTable` to enable checkboxes; that includes
    per-group select-alls and a master select-all in the header (which selects the currently
    filtered rows — filtering is server-side, so that's exactly what's on screen).
  - **Filtering (server-side) — use the shared filter bar, don't hand-roll.** Filtering is done by
    the backend via parameterized list endpoints (multi-valued `status`/`condition`/`type_id`/
    `location` etc.) — including the *derived* item status — not in the browser. The standard UI is
    `components/FilterBar.tsx` (lays out a `SearchField` + the page's filter controls + a Reset
    button that appears only when filters deviate from defaults + a result count) wrapping
    `MultiSelectFilter`s; `components/SearchField.tsx` is the search input (leading magnifier +
    clear ×). `hooks/useDebouncedValue.ts` debounces the (now server-hitting) search; pages own the
    filter state and pass it to `api.*` calls. `hooks/useUrlFilters.ts` mirrors filter state to the
    URL (via `history.replaceState`, so reload/share keep the filters) and returns `hydrated` — gate
    the first fetch on it. For `MultiSelectFilter`, Type/Location use `emptyMeansAll` (empty Set =
    show all, since their option set is dynamic) and `renderOption` for labels (e.g. the
    `__none__` location sentinel → "(No location)").
- **Admin tabs.** `/admin/{users,inventory}` are the CRUD + batch tables; `/admin/history` is the
  paginated event log; `/admin/settings` toggles app config; `/admin/export` downloads the multi-up
  card sheet. Add a tab via `ADMIN_NAV` in `AppShell.tsx`.
- **API access.** All backend calls go through the typed client in `lib/api.ts`; it sends cookies
  (`credentials: "include"`) for the admin session. Don't call `fetch` directly from components.
  Keep `lib/types.ts` in sync with the backend `app/schemas`.
- **Auth.** `components/AuthProvider.tsx` (mounted in `app/layout.tsx`) owns the client's view of
  the admin session: the cookie is httpOnly, so it polls `/api/auth/status` on load, navigation,
  and tab refocus and exposes `{status, refresh}` via `useAuth()` — call `refresh()` after any
  login/logout so the shell updates without a reload. It also runs the **admin idle auto-logout**
  (`admin_idle_timeout_minutes` from settings, 0 = off): throttled activity listeners reset a
  timer; expiry logs out, refreshes, and redirects `/admin/*` to `/login?reason=idle` (the login
  page explains). Client-enforced; the JWT absolute expiry is the server backstop. `app/admin/layout.tsx` is a thin guard on
  top of it: it redirects to `/setup` if no admin password has been configured yet, else to
  `/login` when not authenticated (the shared chrome lives in `AppShell`, rendered per page).
  `/login` and `/setup` each also check `needs_setup` on mount and redirect to the other, so a
  bookmarked/direct hit on either always lands on the right one. There is no `.env`-configured admin password — it's created via `/setup`
  on first launch and changed from Admin → Settings (`api.changePassword`). Kiosk and inventory are
  public.

## The barcode scanner (key feature)

- USB scanners type fast and end with Enter. `lib/scanner.ts` holds the **pure** detection state
  machine (`feedKey`) — unit-tested in `lib/scanner.test.ts`. Keep logic there, not in components,
  so it stays testable.
- `components/BarcodeScannerProvider.tsx` attaches a global `keydown` listener so scans work
  **without focusing an input** (the core kiosk requirement). It ignores keystrokes while an
  input/textarea is focused. If you tweak timing thresholds, update the tests.

## Printing

- ID cards and item tags are **server-rendered PDFs** from SVG templates (backend
  `app/templates/*.svg` + `services/cards.py`). The Users/Inventory tabs download a single card
  (`api.userIdCardPdf` / `api.itemTagPdf`), a whole group/type one-per-page
  (`api.groupIdCardsPdf` / `api.itemTypeTagsPdf`), or the current selection
  (`api.usersIdCardsPdf` / `api.itemsTagsPdf`). Use `downloadBlob(blob, filename)` from `lib/api`
  to trigger the download; binary responses go through `requestBlob` (GET) / `requestBlobPost`
  (POST), not `request`.
- The admin **Export** page (`app/admin/export/page.tsx`) downloads the multi-up US-Letter sheet
  (every ID card, then every item tag) via `api.labelsPdf()`.
- `.no-print` in `globals.css` hides chrome from any browser print; the card PDFs don't rely on it.

## Testing & lint

- `npm test` runs vitest over `lib/**/*.test.ts` (pure logic — no DOM needed). Add tests for new
  pure helpers (especially anything scan/parsing related).
- `react-hooks/set-state-in-effect` is disabled in `eslint.config.mjs` (false positive on async
  fetch-on-mount); all other react-hooks rules are on. Update a ref's `.current` inside an effect,
  not during render.
