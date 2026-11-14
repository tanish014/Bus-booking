# Operations Runbook - Bus Booking API

All commands run from the repo folder on the deployment host.

## 1. Deploy / upgrade
```bash
git pull
./scripts/backup.sh                       # always back up first
# set APP_VERSION=<new tag> in .env
docker compose up -d --build
docker compose ps                         # all services should be (healthy)
./scripts/smoke-test.sh
```

## 2. Restart
```bash
docker compose restart api                # one service
docker compose down && docker compose up -d   # everything (data stays, it is in the pgdata volume)
```
**Never** run `docker compose down -v` - the `-v` deletes the database volume.

## 3. Logs
```bash
docker compose logs -f api                # JSON logs, one line per request
docker compose logs --tail=50 db
docker compose logs proxy                 # nginx access/error
docker compose logs api | grep '"level": "ERROR"'
docker compose logs api | grep '"status": 409'     # seat conflicts
```
Every response has an `X-Request-ID` header; the same id is in the api log line for that request.

## 4. Health checks
| Check | Command | Healthy result |
|---|---|---|
| liveness | `curl -k https://localhost:8443/health` | `{"status":"ok","version":"..."}` |
| readiness | `curl -k https://localhost:8443/ready` | `{"database":"up","status":"ready"}` |
| containers | `docker compose ps` | api/db show `healthy` |

## 5. Backup
```bash
./scripts/backup.sh          # -> backups/busdb_YYYYmmdd_HHMMSS.sql.gz (keeps last 7)
```
Optional daily cron at 2am: `0 2 * * * cd /path/to/repo && ./scripts/backup.sh`

## 6. Restore
```bash
ls backups/
./scripts/restore.sh backups/busdb_20261113_020000.sql.gz
./scripts/smoke-test.sh      # or GET /bookings/<known PNR> to confirm data is back
```
The script stops api+proxy, drops the schema, loads the dump, starts api+proxy again.

## 7. Rollback (bad release)
1. Find the last good tag: `docker images bus-booking-api` (or the CI run summary).
2. `./scripts/rollback.sh <good-tag>`
3. Check `/health` shows the old version, run smoke test.
4. If data was also damaged, do section 6 as well.

## 8. Incident response
| Symptom | Likely cause | What to do |
|---|---|---|
| `/ready` returns 503 | database down or unreachable | `docker compose ps db`; `docker compose logs db`; `docker compose start db`; api recovers by itself once db is back (pool_pre_ping) |
| `/health` fails / 502 from nginx | api container crashed | `docker compose logs api`; `docker compose restart api` |
| browser/curl cannot connect | proxy down or cert missing | `docker compose ps proxy`; check `nginx/certs/server.crt` exists (run `gen-cert.sh`) |
| api keeps restarting | wrong DB password in `.env` | compare `.env` with the one used when the volume was first created |
| many 409 on bookings | normal if seats are taken; check it is not a client bug | `grep 409` in api logs |
| bad deploy | new image broken | section 7 |
| data lost/corrupted | human error | section 6 |

Steps for any incident: (1) check `docker compose ps`, (2) read the logs, (3) fix or roll back,
(4) run smoke test, (5) write down what happened.

## 9. Failure drill (for demo)
`./scripts/failure-drill.sh` stops the db, shows `/ready` = 503 while `/health` = 200, starts the db,
and polls until `/ready` returns 200 again.
