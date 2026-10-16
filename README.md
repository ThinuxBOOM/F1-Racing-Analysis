# F1 Performance Analytics — full build (Phases 1-6)

Driver-vs-car performance analysis for Formula 1. Database, ingestion pipeline (laps + weather +
telemetry at 5 m), data-source abstraction with labelled mock generator, analytics engine (clean
laps, fuel correction + per-circuit estimates, degradation, tyre-adjusted teammate gaps,
consistency, driver-vs-car, team/car pace, tyre offsets, telemetry corners, ridge mixed-effects,
verdict panel, strategy/undercuts, weather, reliability, development, predictions with intervals),
FastAPI service and Next.js front end (all 13 pages). See docs/ARCHITECTURE.md.

## Fastest start (no database, demo data)
```bash
pip install -r services/analytics/requirements.txt
cd services/analytics && DATA_SOURCE=mock uvicorn api:app --port 8000     # terminal 1
cd web && npm install && API_URL=http://localhost:8000 npm run dev          # terminal 2 -> http://localhost:3000
```
All mock data uses fictional teams/drivers, season 2099, and the UI shows a DEMO DATA banner.

## Real data (PostgreSQL + FastF1)
```bash
cp .env.example .env
docker compose up -d                      # PostgreSQL 16 with schema auto-applied

python -m venv .venv && source .venv/bin/activate
pip install -r services/ingest/requirements.txt -r services/analytics/requirements.txt

# 1. ingest a race + qualifying (downloads from FastF1, cached locally)
cd services/ingest && python ingest.py --season 2024 --round 5 --sessions R Q
# add --telemetry for car/position traces (5 m grid); --telemetry-only to backfill

# 2. compute the derived layer
cd ../analytics && python compute.py --season 2024 --round 5 --kind R

# 3. serve the API from the database
DATA_SOURCE=postgres uvicorn api:app --reload --port 8000
# GET /summary/2024/5/R   GET /telemetry/2024/5/R/VER/1   GET /mixed-effects/2024

# tests
python -m pytest -q

## Docker (all services)
```bash
docker compose up --build     # db + api (DATA_SOURCE=mock default) + web -> http://localhost:3000
DATA_SOURCE=postgres docker compose up --build api web   # serve real data (db must be ingested)
```

## Layout
- `db/schema.sql` - raw layer (events, sessions, entries, laps, weather, telemetry) and derived layer
- `services/ingest/ingest.py` - FastF1 -> PostgreSQL, idempotent (laps, weather, 5 m telemetry)
- `services/analytics/metrics.py` - lap cleaning, fuel correction, degradation, bootstrap teammate deltas
- `services/analytics/compute.py` - writes derived tables
- `services/analytics/analysis/` - pipeline, quality, consistency, decomposition, teams, tyres,
  season, telemetry, fuel, mixed, verdict, strategy, reliability, predictions, methodology
- `services/analytics/api.py` - FastAPI endpoints (GZip, server caches, every payload has meta.is_mock)
- `web/` - Next.js 14 app (13 pages, search, virtualised tables, mobile nav, Framer Motion)
- `docs/` - process documentation

## Tests
`cd services/analytics && python -m pytest -q` (41 tests; analytics are checked against the mock
generator's hidden ground truth, including car order, fuel recovery, tyre offsets, predictions MAE).
Frontend: `cd web && npx tsc --noEmit && npm run build`.

## Known limits
- Not yet run against live FastF1 data or a live PostgreSQL (postgres source, ingest and
  telemetry ingest are code-reviewed + unit-tested via pure functions, not live-run — the build
  sandbox had no FastF1 network/database). First-run checklist in the build doc §11 still applies.
- Fuel: 0.035 fallback unless per-circuit estimate is reliable (flagged per round).
- Traffic/dirty air unobserved; some "clean" laps still slowed. Consistency single-session ±16 pts.
- Car vs driver weakly identified with no team moves (mock has none); ridge prior + round-bootstrap
  intervals disclose this. No auth (local single-user analytics, no personal data).
