#!/usr/bin/env bash
# Runs ON AN OFFSITE MACHINE (e.g. a Raspberry Pi), not on the VPS. Pulls the cookbook VPS's
# on-server backups (see readme.MD's "Backups" section — scripts/backup.sh writes dated Postgres
# dumps + image archives into ./backups/db/ and ./backups/images/ under the deployed repo
# checkout) down here over SSH/rsync, so a copy survives even if the VPS itself is lost. See
# maintenance/README.md for setup.
#
# The VPS side only ever keeps ~4 backups of each kind (its own retention prune in backup.sh);
# this script has its own independent local retention (KEEP_COUNT below), unrelated to that one.
#
# Requires: rsync + ssh on this machine, and an SSH key already authorized on the VPS for
# REMOTE_USER (confirm first with: ssh REMOTE_USER@REMOTE_HOST — this script never prompts for a
# password).
set -euo pipefail

# ---- Configure these for your setup, then leave them alone ----
REMOTE_USER="${REMOTE_USER:-your-vps-user}"
REMOTE_HOST="${REMOTE_HOST:-easy2cook.app}"
REMOTE_PORT="${REMOTE_PORT:-22}"
# Path to the deployed cookbook repo checkout on the VPS — the directory backup.sh is cron-run
# from, containing ./backups/db and ./backups/images.
REMOTE_REPO_PATH="${REMOTE_REPO_PATH:-/path/to/cookbook}"
# Where pulled copies land on this machine.
LOCAL_DEST="${LOCAL_DEST:-$HOME/cookbook-backups}"
# Optional: a specific private key, e.g. ~/.ssh/id_ed25519_cookbook. Leave blank to use
# ssh-agent/the default key.
SSH_KEY="${SSH_KEY:-}"
# Local retention: keep only the newest KEEP_COUNT backups per kind (db, images), deleting older
# ones after each pull. Filenames sort chronologically (cookbook-db-YYYYMMDD.sql.gz), so a plain
# filename sort doubles as a date sort — no need to parse dates the way backup.sh's own prune()
# does on the VPS side.
KEEP_COUNT="${KEEP_COUNT:-50}"
# ---- End configuration ----

SSH_CMD="ssh -p $REMOTE_PORT -o BatchMode=yes -o ConnectTimeout=10${SSH_KEY:+ -i $SSH_KEY}"

log() { echo "[$(date -Iseconds)] $*"; }

# Deletes the oldest files in $1 until at most KEEP_COUNT remain.
prune_local() {
  local dir="$1" total
  total=$(find "$dir" -maxdepth 1 -type f | wc -l)
  [ "$total" -le "$KEEP_COUNT" ] && return
  log "pruning $dir: $total on disk, keeping newest $KEEP_COUNT"
  find "$dir" -maxdepth 1 -type f -printf '%f\n' | sort | head -n "-$KEEP_COUNT" \
    | while IFS= read -r f; do rm -f -- "$dir/$f"; done
}

log "checking SSH connectivity to $REMOTE_USER@$REMOTE_HOST:$REMOTE_PORT..."
if ! $SSH_CMD "$REMOTE_USER@$REMOTE_HOST" true; then
  log "ERROR: could not connect over SSH. Confirm the key is authorized" >&2
  log "  (ssh-copy-id -p $REMOTE_PORT $REMOTE_USER@$REMOTE_HOST)" >&2
  log "  and REMOTE_HOST/REMOTE_USER/REMOTE_PORT are correct." >&2
  exit 1
fi

mkdir -p "$LOCAL_DEST/db" "$LOCAL_DEST/images"

log "pulling database backups..."
rsync -avz --progress -e "$SSH_CMD" \
  "$REMOTE_USER@$REMOTE_HOST:$REMOTE_REPO_PATH/backups/db/" "$LOCAL_DEST/db/"

log "pulling image backups..."
rsync -avz --progress -e "$SSH_CMD" \
  "$REMOTE_USER@$REMOTE_HOST:$REMOTE_REPO_PATH/backups/images/" "$LOCAL_DEST/images/"

prune_local "$LOCAL_DEST/db"
prune_local "$LOCAL_DEST/images"

log "done — $(find "$LOCAL_DEST" -type f | wc -l) files total under $LOCAL_DEST"
