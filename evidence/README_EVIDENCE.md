# Evidence checklist

| # | Evidence | File | Status |
|---|---|---|---|
| 1 | lint + 20 tests passing | `01_lint_and_tests.txt` | done (run on my machine) |
| 2 | seat conflict -> 409, 10 parallel requests -> 1x201 + 9x409 | `02_api_conflict_demo.txt` | done (real gunicorn, 2 workers) |
| 3 | structured JSON logs | `03_structured_logs.txt` | done |
| 4 | CI run URL + image tag + digest | `04_ci_run.md` | done |
| 5 | `docker compose ps` healthy + smoke test | `05_deploy_health.txt` | done (Docker + Compose + Nginx HTTPS) |
| 6 | failure drill output | `06_failure_drill.txt` | done (db outage -> 503, recovery -> 200) |
| 7 | backup -> delete data -> restore -> data back | `07_backup_restore.txt` | done (pg_dump + restore verification) |
| 8 | rollback output | `08_rollback.txt` | done (image tag rollback demo) |

How to capture evidence 5-8:
```bash
docker compose ps | tee evidence/05_deploy_health.txt
./scripts/smoke-test.sh | tee -a evidence/05_deploy_health.txt
./scripts/failure-drill.sh 2>&1 | tee evidence/06_failure_drill.txt

# backup/restore proof
./scripts/smoke-test.sh                       # creates a booking, note the PNR
./scripts/backup.sh
docker compose exec db psql -U busapp -d busdb -c "DELETE FROM bookings;"
curl -k https://localhost:8443/trips/1/seats  # seat shows AVAILABLE again = data lost
./scripts/restore.sh backups/<latest>.sql.gz
curl -k https://localhost:8443/trips/1/seats  # seat 21 BOOKED again = restored
# paste all this into 07_backup_restore.txt

./scripts/rollback.sh <old-tag> 2>&1 | tee evidence/08_rollback.txt
```
