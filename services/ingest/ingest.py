"""Load one or more F1 sessions from FastF1 into PostgreSQL.

Usage:
    python ingest.py --season 2024 --round 5 --sessions R Q
    python ingest.py --season 2024 --all-rounds --sessions R Q

Idempotent: re-running a session replaces its rows.
"""
from __future__ import annotations
import argparse, os, sys
import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()
KIND_TO_FASTF1 = {"FP1": "FP1", "FP2": "FP2", "FP3": "FP3", "Q": "Q",
                  "SQ": "SQ", "S": "S", "R": "R"}
TELEMETRY_STEP_M = 5


def secs(td):
    return None if pd.isna(td) else float(td.total_seconds())


def nn(v):
    """NaN-safe python value for SQL."""
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NaT:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def upsert_event(cur, ev) -> int:
    cur.execute("INSERT INTO seasons (season) VALUES (%s) ON CONFLICT DO NOTHING",
                (int(ev["EventDate"].year),))
    cur.execute("""INSERT INTO events (season, round, name, circuit, country, event_date, format)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (season, round) DO UPDATE SET name=EXCLUDED.name
                   RETURNING event_id""",
                (int(ev["EventDate"].year), int(ev["RoundNumber"]), ev["EventName"],
                 ev["Location"], ev["Country"], ev["EventDate"].date(), ev["EventFormat"]))
    return cur.fetchone()[0]


def ingest_session(conn, season: int, rnd: int, kind: str):
    import fastf1
    ses = fastf1.get_session(season, rnd, KIND_TO_FASTF1[kind])
    ses.load(laps=True, telemetry=False, weather=True, messages=False)
    ev = ses.event
    with conn.cursor() as cur:
        event_id = upsert_event(cur, ev)
        cur.execute("DELETE FROM sessions WHERE event_id=%s AND kind=%s", (event_id, kind))
        total = int(ses.total_laps) if getattr(ses, "total_laps", None) else None
        cur.execute("""INSERT INTO sessions (event_id, kind, start_utc, total_laps, data_source)
                       VALUES (%s,%s,%s,%s,'fastf1') RETURNING session_id""",
                    (event_id, kind, ses.date, total))
        session_id = cur.fetchone()[0]

        # --- entries ---
        entry_ids: dict[str, int] = {}
        for _, r in ses.results.iterrows():
            cur.execute("""INSERT INTO teams (name, season) VALUES (%s,%s)
                           ON CONFLICT (name, season) DO UPDATE SET name=EXCLUDED.name
                           RETURNING team_id""", (r["TeamName"], season))
            team_id = cur.fetchone()[0]
            cur.execute("""INSERT INTO drivers (code, full_name, number) VALUES (%s,%s,%s)
                           ON CONFLICT (code) DO UPDATE SET full_name=EXCLUDED.full_name
                           RETURNING driver_id""",
                        (r["Abbreviation"], r["FullName"], nn(pd.to_numeric(r["DriverNumber"], errors="coerce"))))
            driver_id = cur.fetchone()[0]
            cur.execute("""INSERT INTO entries (session_id, driver_id, team_id, grid_pos,
                                                finish_pos, status, points)
                           VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING entry_id""",
                        (session_id, driver_id, team_id, nn(r.get("GridPosition")),
                         nn(r.get("Position")), r.get("Status"), nn(r.get("Points"))))
            entry_ids[r["Abbreviation"]] = cur.fetchone()[0]

        # --- laps ---
        for _, l in ses.laps.iterrows():
            eid = entry_ids.get(l["Driver"])
            if eid is None or pd.isna(l["LapNumber"]):
                continue
            cur.execute("""INSERT INTO laps (entry_id, lap_number, lap_time_s, s1_s, s2_s, s3_s,
                              speed_i1, speed_i2, speed_fl, speed_st, compound, tyre_age,
                              fresh_tyre, stint_number, position, pit_in, pit_out,
                              track_status, is_accurate, deleted)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (entry_id, lap_number) DO NOTHING""",
                        (eid, int(l["LapNumber"]), secs(l["LapTime"]), secs(l["Sector1Time"]),
                         secs(l["Sector2Time"]), secs(l["Sector3Time"]), nn(l["SpeedI1"]),
                         nn(l["SpeedI2"]), nn(l["SpeedFL"]), nn(l["SpeedST"]), l["Compound"],
                         nn(l["TyreLife"]), nn(l["FreshTyre"]), nn(l["Stint"]), nn(l["Position"]),
                         not pd.isna(l["PitInTime"]), not pd.isna(l["PitOutTime"]),
                         str(l["TrackStatus"]) if not pd.isna(l["TrackStatus"]) else None,
                         nn(l["IsAccurate"]), bool(l.get("Deleted", False) is True)))

        # --- weather (per-minute) ---
        w = ses.weather_data
        if w is not None and len(w):
            t0 = w["Time"].iloc[0]
            for _, x in w.iterrows():
                cur.execute("""INSERT INTO weather VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                               ON CONFLICT DO NOTHING""",
                            (session_id, int((x["Time"] - t0).total_seconds() // 60),
                             nn(x["AirTemp"]), nn(x["TrackTemp"]), nn(x["Humidity"]),
                             nn(x["Pressure"]), nn(x["WindSpeed"]), nn(x["WindDirection"]),
                             nn(x["Rainfall"])))
    conn.commit()
    print(f"ingested {season} R{rnd} {kind}: {len(ses.laps)} laps")
    return session_id


def resample_telemetry(car: pd.DataFrame, pos: pd.DataFrame, step_m: int = 5) -> pd.DataFrame:
    """Resample FastF1 time-based telemetry onto a distance grid.

    car: must contain Distance, Speed, Throttle, Brake, nGear, DRS, RPM.
    pos: must contain Distance, X, Y. Both sorted by Distance.
    Returns columns matching the telemetry table.
    Pure function so it is unit-testable without FastF1.
    """
    car = car.sort_values("Distance").dropna(subset=["Distance"])
    pos = pos.sort_values("Distance").dropna(subset=["Distance"])
    if car.empty:
        return pd.DataFrame(columns=["distance_m", "speed", "throttle", "brake",
                                     "gear", "rpm", "drs", "x", "y"])
    lo, hi = float(car["Distance"].min()), float(car["Distance"].max())
    grid = np.arange(max(lo, 0), hi, step_m)
    out = pd.DataFrame({"distance_m": grid})
    for col, out_col in [("Speed", "speed"), ("Throttle", "throttle"),
                         ("nGear", "gear"), ("DRS", "drs"), ("RPM", "rpm")]:
        if col in car.columns:
            out[out_col] = np.interp(grid, car["Distance"].to_numpy(float),
                                     car[col].fillna(0).to_numpy(float))
    if "Brake" in car.columns:
        b = car["Brake"].to_numpy()
        # FastF1 Brake is 0/1 or boolean
        b_num = (b > 0).astype(float) if np.issubdtype(np.asarray(b).dtype, np.number) else b.astype(float)
        out["brake"] = np.interp(grid, car["Distance"].to_numpy(float), b_num) > 0.5
    else:
        out["brake"] = False
    for col, out_col in [("X", "x"), ("Y", "y")]:
        if col in pos.columns and len(pos):
            out[out_col] = np.interp(grid, pos["Distance"].to_numpy(float),
                                     pos[col].fillna(0).to_numpy(float))
        else:
            out[out_col] = 0.0
    return out


def ingest_telemetry(conn, season: int, rnd: int, kind: str, session_id: int,
                     max_drivers: int = 10, max_laps_per_driver: int = 3) -> int:
    """Fetch car + position telemetry for a session's fastest laps and store
    at 5 m steps. Idempotent per lap (deletes existing rows for the lap first).

    Selects up to `max_laps_per_driver` fastest clean-ish laps per driver so
    storage stays bounded (~5 km / 5 m = ~1000 rows per lap).
    Returns number of telemetry rows written.
    """
    import fastf1
    ses = fastf1.get_session(season, rnd, KIND_TO_FASTF1[kind])
    ses.load(laps=True, telemetry=True, weather=False, messages=False)
    total = 0
    with conn.cursor() as cur:
        for drv in ses.laps["Driver"].unique()[:max_drivers]:
            dlaps = ses.laps.pick_drivers([drv]).sort_values("LapTime").head(max_laps_per_driver)
            for _, l in dlaps.iterrows():
                if pd.isna(l["LapNumber"]):
                    continue
                try:
                    car = l.get_car_data()
                    pos = l.get_pos_data()
                except Exception as e:
                    print(f"  telemetry skip {drv} lap {l['LapNumber']}: {e}")
                    continue
                grid = resample_telemetry(car, pos, step_m=TELEMETRY_STEP_M)
                if grid.empty:
                    continue
                cur.execute("SELECT lap_id FROM laps l JOIN entries e ON e.entry_id=l.entry_id "
                            "JOIN drivers d ON d.driver_id=e.driver_id "
                            "WHERE e.session_id=%s AND d.code=%s AND l.lap_number=%s",
                            (session_id, drv, int(l["LapNumber"])))
                row = cur.fetchone()
                if not row:
                    continue
                lap_id = row[0]
                cur.execute("DELETE FROM telemetry WHERE lap_id=%s", (lap_id,))
                cur.executemany(
                    "INSERT INTO telemetry VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    [(int(lap_id), float(r.distance_m), float(r.speed), float(r.throttle),
                      bool(r.brake), int(r.gear) if not pd.isna(r.gear) else None,
                      int(r.rpm) if "rpm" in grid and not pd.isna(getattr(r, "rpm", None)) else None,
                      int(r.drs) if not pd.isna(r.drs) else 0,
                      float(r.x), float(r.y)) for r in grid.itertuples()])
                total += len(grid)
    conn.commit()
    print(f"telemetry: {season} R{rnd} {kind}: {total} samples")
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--round", type=int)
    ap.add_argument("--all-rounds", action="store_true")
    ap.add_argument("--sessions", nargs="+", default=["R", "Q"])
    ap.add_argument("--telemetry", action="store_true",
                    help="also ingest car/position telemetry for fastest laps (5 m grid)")
    ap.add_argument("--telemetry-only", action="store_true",
                    help="only ingest telemetry for already-ingested sessions")
    a = ap.parse_args()

    cache = os.getenv("FASTF1_CACHE", "./.fastf1-cache")
    os.makedirs(cache, exist_ok=True)
    import fastf1
    fastf1.Cache.enable_cache(cache)

    rounds = [a.round]
    if a.all_rounds:
        sched = fastf1.get_event_schedule(a.season, include_testing=False)
        rounds = [int(r) for r in sched["RoundNumber"] if r > 0]
    if rounds == [None]:
        sys.exit("give --round N or --all-rounds")

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        for rnd in rounds:
            for kind in a.sessions:
                try:
                    if a.telemetry_only:
                        cur = conn.cursor()
                        cur.execute("SELECT s.session_id FROM sessions s JOIN events ev ON ev.event_id=s.event_id "
                                    "WHERE ev.season=%s AND ev.round=%s AND s.kind=%s",
                                    (a.season, rnd, kind))
                        row = cur.fetchone()
                        cur.close()
                        if not row:
                            print(f"skip telemetry {a.season} R{rnd} {kind}: session not ingested")
                            continue
                        ingest_telemetry(conn, a.season, rnd, kind, int(row[0]))
                    else:
                        sid = ingest_session(conn, a.season, rnd, kind)
                        if a.telemetry:
                            ingest_telemetry(conn, a.season, rnd, kind, sid)
                except Exception as e:  # sprint/FP sessions may not exist every round
                    conn.rollback()
                    print(f"skip {a.season} R{rnd} {kind}: {e}")


if __name__ == "__main__":
    main()
