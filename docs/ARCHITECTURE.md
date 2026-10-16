# Architecture, methodology and data realism

## 1. Pipeline
DATA SOURCE (FastF1 | OpenF1 | Ergast | mock) -> INGESTION -> CLEANING -> STORAGE (PostgreSQL)
-> ANALYTICS ENGINE (Python) -> API (FastAPI) -> UI (Next.js)

The analytics engine and API only see `DataSource` frames (`services/analytics/datasource/base.py`).
Swapping the data layer means writing one new class. The UI only calls `web/lib/api.ts`.

## 2. Schema
`db/schema.sql` (raw + derived) and `db/002_extended.sql` (seasons, circuits, cars, stints, pit_stops,
incidents, data_quality, per-session `data_source`/`is_mock`). Derived tables carry `model_version`.
Circuit "characteristics" are columns computed from data, never hand-labelled.

## 3. API (all responses include `meta.is_mock`; GZip above 1 kB; heavy season endpoints server-cached)
GET /meta /seasons /events/{season} /methodology
GET /summary|pace|stints|consistency|quality/{season}/{round}/{kind}
GET /driver-vs-car/{season}/{round}/{a}/{b}   GET /pit-stops/{season}/{round}
GET /teams|tyres/{season}/{round}/{kind}  GET /standings/{season}  GET /circuits/{season}  GET /races/{season}/{round}
GET /telemetry/{season}/{round}/{kind}/{driver}/{lap}  GET /corner-deltas/...
GET /fuel/{season}/{round}  GET /mixed-effects/{season}  GET /verdict/{season}/{round}/{a}/{b}
GET /strategy|weather/{season}/{round}  GET /reliability|development/{season}  GET /predictions/{season}/{round}

## 4. Frontend pages
Built: Dashboard, Drivers, Head-to-Head (+ verdict panel), Teams, Cars, Circuits, Races, Tyres,
Telemetry (overlays + track map), Strategy, Season Analysis (ratings + development + reliability),
Predictions (with intervals + backtest MAE), Methodology. No "soon" entries remain.
Global search, virtualised lap explorer, Framer Motion fades, mobile nav included.

## 4. Frontend pages
Built: Dashboard, Drivers, Head-to-Head (+ verdict panel), Teams, Cars, Circuits, Races, Tyres,
Telemetry (overlays + track map), Strategy, Season Analysis (ratings + development + reliability),
Predictions (with intervals + backtest MAE), Methodology. No "soon" entries remain.
Global search, virtualised lap explorer, Framer Motion fades, mobile nav included.

## 5. What real data can support
| Need | Source | Notes |
|---|---|---|
| Lap/sector times, compounds, stints, track status, weather, pit laps | FastF1 (2018+), OpenF1 | Core of Phases 1-2 |
| Speed, throttle, brake, gear, RPM, DRS, GPS | FastF1 telemetry (2018+) | Needed for corner/braking analysis |
| Historical results, standings, qualifying | Jolpica-Ergast (1950+) | Trends only; no laps before 2018 |
| Fuel load, engine modes, tyre temps/pressures, setup, true stationary pit time | Not public | Must be modelled or omitted |

## 6. Timing-only vs telemetry-required
Timing only (implemented): clean laps, fuel correction (+ per-circuit estimates), stint degradation,
teammate gaps, race pace, consistency, sector gaps, data quality, driver-vs-car estimate,
team/car pace, tyre offsets, standings, circuit profiles, strategy/undercuts, weather effects,
reliability, development curves, mixed-effects ratings, verdict panel, predictions with intervals.
Telemetry (implemented): braking points, minimum corner speed, throttle application, corner
entry/apex/exit deltas, track-map overlays. DRS/slipstream isolation remains unmodelled.

## 7. Known limitations and biases
- Fuel burn is a constant (0.035 s/lap); real burn varies. Stored in `model_version`.
- Traffic/dirty air is not directly observable; it inflates variance and biases clean-pace estimates.
- Teammate comparisons assume equal cars; teams can split parts or strategies.
- Car vs driver is only weakly identifiable within one season; the shared team effect is credited to the car.
- Single-race statistics are noisy (consistency score about +-16 points in synthetic tests).
- Survivorship: faster cars get more clean-air laps; lap-1 and SC laps are dropped everywhere.
- Mock data validates the code, not real-world conclusions.

## 8. Roadmap — all built
P2 remainder: Teams/Cars/Races/Tyres/Circuits pages, search, virtualised tables, mobile, animations. DONE.
P3: telemetry ingest (5 m grid) + corner deltas + track map. DONE.
P4: per-circuit fuel, ridge mixed-effects, verdict panel. DONE.
P5: strategy/undercuts, weather, reliability, development, predictions. DONE.
P6: GZip, server caches, Dockerfiles + compose, healthchecks. DONE.

## 9. Deployment and operations
- `docker compose up --build`: db (Postgres 16 + schema), api (DATA_SOURCE=mock by default;
  set DATA_SOURCE=postgres + DATABASE_URL for real data), web (API_URL=http://api:8000).
- Demo: `DATA_SOURCE=mock uvicorn api:app --port 8000` + `API_URL=http://localhost:8000 npm run dev`.
- Real data: `cp .env.example .env && docker compose up -d db`, ingest R+Q, ingest `--telemetry`,
  `DATA_SOURCE=postgres uvicorn api:app`.
- Health: GET /health? No — GET /meta is the health signal (200 + model_version + is_mock).
  API container HEALTHCHECK polls /meta. No auth: single-user local analytics, no personal data.
- Monitoring: uvicorn access logs + compose `docker compose logs`. No PII logged.
- Performance: lru_cache on prepared/teammate/frames/mixed/predictions; GZip; virtualised
  lap explorer; pace/telemetry payloads on 25 m+ grids. Mixed/predictions bootstraps are the
  slowest (~30-60 s cold, cached after).
