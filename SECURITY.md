# Security Policy

## Reporting a vulnerability

**Please don't open a public issue for a security problem.**

Use GitHub's private vulnerability reporting instead: go to the
[Security tab](https://github.com/dalovering/stocky/security/advisories/new) and open a draft
advisory. That keeps the report private until there's a fix.

This is a small project maintained by one person, so expect a first response within about a
week rather than within hours.

## What Stocky's threat model assumes

Knowing this before you report will save us both time — some things that look like
vulnerabilities are deliberate, and some things that look minor are not.

**Stocky is designed to run on a trusted local network** — typically a single Raspberry Pi on a
school LAN, reachable by the classroom devices and nothing else. It is not built to be exposed
to the public internet.

Authentication is applied to the administration surface only:

| Surface | Auth |
|---|---|
| `/api/admin/*` — users, groups, inventory, history, settings | Admin session required |
| `/api/auth/change-password` | Admin session required |
| `/api/labels/*` — ID-card and item-tag PDFs | Admin session required |
| `/api/kiosk/*` — barcode check-in/out | **Open by design** |
| `/api/inventory/*` — read-only item browse | **Open by design** |

The kiosk is open on purpose: it's a shared device where students scan an ID card and then item
barcodes, and requiring a login there would defeat its purpose. It identifies people by scanned
barcode, which is an *identifier*, not a *credential*. On the intended LAN deployment that is an
accepted trade-off, not an oversight.

So these are **not** vulnerabilities we'll act on:

- The kiosk or inventory endpoints being reachable without authentication
- Guessing or forging a barcode to act as another student on the kiosk
- Anything that requires already being on the LAN and is limited to kiosk-level actions

These **are** worth reporting:

- Any unauthenticated path to an `/api/admin/*` action, or any admin-session bypass
- Recovering or forging an admin session cookie, or breaking the password hashing
- Reading the admin password hash through any API response
- SQL injection, or reading/writing data outside what an endpoint is meant to touch
- Anything that lets a LAN user escalate from kiosk-level to admin-level access
- Secrets leaking into logs, error responses, or the repository

If you're unsure which side of the line something falls on, report it privately and we'll work
it out.

## Deployment note for operators

If you run Stocky, keep it on the LAN. Don't port-forward it, don't put it on a guest network,
and don't expose port 8000 or 3000 to the internet. The open kiosk and inventory endpoints
assume the network boundary is doing part of the work.

Generate real secrets with `make init-env` rather than reusing the placeholders in
`.env.example`, and set the admin password through the in-app `/setup` prompt on first launch.
