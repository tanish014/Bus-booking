# Bus Booking API - Cloud Deployment & CI/CD

**Student:** Tanish  |  **Reg. no:** 12401986 |  **Role:** DevOps & Cloud Engineering  
**Project:** Cloud Deployment & CI/CD - Bus Booking Platform (Algions AI Labs)  
**Repository:** [https://github.com/tanish014/Bus-booking](https://github.com/tanish014/Bus-booking)  
**Latest CI Run:** [GitHub Actions Run #43612423600 (Passed / Green)](https://github.com/tanish014/Bus-booking/actions/runs/43612423600)  

---

## Quick Start for Reviewers

### Requirements
- **Docker + Docker Compose**
- **git**
- **openssl**
- *Note for Windows users:* Please run these commands inside **Git Bash** or **WSL** because helper scripts are `.sh` files.

### Steps in Order
```bash
# 1. Clone repository
git clone https://github.com/tanish014/Bus-booking
cd Bus-booking

# 2. Setup environment configuration (set your POSTGRES_PASSWORD)
cp .env.example .env

# 3. Generate self-signed TLS certificates for Nginx HTTPS
./scripts/gen-cert.sh

# 4. Build and start containers in background
docker compose up -d --build

# 5. Check container health status (wait until api, db, and proxy are healthy)
docker compose ps

# 6. Run automated smoke tests
./scripts/smoke-test.sh
```
*(If your system uses the older standalone Docker Compose v1 binary, you can use `docker-compose` in place of `docker compose`.)*

### What to Open in Browser
Open **`https://localhost:8443`** in your browser to view the interactive web UI.  
> **Note:** The browser will display a certificate warning because the TLS certificate is self-signed. Click **Advanced > Proceed to localhost (unsafe)** to open the application.

### Expected Results
- **`GET /health`** -> `{"status":"ok","version":"dev"}` (or current git tag)
- **`GET /ready`** -> `{"database":"up","status":"ready"}`
- **Smoke test output (`./scripts/smoke-test.sh`):**
  - First booking on seat 21 returns **HTTP 201** with confirmed PNR.
  - Second concurrent booking for the same seat returns **HTTP 409 Conflict** with no second PNR created.

### How to Run Tests Without Docker
If you want to run tests locally with Python (using an in-memory SQLite database):
```bash
pip install -r requirements-dev.txt
pytest
```
*Expected output:* **21 passed** (100% test coverage for health, readiness, routes, seat map, booking conflicts, validation, and web UI).

---

## Project Overview

This project is a small bus trip + seat reservation API with an interactive frontend. The main goal is **not just the app itself**, it is how I build, ship, run, monitor, back up, and recover it.

![architecture](docs/architecture.png)

## What is in this repo

| Path | What it is |
|---|---|
| `app/` | Flask API (`main.py`), database code (`db.py`), templates (`index.html`), and static assets (`style.css`, `app.js`) |
| `tests/` | 21 automated API and UI tests (pytest) |
| `Dockerfile` | multi-stage build, runs as non-root user (`appuser`), has a healthcheck |
| `docker-compose.yml` | api + PostgreSQL 16 + nginx TLS proxy, with volume and health checks |
| `nginx/nginx.conf` | HTTPS reverse proxy, http -> https redirect |
| `.github/workflows/ci.yml` | CI: black, flake8, pytest, docker build, trivy scan, push image to GHCR |
| `scripts/` | cert, backup, restore, rollback, smoke test, failure drill |
| `docs/RUNBOOK.md` | operations runbook (deploy, restart, logs, backup, incident) |
| `docs/PROJECT_OVERVIEW.md` | detailed architecture, data flow diagrams, and tech stack overview |
| `evidence/` | full evidence pack (all 8 items completed with raw terminal outputs) |

## API & Web UI

| Method | Path | What it does |
|---|---|---|
| GET | `/` | Web UI - interactive booking, seat map, and PNR lookup |
| GET | `/health` | liveness - app is running (no db check) |
| GET | `/ready` | readiness - checks the database, returns 503 if db is down |
| GET | `/routes` | routes with their stops |
| GET | `/trips?route_id=1&date=YYYY-MM-DD` | list trips |
| GET | `/trips/<id>/seats` | seat map (40 seats, AVAILABLE/BOOKED) |
| POST | `/bookings` | create booking, returns PNR |
| GET | `/bookings/<pnr>` | ticket details / status |
| POST | `/bookings/<pnr>/cancel` | cancel (seat becomes free again) |

Example booking body:
```json
{
  "trip_id": 1,
  "seat_no": 5,
  "travel_date": "2026-11-15",
  "boarding_stop": "Ludhiana",
  "drop_stop": "Delhi",
  "passenger": {
    "name": "Ravi Kumar",
    "age": 24,
    "phone": "9876543210"
  }
}
```
(`travel_date` must equal the trip's date. Seed trips are automatically created for the next 10 days.)

### How double booking is prevented
A Python-level "is the seat free?" check is not safe when two requests arrive simultaneously. So the database has a **partial unique index** on `(trip_id, seat_no) WHERE status='CONFIRMED'`.  
If two requests race, PostgreSQL lets one insert succeed and rejects the second with an integrity error, which the API turns into **HTTP 409** (with zero duplicate PNRs). When a booking is cancelled, its status changes to `CANCELLED`, allowing the seat to be safely rebooked.

---

## Run it (Clean Machine)

Needs: Docker + Docker Compose, openssl, git.

```bash
git clone https://github.com/tanish014/Bus-booking
cd Bus-booking
cp .env.example .env              # then edit POSTGRES_PASSWORD
./scripts/gen-cert.sh             # self-signed cert for HTTPS
docker compose up -d --build
docker compose ps                 # wait until all are "healthy"
./scripts/smoke-test.sh           # health, ready, booking, conflict
```
Open `https://localhost:8443` (browser warning is expected for a self-signed cert; use `curl -k` for CLI).

### Run without Docker (dev)
```bash
pip install -r requirements-dev.txt
pytest                                            # uses SQLite, no setup needed
AUTO_INIT_DB=1 flask --app "app.main:app_factory()" run
```

---

## Environment Variables

| Variable | Used by | Meaning |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | db, api | database credentials (in `.env`, not committed) |
| `APP_VERSION` | compose, api | image tag; shown in `/health` |
| `HTTPS_PORT` / `HTTP_PORT` | proxy | published host ports (default 8443 / 8080) |
| `DATABASE_URL` | api | built by compose from the values above |
| `LOG_LEVEL` | api | INFO by default |
| `AUTO_INIT_DB` | api | `1` = create tables on startup (only for dev/CI) |

## Port Map

| Port | Who | Exposed to host? |
|---|---|---|
| 8443 -> 443 | nginx (HTTPS) | yes |
| 8080 -> 80 | nginx (redirect to https) | yes |
| 8000 | api (gunicorn) | **no**, only inside docker network |
| 5432 | postgres | **no**, only on internal `backend` network |

> **Important Note on HTTP -> HTTPS Redirect:** `nginx/nginx.conf` has `return 301 https://$host:8443$request_uri;` which directs plain HTTP requests on port 8080 to HTTPS port 8443. If you change `HTTPS_PORT` in `.env` to a different host port, please also update the port number in `nginx/nginx.conf` to match and reload proxy with `docker compose restart proxy`.

---

## Troubleshooting

| Problem | Cause | Solution |
|---|---|---|
| Port 8443 or 8080 already in use | Another local service is bound to that port | Change `HTTPS_PORT` and/or `HTTP_PORT` in `.env` (e.g. `HTTPS_PORT=9443`) |
| nginx fails to start | TLS certificates missing | Run `./scripts/gen-cert.sh` to generate certificates in `nginx/certs/` |
| 502 Bad Gateway from nginx | API container crashed or is still initializing | Run `docker compose logs api` to inspect traceback or wait for DB ready check |
| `/ready` returns 503 | Backend cannot connect to PostgreSQL | Run `docker compose logs db` to check database container health |
| Smoke test returns 409 on first booking | Seat 21 was already booked in an earlier run | API is functioning as designed; either book another seat number or wipe/reset DB using `docker compose down -v` |

---

## Evidence Pack

All 8 evidence artifacts have been captured, verified, and saved in the [`evidence/`](evidence/) directory:

- [evidence/01_lint_and_tests.txt](evidence/01_lint_and_tests.txt) - Clean Flake8 linting and 21 passing pytest tests
- [evidence/02_api_conflict_demo.txt](evidence/02_api_conflict_demo.txt) - 10 parallel curl requests proving race-condition safety (1x 201, 9x 409)
- [evidence/03_structured_logs.txt](evidence/03_structured_logs.txt) - Structured JSON log outputs with request IDs, response times, and status
- [evidence/04_ci_run.md](evidence/04_ci_run.md) - GitHub Actions CI run URL, git SHA, and container image digest
- [evidence/05_deploy_health.txt](evidence/05_deploy_health.txt) - `docker compose ps` showing healthy containers & smoke test execution
- [evidence/06_failure_drill.txt](evidence/06_failure_drill.txt) - Simulating database failure, testing readiness failure (503), and recovery
- [evidence/07_backup_restore.txt](evidence/07_backup_restore.txt) - Running `backup.sh`, wiping bookings table, and executing `restore.sh`
- [evidence/08_rollback.txt](evidence/08_rollback.txt) - Rolling back image version in `.env` and proving zero-downtime rollback
- [evidence/README_EVIDENCE.md](evidence/README_EVIDENCE.md) - Complete evidence matrix and checklist

Latest passing CI run: **[GitHub Actions Run #43612423600](https://github.com/tanish014/Bus-booking/actions/runs/43612423600)**

---

## Security Choices
- container runs as non-root user (`appuser`, uid 10001), `read_only` filesystem, `cap_drop: ALL`, `no-new-privileges`
- database is on an `internal` docker network: not reachable from the host or internet
- no secrets in git: `.env` and certs are in `.gitignore`, only `.env.example` is committed
- CI uses the built-in `GITHUB_TOKEN` with minimal permissions, no personal tokens
- Trivy scans the container image in CI for HIGH/CRITICAL security vulnerabilities
- nginx: TLS 1.2+, HSTS, `server_tokens off`

## CI/CD
On every push / PR the workflow runs: **black -> flake8 -> pytest -> docker build -> trivy -> container smoke test**.  
On push to `main` it also pushes the image to `ghcr.io/<owner>/bus-booking-api` tagged with the short git SHA (and `latest`). The image digest is written in the run summary.  
Deployment is manual and simple: set `APP_VERSION` in `.env` and run `docker compose up -d`.

## Rollback
Short version (details in `docs/RUNBOOK.md`):
```bash
./scripts/rollback.sh <previous-tag>      # e.g. ./scripts/rollback.sh a1b2c3d
curl -k https://localhost:8443/health     # version should show the old tag
```
If the problem is bad data (not bad code), use `./scripts/restore.sh backups/<file>.sql.gz`.  
The schema has only `CREATE IF NOT EXISTS`, so rolling back the image is safe, no migrations to undo.

## Known Limitations / Assumptions
- "Cloud" deployment is a local docker-compose stack (allowed by the brief), TLS is self-signed.
- Booking is one seat per request; no payment, no user login, no authentication on the API.
- Prices/fare, seat layout, and seed data are simple demo data.
- Metrics (Prometheus) not done - stretch goal. Only health, readiness, and JSON logs.
- Trivy step only reports (`exit-code: 0`), it does not fail the pipeline yet.
- No database migration tool (Alembic); schema is created by `app/db.py`.
- Tests run on SQLite; the same SQL works on PostgreSQL, but the Postgres path is verified through docker-compose (see `evidence/`).
- Backups are manual (script); a cron job is suggested in the runbook but not set up.
