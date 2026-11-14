# 3-5 minute demo plan

1. (0:00) Show repo + GitHub Actions run: green checks, image tag + digest in summary.
2. (0:45) `docker compose up -d --build` -> `docker compose ps` all healthy; open `https://localhost:8443/health` and `/ready`.
3. (1:30) Run `./scripts/smoke-test.sh`: first booking 201, second same seat 409 (no second PNR).
4. (2:15) `docker compose logs api` - show JSON log lines, `seat conflict` warning.
5. (2:45) `./scripts/failure-drill.sh` - db stopped, `/ready` 503, restart, back to 200.
6. (3:45) Backup -> delete bookings -> restore -> seat is BOOKED again.
7. (4:30) Mention rollback script + known limitations. Done.
