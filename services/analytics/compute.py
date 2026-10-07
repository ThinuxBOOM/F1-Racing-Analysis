"""Compute the derived layer for a session and write it to PostgreSQL.

Usage: python compute.py --season 2024 --round 5 --kind R
"""
from __future__ import annotations
import argparse, os
import pandas as pd
import psycopg
from dotenv import load_dotenv
import metrics as m

load_dotenv()


def load_laps(conn, season, rnd, kind) -> tuple[pd.DataFrame, int, int]:
    q = """SELECT l.lap_id, l.entry_id, d.code AS driver, d.driver_id, t.name AS team,
                  l.lap_number, l.lap_time_s, l.tyre_age, l.compound, l.stint_number,
                  l.pit_in, l.pit_out, l.track_status, l.deleted,
                  s.session_id, s.total_laps
           FROM laps l
           JOIN entries e ON e.entry_id = l.entry_id
           JOIN drivers d ON d.driver_id = e.driver_id
           JOIN teams t ON t.team_id = e.team_id
           JOIN sessions s ON s.session_id = e.session_id
           JOIN events ev ON ev.event_id = s.event_id
           WHERE ev.season=%s AND ev.round=%s AND s.kind=%s"""
    df = pd.read_sql(q, conn, params=(season, rnd, kind))
    if df.empty:
        raise SystemExit("no laps found - ingest the session first")
    total = int(df["total_laps"].iloc[0] or df["lap_number"].max())
    return df, int(df["session_id"].iloc[0]), total


def compute(conn, season, rnd, kind):
    df, session_id, total = load_laps(conn, season, rnd, kind)
    df = m.flag_clean_laps(df)
    df["fuel_corr_time_s"] = m.fuel_correct(df, total) if kind in ("R", "S") else df["lap_time_s"]

    with conn.cursor() as cur:
        cur.execute("DELETE FROM lap_features WHERE lap_id = ANY(%s)", (df["lap_id"].tolist(),))
        cur.executemany(
            "INSERT INTO lap_features VALUES (%s,%s,%s,%s,%s)",
            [(int(r.lap_id), bool(r.is_clean), r.exclude_reason,
              None if pd.isna(r.fuel_corr_time_s) else float(r.fuel_corr_time_s), m.MODEL_VERSION)
             for r in df.itertuples()])

        # stint metrics
        for (eid, stint), g in df.groupby(["entry_id", "stint_number"]):
            s = m.stint_degradation(g)
            cur.execute("""INSERT INTO stint_metrics VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (entry_id, stint_number) DO UPDATE SET
                           deg_s_per_lap=EXCLUDED.deg_s_per_lap, deg_se=EXCLUDED.deg_se,
                           n_clean=EXCLUDED.n_clean, mean_pace_s=EXCLUDED.mean_pace_s,
                           consistency_sd=EXCLUDED.consistency_sd""",
                        (int(eid), int(stint), g["compound"].iloc[0], len(g), s["n_clean"],
                         None if pd.isna(s["mean"]) else s["mean"],
                         None if pd.isna(s["deg"]) else s["deg"],
                         None if pd.isna(s["deg_se"]) else s["deg_se"],
                         None if pd.isna(s["sd"]) else s["sd"]))

        # per-driver pace + teammate deltas (race-type sessions)
        clean = df[df["is_clean"]]
        pace = clean.groupby(["entry_id", "driver_id", "team"])["fuel_corr_time_s"].agg(
            ["median", "count", "min", "std"]).reset_index()
        for r in pace.itertuples():
            cur.execute("""INSERT INTO driver_session_pace VALUES (%s,%s,%s,%s,%s)
                           ON CONFLICT (entry_id) DO UPDATE SET median_pace_s=EXCLUDED.median_pace_s""",
                        (int(r.entry_id), float(r.median), int(r.count), float(r.min),
                         None if pd.isna(r.std) else float(r.std)))

        for team, g in clean.groupby("team"):
            drivers = sorted(g["driver_id"].unique())
            if len(drivers) != 2:
                continue
            a_id, b_id = drivers
            d = m.teammate_delta(g[g.driver_id == a_id]["fuel_corr_time_s"],
                                 g[g.driver_id == b_id]["fuel_corr_time_s"])
            cur.execute("""INSERT INTO teammate_deltas VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (session_id, driver_a, driver_b, metric)
                           DO UPDATE SET delta_s=EXCLUDED.delta_s, ci_low=EXCLUDED.ci_low,
                                         ci_high=EXCLUDED.ci_high""",
                        (session_id, int(a_id), int(b_id), "race_pace" if kind in ("R", "S") else "pace",
                         d["delta"], d["ci_low"], d["ci_high"], d["n_a"], d["n_b"]))
    conn.commit()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--kind", default="R")
    a = ap.parse_args()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        compute(conn, a.season, a.round, a.kind)
        print("derived layer written")
