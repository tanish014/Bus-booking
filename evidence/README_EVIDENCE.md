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
| 8 | rollback output | `08_rollback.txt` | done (image tag rollback demo ) |


