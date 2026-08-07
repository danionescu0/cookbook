#!/usr/bin/env bash
# Nightly local backup: Postgres (all structured data) + the images_data volume (recipe photos).
# rabbitmq_data is deliberately NOT backed up — it only ever holds transient in-flight job
# state, nothing durable that isn't already reconstructible.
#
# Meant to be run from the deployed repo's root via cron (see readme.MD's Deployment section for
# the crontab line). Writes into ./backups/{db,images}/ as dated, compressed files, then prunes
# down to at most 4 backups of each kind: today's, yesterday's, one from roughly 4 days back, and
# one from roughly 8 days back (see prune()'s own comment for exactly what "roughly" means and
# why). An external tool (this script does not do it) is expected to pull these off the VPS on
# its own schedule.
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

# Prints "<path> <age-in-days>" for every backup already on disk matching dir/prefix*suffix,
# relative to $DATE.
_backup_ages() {
  local dir="$1" prefix="$2" suffix="$3"
  local today_epoch f base file_date file_epoch age_days
  today_epoch=$(date -d "$DATE" +%s)
  for f in "$dir/$prefix"*"$suffix"; do
    [ -e "$f" ] || continue
    base="$(basename "$f")"
    file_date="${base#"$prefix"}"
    file_date="${file_date%"$suffix"}"
    file_epoch=$(date -d "$file_date" +%s 2>/dev/null) || continue
    age_days=$(( (today_epoch - file_epoch) / 86400 ))
    echo "$f $age_days"
  done
}

# Retention: always keep age 0-1 (today, yesterday). Additionally keep the single OLDEST survivor
# aged 2-5 (the "~4 days ago" slot) and the single OLDEST survivor aged 6-9 (the "~8 days ago"
# slot); everything else, including anything past age 9, is deleted. So at most 4 backups of each
# kind exist at once, and the two older ones drift within their range before rotating to a fresher
# backup once they age out — never frozen on one ever-aging file forever.
#
# This is NOT the same as "keep age exactly {0,1,4,8}" — an earlier version of this script did
# exactly that, and it doesn't work: re-applied every day, it deletes every backup the moment it
# turns 2 days old, so nothing ever survives long enough to reach age 4 or 8 in the first place.
# Picking the OLDEST survivor within a range instead is what makes a backup "stick" through the
# gap ages until something replaces it — verified by simulating 25 consecutive daily runs (see
# Design Decisions, "Local backup strategy") before trusting this in production.
prune() {
  local dir="$1" prefix="$2" suffix="$3"
  local mid_keep="" old_keep="" f age best_age

  best_age=-1
  while read -r f age; do
    [ "$age" -ge 2 ] && [ "$age" -le 5 ] || continue
    [ "$age" -gt "$best_age" ] && { mid_keep="$f"; best_age="$age"; }
  done < <(_backup_ages "$dir" "$prefix" "$suffix")

  best_age=-1
  while read -r f age; do
    [ "$age" -ge 6 ] && [ "$age" -le 9 ] || continue
    [ "$age" -gt "$best_age" ] && { old_keep="$f"; best_age="$age"; }
  done < <(_backup_ages "$dir" "$prefix" "$suffix")

  while read -r f age; do
    if [ "$age" -le 1 ] || [ "$f" = "$mid_keep" ] || [ "$f" = "$old_keep" ]; then
      continue
    fi
    echo "  pruning $f (${age}d old)"
    rm -f "$f"
  done < <(_backup_ages "$dir" "$prefix" "$suffix")
}

echo "[$(date -Iseconds)] pruning old backups..."
prune "$DB_DIR" "cookbook-db-" ".sql.gz"
prune "$IMAGES_BACKUP_DIR" "cookbook-images-" ".tar.gz"

echo "[$(date -Iseconds)] done."
