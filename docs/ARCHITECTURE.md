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

## 3. API (all responses include `meta.is_mock`)
GET /meta /seasons /events/{season} /methodology
GET /summary|pace|stints|consistency|quality/{season}/{round}/{kind}
GET /driver-vs-car/{season}/{round}/{a}/{b}   GET /pit-stops/{season}/{round}

## 4. Frontend pages
Built: Dashboard, Driver, Head-to-Head, Methodology. Listed as "soon" in the nav (not built):
Teams, Cars, Circuits, Races, Telemetry, Tyres, Strategy, Season Analysis, Predictions.

## 5. What real data can support
| Need | Source | Notes |
|---|---|---|
| Lap/sector times, compounds, stints, track status, weather, pit laps | FastF1 (2018+), OpenF1 | Core of Phases 1-2 |
| Speed, throttle, brake, gear, RPM, DRS, GPS | FastF1 telemetry (2018+) | Needed for corner/braking analysis |
| Historical results, standings, qualifying | Jolpica-Ergast (1950+) | Trends only; no laps before 2018 |
| Fuel load, engine modes, tyre temps/pressures, setup, true stationary pit time | Not public | Must be modelled or omitted |

## 6. Timing-only vs telemetry-required
Timing only (implemented): clean laps, fuel correction, stint degradation, teammate gaps, race pace,
consistency, sector gaps, data quality, driver-vs-car estimate, strategy timelines, pit loss.
Telemetry required (planned): braking points, minimum corner speed, throttle application, corner
entry/apex/exit deltas, DRS/slipstream effects, track-map overlays, brake/throttle zones.

## 7. Known limitations and biases
- Fuel burn is a constant (0.035 s/lap); real burn varies. Stored in `model_version`.
- Traffic/dirty air is not directly observable; it inflates variance and biases clean-pace estimates.
- Teammate comparisons assume equal cars; teams can split parts or strategies.
- Car vs driver is only weakly identifiable within one season; the shared team effect is credited to the car.
- Single-race statistics are noisy (consistency score about +-16 points in synthetic tests).
- Survivorship: faster cars get more clean-air laps; lap-1 and SC laps are dropped everywhere.
- Mock data validates the code, not real-world conclusions.

## 8. Roadmap
P3 telemetry ingest + corner deltas + track map. P4 mixed-effects driver/car across seasons, per-circuit fuel.
P5 strategy simulation, weather, reliability, season development, predictions with intervals, global search.
P6 virtualised tables, mobile layouts for complex charts, caching, deployment.
