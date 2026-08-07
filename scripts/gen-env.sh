#!/usr/bin/env bash
# Generate a local .env from .env.example, filling in strong random secrets with openssl,
# then offer to configure the Nelko PM220 label printer (interactive runs only).
# Safe to run repeatedly: it will NOT overwrite an existing .env unless --force is given.
#
#   --printer   skip generation entirely and run ONLY the printer wizard, appending to
#               the EXISTING .env (make printer-env). Never touches secrets.
set -euo pipefail

cd "$(dirname "$0")/.."

# ENV_FILE / GEN_ENV_PROMPT / GEN_ENV_OS are overridable for the script's own tests.
ENV_FILE="${ENV_FILE:-.env}"
EXAMPLE_FILE=".env.example"
FORCE=0
PRINTER_ONLY=0
case "${1:-}" in
  --force | -f) FORCE=1 ;;
  --printer) PRINTER_ONLY=1 ;;
esac

if [[ "$PRINTER_ONLY" -eq 1 ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "error: $ENV_FILE does not exist — run 'make init-env' (or 'make run') first." >&2
    exit 1
  fi
  if [[ ! -t 0 && -z "${GEN_ENV_PROMPT:-}" ]]; then
    echo "error: --printer is interactive; run it from a terminal." >&2
    exit 1
  fi
else
  if [[ ! -f "$EXAMPLE_FILE" ]]; then
    echo "error: $EXAMPLE_FILE not found" >&2
    exit 1
  fi
  if [[ -f "$ENV_FILE" && "$FORCE" -ne 1 ]]; then
    echo "$ENV_FILE already exists; refusing to overwrite. Re-run with --force to replace it." >&2
    echo "(To add the label printer to an existing .env: make printer-env)" >&2
    exit 1
  fi
fi

if [[ "$PRINTER_ONLY" -ne 1 ]]; then
  # Generate secrets.
  JWT_SECRET="$(openssl rand -base64 48 | tr -d '\n')"
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
  sed_inplace "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|"

  echo "Wrote $ENV_FILE with freshly generated secrets."
  echo "(Keep .env private — it is git-ignored.)"
  echo "The admin password isn't set here — the app will prompt you to create one on first launch."
fi

# ---------------------------------------------------------------------------
# Optional: label printer (Nelko PM220).
# Appends to $ENV_FILE — for duplicated keys, docker compose and pydantic-settings
# both take the last occurrence, so appending safely wins over any earlier value.
# ---------------------------------------------------------------------------

prompt() { # prompt <question> <default> -> answer (default when blank)
  local reply
  read -r -p "$1" reply
  echo "${reply:-$2}"
}

lower() { echo "$1" | tr '[:upper:]' '[:lower:]'; }

append_env() {
  {
    echo ""
    echo "# --- Label printer (Nelko PM220) — added by make init-env ---"
    printf '%s\n' "$@"
  } >>"$ENV_FILE"
}

if [[ "$PRINTER_ONLY" -ne 1 ]]; then
  if [[ ! -t 0 && -z "${GEN_ENV_PROMPT:-}" ]]; then
    echo
    echo "(Non-interactive run: skipping label-printer setup — 'make printer-env' adds it later.)"
    exit 0
  fi
  echo
  answer="$(prompt "Set up the Nelko PM220 label printer now? [y/N] " n)"
  if [[ "$(lower "$answer")" != y* ]]; then
    echo "Skipped. You can set it up any time with: make printer-env"
    exit 0
  fi
fi

case "${GEN_ENV_OS:-$(uname -s)}" in
  Darwin)
    echo
    echo "Note: Docker Desktop on macOS can't pass devices into containers, so on a Mac"
    echo "the printer only works with 'make dev' over Bluetooth serial (pair the printer"
    echo "in System Settings first; it appears as /dev/cu.<name>)."
    suggestion="$(ls /dev/cu.* 2>/dev/null | grep -v "Bluetooth-Incoming" | head -1 || true)"
    device="$(prompt "Serial device [${suggestion:-none found — enter path, blank to skip}]: " "${suggestion:-}")"
    if [[ -z "$device" ]]; then
      echo "Skipped. Pair the printer and re-run, or edit $ENV_FILE later."
      exit 0
    fi
    append_env "PRINTER_DEVICE=${device}"
    echo "PRINTER_DEVICE set. Check it with: make dev-printer-status  (during 'make dev')"
    ;;
  *)
    echo
    echo "  1) USB (recommended)"
    echo "  2) Bluetooth serial (rfcomm)"
    mode="$(prompt "How is the printer connected? [1/2] " 1)"
    if [[ "$mode" == 2* ]]; then
      device="$(prompt "Serial device [/dev/rfcomm0]: " /dev/rfcomm0)"
      append_env "PRINTER_DEVICE=${device}"
      echo
      echo "PRINTER_DEVICE set. Bluetooth needs two manual steps before printing works:"
      echo "  1. Pair + bind on the host:  bluetoothctl pair <MAC> && bluetoothctl trust <MAC>"
      echo "                               sudo rfcomm bind ${device##*/dev/rfcomm} <MAC> 1"
      echo "  2. Grant the container the device: see the Bluetooth section at the bottom"
      echo "     of docker-compose.printer.yml, then add its overlay to COMPOSE_FILE."
      exit 0
    fi
    detected="$(ls /dev/usb/lp* 2>/dev/null | head -1 || true)"
    if [[ -z "$detected" ]]; then
      echo "No /dev/usb/lp* device found right now (printer off/unplugged, or CUPS has"
      echo "claimed it — see README 'Label printer'). Continuing with the usual default."
    fi
    device="$(prompt "Printer device [${detected:-/dev/usb/lp0}]: " "${detected:-/dev/usb/lp0}")"
    gid="$(getent group lp 2>/dev/null | cut -d: -f3 || true)"
    if [[ -z "$gid" ]]; then
      gid=7
      echo "Couldn't read the 'lp' group id (getent); using the Debian/RPi OS default (7)."
    fi
    append_env \
      "PRINTER_DEVICE=${device}" \
      "PRINTER_GID=${gid}" \
      "COMPOSE_FILE=docker-compose.yml:docker-compose.printer.yml"
    echo
    echo "Label printer configured (device ${device}, lp gid ${gid}, compose overlay on)."
    echo "After 'make run': make printer-status, make printer-test, then enable label"
    echo "printing in Admin -> Settings."
    ;;
esac
