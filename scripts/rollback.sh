#!/usr/bin/env bash
# usage: ./scripts/rollback.sh 1.0.0     (go back to an older image tag)
set -e
OLD="$1"
[ -n "$OLD" ] || { echo "usage: $0 <old version tag>"; exit 1; }
docker image inspect "bus-booking-api:$OLD" > /dev/null 2>&1 || { echo "image bus-booking-api:$OLD not found on this machine"; exit 1; }
sed -i "s/^APP_VERSION=.*/APP_VERSION=$OLD/" .env
# no --build so it uses the old image that already exists
docker compose up -d --no-build api
sleep 5
curl -sk https://localhost:${HTTPS_PORT:-8443}/health
echo
echo "rolled back to $OLD"
