# Offsite backup pull

Cookbook's VPS backs itself up locally via `scripts/backup.sh` (see `readme.MD`'s
[Backups](../readme.MD#backups) section) — dated Postgres dumps and image archives land under
`./backups/db/` and `./backups/images/` on the VPS, pruned down to ~4 of each kind. That's
protection against a bad deploy or a bad migration, but not against losing the VPS itself: if the
server disappears, so do the backups sitting on it.

`pull-cookbook-backups.sh` in this folder closes that gap. It runs on a separate machine you
control — a Raspberry Pi, a NAS, a laptop, anything with `rsync`/`ssh` and enough disk — and pulls
those same backup files down over SSH on its own schedule, building up an independent, longer-lived
local archive.

## What it does

- Confirms SSH connectivity before doing anything else, and fails loudly (not silently) if the key
  isn't authorized.
- `rsync`s `./backups/db/` and `./backups/images/` from the VPS's deployed repo checkout into a
  local directory, transferring only new/changed files each run.
- Prunes its **own** local copy down to the newest `KEEP_COUNT` files per kind (defaults to 50) —
  independent of, and usually much larger than, the VPS's own ~4-per-kind retention, so this
  machine ends up holding a much longer history than the VPS ever does at once.

It never deletes anything on the VPS, and never touches the live app or database directly — it
only reads files the VPS's own `backup.sh` already produced.

## Setup

1. **Get an SSH key onto the VPS for this machine**, if you haven't already:
   ```
   ssh-copy-id your-vps-user@easy2cook.app
   ```
   Confirm it works with no password prompt:
   ```
   ssh your-vps-user@easy2cook.app
   ```
   This script intentionally never falls back to a password (`BatchMode=yes`) — if the key isn't
   authorized, it fails fast with a clear message instead of hanging on a prompt.

2. **Install rsync** on the pulling machine if it's not already there (Raspberry Pi OS / Debian):
   ```
   sudo apt update && sudo apt install -y rsync
   ```

3. **Get this script onto that machine.** Either clone the whole repo there, or just copy this one
   file over, e.g.:
   ```
   scp maintenance/pull-cookbook-backups.sh your-pi-user@your-pi-host:~/bin/
   ```

4. **Set the configuration** — either edit the variables at the top of the script directly, or
   export them as environment variables before running it (the script reads `${VAR:-default}`
   either way):

   | Variable          | Meaning                                                              | Default              |
   |-------------------|-----------------------------------------------------------------------|----------------------|
   | `REMOTE_USER`     | SSH user on the VPS                                                    | `your-vps-user`      |
   | `REMOTE_HOST`     | VPS hostname                                                           | `easy2cook.app`      |
   | `REMOTE_PORT`     | SSH port                                                               | `22`                 |
   | `REMOTE_REPO_PATH`| Path to the deployed cookbook checkout on the VPS (contains `backups/`)| `/path/to/cookbook`  |
   | `LOCAL_DEST`      | Where pulled files land on this machine                                | `$HOME/cookbook-backups` |
   | `SSH_KEY`         | A specific private key, if not the default/agent one                   | *(blank = default)*  |
   | `KEEP_COUNT`      | How many of the newest backups per kind to keep locally                | `50`                 |

   `REMOTE_REPO_PATH` is the one thing you must get right — check the VPS's crontab
   (`crontab -l` on the VPS) for the exact path `backup.sh` runs from if you're unsure.

5. **Run it once by hand** to verify:
   ```
   chmod +x ~/bin/pull-cookbook-backups.sh
   ~/bin/pull-cookbook-backups.sh
   ```
   Check that files land under `$LOCAL_DEST/db/` and `$LOCAL_DEST/images/`.

6. **Schedule it on cron**, timed comfortably after the VPS's own daily backup job (which runs at
   3am per `readme.MD`'s Deployment section) so that day's files already exist:
   ```
   crontab -e
   ```
   ```
   30 4 * * * /home/pi/bin/pull-cookbook-backups.sh >> /home/pi/cookbook-backup-pull.log 2>&1
   ```

7. **Spot-check occasionally**: `tail ~/cookbook-backup-pull.log` after a scheduled run, and
   `ls $LOCAL_DEST/db $LOCAL_DEST/images` to confirm the count stays capped at `KEEP_COUNT` each.

## Restoring from a pulled backup

A file pulled by this script is byte-identical to the one on the VPS, so the restore commands in
`readme.MD`'s [Backups](../readme.MD#backups) section apply unchanged — just point `gunzip` at the
local path instead of `backups/db/...`/`backups/images/...` on the VPS, and run the
`docker compose exec` half of each command from wherever your Docker stack actually is (the VPS,
most likely, if you're restoring a lost deployment rather than just inspecting a dump locally).
