# F1 Performance Analytics - Phases 1-2 (foundation)

Driver-vs-car performance analysis for Formula 1. Delivers the database, ingestion pipeline,
data-source abstraction with a labelled mock generator, analytics engine (clean laps, fuel
correction, degradation, tyre-adjusted teammate gaps, consistency, driver-vs-car estimate,
data quality), a FastAPI service and a Next.js front end (Dashboard, Driver, Head-to-Head, Methodology).
See docs/ARCHITECTURE.md.

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

# 2. compute the derived layer
cd ../analytics && python compute.py --season 2024 --round 5 --kind R

# 3. serve the API from the database
DATA_SOURCE=postgres uvicorn api:app --reload --port 8000
# GET /teammates/2024/5/R   GET /stints/2024/5/R   GET /events/2024

# tests
python -m pytest -q
```

## Layout
- `db/schema.sql` - raw layer (events, sessions, entries, laps, weather, telemetry) and derived layer
- `services/ingest/ingest.py` - FastF1 -> PostgreSQL, idempotent
- `services/analytics/metrics.py` - lap cleaning, fuel correction, degradation, bootstrap teammate deltas
- `services/analytics/compute.py` - writes derived tables
- `services/analytics/api.py` - FastAPI endpoints
- `docs/` - process documentation

## Tests
`cd services/analytics && python -m pytest -q` (16 tests; analytics are checked against the mock
generator's hidden ground truth). Frontend: `cd web && npx tsc --noEmit && npm run build`.

## Known limits
- Not yet run against live FastF1 data or a live PostgreSQL (postgres source and ingest are compile-checked only).
- Pages not built yet: Teams, Cars, Circuits, Races, Telemetry, Tyres, Strategy, Season Analysis, Predictions, global search.
- No Framer Motion animations yet; mobile layouts are basic.
- Fuel burn is a constant (0.035 s/lap), not measured. Stored as `model_version`.
- Ingestion and API were compile-checked and the metrics engine is unit-tested on synthetic data;
  ingestion has not yet been run against live FastF1 data.
- Telemetry table is created but not populated until Phase 3.
