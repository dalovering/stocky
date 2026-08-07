# Upgrading Stocky

Everything runs from a terminal on the machine hosting Stocky (SSH in first if it's a
Raspberry Pi). Commands are run inside the `stocky` folder — `cd ~/Code/stocky` or
wherever it was cloned.

---

## 0.1.0 → 0.2.0

### 1. Back up your data

Your database survives upgrades, but take a backup anyway — it's one command:

```bash
docker compose exec -T db pg_dump -U stocky -d stocky -Fc > ~/stocky-backup.dump
```

(That exact command is only needed this once — from 0.2.0 onward it's just `make backup`.)

### 2. Upgrade

```bash
git pull
make run
```

That's the whole upgrade: `git pull` fetches the new version, and `make run` rebuilds the
app and updates the database schema automatically. On a Raspberry Pi the rebuild takes a
few minutes — that's normal.

If `git pull` says you are not on a branch: `git checkout main && git pull`, then `make run`.

### 3. Check that it worked

- The site loads and your **existing admin password** logs in (you will not be asked to
  set a new one — if you are, stop and restore from the backup).
- Your users, items, and history are all still there.
- The new **Attendance** tab under Admin opens without an error.
- **Admin → Settings** shows the new version under Software update.

### 4. Optional: set up the Nelko PM220 label printer

Plug the printer into the Pi over USB and power it on, then:

```bash
make printer-env      # asks how the printer is connected and configures everything
make run              # restart so the app picks the printer up
make printer-test     # one test label should print
```

Printing turns itself on once configured — the print buttons on the Users and Inventory
tabs gain a "Print to label printer" option next to the PDF downloads.

Printer tips:

- Use **40 mm-wide or wider** label rolls, ideally Nelko/Marklife brand (third-party
  rolls often mis-feed). 50 × 30 mm is the default; set your actual roll size in
  **Admin → Settings → Label printer**.
- If the wizard warns it can't find the printer: check the USB cable and power, and if
  CUPS is installed it steals the device — `sudo systemctl disable --now cups cups-browsed`,
  then unplug/replug the printer and run `make printer-env` again.
- `make printer-scan-check b=<item barcode>` prints a real item tag you can scan at the
  kiosk to verify end to end.

### What's new in 0.2.0

- **Label printing** — item tags and user badges straight to a Nelko PM220 thermal printer.
- **Restore from backup** — Admin → Export can now restore a full-database `.xlsx` backup,
  showing exactly what would change before touching anything.
- **One-command install and update** — `make run` now creates `.env` when missing and
  applies database migrations itself; `make update REF=...`, `make backup`, and
  `make restore` cover future upgrades and disaster recovery.
- **Attendance** — per-group Present/Absent reporting from kiosk check-ins.
- All dependency security fixes as of the release date.

---

## 0.2.0 and later → newer versions

```bash
make backup                  # dump the database to backups/
make update REF=main         # or REF=v0.3.0 — asks for confirmation, then does everything
```

**Admin → Settings → Software update** shows the running version and what's available.

---

## If something goes wrong

Your backup is the safety net. To roll back a 0.1.0 → 0.2.0 upgrade:

```bash
git checkout v0.1.0
make build && make start
docker compose exec -T db pg_restore -U stocky -d stocky --clean --if-exists --no-owner < ~/stocky-backup.dump
```

Then ask for help before trying the upgrade again — something worth fixing happened.
