#!/usr/bin/env bash
# usage: ./scripts/restore.sh backups/busdb_xxx.sql.gz
set -e
source .env
FILE="$1"
[ -f "$FILE" ] || { echo "usage: $0 <backup file>"; exit 1; }
echo "stopping api so nobody writes during restore..."
docker compose stop api proxy
# drop and recreate the schema, then load the backup
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
gunzip -c "$FILE" | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q
docker compose start api proxy
echo "restore finished from $FILE"
