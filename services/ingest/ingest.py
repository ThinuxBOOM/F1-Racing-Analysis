"""Load one or more F1 sessions from FastF1 into PostgreSQL.

Usage:
    python ingest.py --season 2024 --round 5 --sessions R Q
    python ingest.py --season 2024 --all-rounds --sessions R Q

Idempotent: re-running a session replaces its rows.
"""
from __future__ import annotations
import argparse, os, sys
import fastf1
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


def ingest_session(conn, season: int, rnd: int, kind: str) -> None:
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--round", type=int)
    ap.add_argument("--all-rounds", action="store_true")
    ap.add_argument("--sessions", nargs="+", default=["R", "Q"])
    a = ap.parse_args()

    cache = os.getenv("FASTF1_CACHE", "./.fastf1-cache")
    os.makedirs(cache, exist_ok=True)
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
                    ingest_session(conn, a.season, rnd, kind)
                except Exception as e:  # sprint/FP sessions may not exist every round
                    conn.rollback()
                    print(f"skip {a.season} R{rnd} {kind}: {e}")


if __name__ == "__main__":
    main()
