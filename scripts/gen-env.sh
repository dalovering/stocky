#!/usr/bin/env bash
# Generate a local .env from .env.example, filling in strong random secrets with openssl.
# Safe to run repeatedly: it will NOT overwrite an existing .env unless --force is given.
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE=".env"
EXAMPLE_FILE=".env.example"
FORCE=0
[[ "${1:-}" == "--force" || "${1:-}" == "-f" ]] && FORCE=1

if [[ ! -f "$EXAMPLE_FILE" ]]; then
  echo "error: $EXAMPLE_FILE not found" >&2
  exit 1
fi

if [[ -f "$ENV_FILE" && "$FORCE" -ne 1 ]]; then
  echo "$ENV_FILE already exists; refusing to overwrite. Re-run with --force to replace it." >&2
  exit 1
fi

# Generate secrets.
JWT_SECRET="$(openssl rand -base64 48 | tr -d '\n')"
ADMIN_PASSWORD="$(openssl rand -base64 18 | tr -d '\n/+=' | cut -c1-20)"
DB_PASSWORD="$(openssl rand -base64 18 | tr -d '\n/+=' | cut -c1-20)"

# Start from the example, then substitute the sensitive / derived values.
cp "$EXAMPLE_FILE" "$ENV_FILE"

# Portable in-place edit (works on both macOS/BSD and GNU sed).
sed_inplace() {
  if sed --version >/dev/null 2>&1; then
    sed -i "$1" "$ENV_FILE"      # GNU
  else
    sed -i '' "$1" "$ENV_FILE"   # BSD/macOS
  fi
}

# POSTGRES_PASSWORD is the single source of truth — the backend builds the DB URL from it,
# so there is nothing else to keep in sync.
sed_inplace "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DB_PASSWORD}|"
sed_inplace "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${ADMIN_PASSWORD}|"
sed_inplace "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|"

echo "Wrote $ENV_FILE with freshly generated secrets."
echo "  Admin password: ${ADMIN_PASSWORD}"
echo "(Keep .env private — it is git-ignored.)"
