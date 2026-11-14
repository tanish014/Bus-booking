#!/usr/bin/env bash
# takes a backup of the postgres database into ./backups
set -e
source .env
mkdir -p backups
FILE="backups/busdb_$(date +%Y%m%d_%H%M%S).sql.gz"
docker-compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$FILE"
echo "backup saved: $FILE ($(du -h "$FILE" | cut -f1))"
# keep only the latest 7 backups
ls -1t backups/*.sql.gz | tail -n +8 | xargs -r rm --
