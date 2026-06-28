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
- **API access.** All backend calls go through the typed client in `lib/api.ts`; it sends cookies
  (`credentials: "include"`) for the admin session. Don't call `fetch` directly from components.
  Keep `lib/types.ts` in sync with the backend `app/schemas`.
- **Auth.** `app/admin/layout.tsx` checks `api.authStatus()` and redirects to `/login` when not
  authenticated. Kiosk and inventory are public.

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

## Testing & lint

- `npm test` runs vitest over `lib/**/*.test.ts` (pure logic — no DOM needed). Add tests for new
  pure helpers (especially anything scan/parsing related).
- `react-hooks/set-state-in-effect` is disabled in `eslint.config.mjs` (false positive on async
  fetch-on-mount); all other react-hooks rules are on. Update a ref's `.current` inside an effect,
  not during render.
