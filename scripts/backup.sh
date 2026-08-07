#!/usr/bin/env bash
# Nightly local backup: Postgres (all structured data) + the images_data volume (recipe photos).
# rabbitmq_data is deliberately NOT backed up — it only ever holds transient in-flight job
# state, nothing durable that isn't already reconstructible.
#
# Meant to be run from the deployed repo's root via cron (see readme.MD's Deployment section for
# the crontab line). Writes into ./backups/{db,images}/ as dated, compressed files, then prunes
# anything not aged 0, 1, 4, or 8 days — so at any point there are at most 4 backups of each kind:
# today's, yesterday's, one from ~4 days ago, and one from ~8 days ago. An external tool (this
# script does not do it) is expected to pull these off the VPS on its own schedule.
#
# Restore procedure is documented in readme.MD's Deployment section, not duplicated here.
set -euo pipefail

cd "$(dirname "$0")/.."

DATE="$(date +%Y%m%d)"
BACKUP_ROOT="./backups"
DB_DIR="$BACKUP_ROOT/db"
IMAGES_BACKUP_DIR="$BACKUP_ROOT/images"
mkdir -p "$DB_DIR" "$IMAGES_BACKUP_DIR"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

echo "[$(date -Iseconds)] dumping database..."
# POSTGRES_USER/POSTGRES_DB are read from the db container's own environment (set from .env by
# docker-compose.yml already) rather than parsed again here — .env has unquoted values containing
# spaces/parens (SCRAPE_USER_AGENT) that aren't valid to `source` as a shell script on the host.
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  | gzip > "$DB_DIR/cookbook-db-$DATE.sql.gz"

echo "[$(date -Iseconds)] archiving images..."
# Streamed straight out of the already-running `api` container, which already has images_data
# mounted at /data/images (see docker-compose.yml) — no throwaway container, and no need to know
# the volume's actual Docker-assigned name (which depends on the compose project name).
$COMPOSE exec -T api tar czf - -C /data/images . > "$IMAGES_BACKUP_DIR/cookbook-images-$DATE.tar.gz"

prune() {
  local dir="$1" prefix="$2" suffix="$3"
  local today_epoch
  today_epoch=$(date -d "$DATE" +%s)
  for f in "$dir/$prefix"*"$suffix"; do
    [ -e "$f" ] || continue
    local base file_date file_epoch age_days
    base="$(basename "$f")"
    file_date="${base#"$prefix"}"
    file_date="${file_date%"$suffix"}"
    file_epoch=$(date -d "$file_date" +%s 2>/dev/null) || continue
    age_days=$(( (today_epoch - file_epoch) / 86400 ))
    case "$age_days" in
      0|1|4|8) ;;                 # keep
      *) echo "  pruning $f (${age_days}d old)"; rm -f "$f" ;;
    esac
  done
}

echo "[$(date -Iseconds)] pruning old backups..."
prune "$DB_DIR" "cookbook-db-" ".sql.gz"
prune "$IMAGES_BACKUP_DIR" "cookbook-images-" ".tar.gz"

echo "[$(date -Iseconds)] done."
