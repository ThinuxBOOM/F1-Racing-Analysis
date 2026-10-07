"""FastAPI service. Run: DATA_SOURCE=mock uvicorn api:app --reload --port 8000

The API only talks to the DataSource interface, so mock and real data are interchangeable.
Every response that carries data includes `meta` so the UI can always label demo data.
"""
from __future__ import annotations
from functools import lru_cache
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import metrics as m
from datasource import get_source
from analysis.pipeline import prepare
from analysis.consistency import consistency, RELIABILITY_NOTE
from analysis.decomposition import decompose, driver_effects
from analysis.quality import quality_report
from analysis.methodology import METRICS, BY_ID

app = FastAPI(title="F1 Performance Analytics API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["GET"])
SRC = get_source()
RACE_LIKE = ("R", "S")


def meta() -> dict:
    return dict(data_source=SRC.name, is_mock=SRC.is_mock, model_version=m.MODEL_VERSION,
                notice=("DEMO DATA: synthetic, fictional teams and drivers. Not real results." if SRC.is_mock
                        else "Independent analytics project. Not affiliated with Formula 1."))


def _total_laps(season: int, rnd: int, laps: pd.DataFrame) -> int:
    ev = SRC.events(season)
    row = ev[ev["round"] == rnd]
    if len(row) and pd.notna(row["total_laps"].iloc[0]):
        return int(row["total_laps"].iloc[0])
    return int(laps["lap_number"].max())


@lru_cache(maxsize=64)
def prepared(season: int, rnd: int, kind: str) -> pd.DataFrame:
    laps = SRC.laps(season, rnd, kind)
    if laps.empty:
        raise HTTPException(404, f"no laps for {season} round {rnd} {kind}")
    return prepare(laps, _total_laps(season, rnd, laps), race_like=kind in RACE_LIKE)


def _clean(v):
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else round(float(v), 4)
    if isinstance(v, np.integer): return int(v)
    if isinstance(v, np.bool_): return bool(v)
    return v


def _records(df: pd.DataFrame) -> list[dict]:
    return [{k: _clean(v) for k, v in r.items()} for r in df.to_dict("records")]


@app.get("/meta")
def get_meta(): return meta()


@app.get("/seasons")
def seasons(): return dict(meta=meta(), seasons=SRC.seasons())


@app.get("/events/{season}")
def events(season: int): return dict(meta=meta(), events=_records(SRC.events(season)))


@app.get("/pace/{season}/{rnd}/{kind}")
def pace(season: int, rnd: int, kind: str):
    """Lap-by-lap data for the race-pace chart, plus the field median of clean laps per lap."""
    df = prepared(season, rnd, kind)
    cols = ["driver", "team", "lap_number", "lap_time_s", "fuel_corr_time_s", "compound", "tyre_age",
            "stint_number", "position", "is_clean", "exclude_reason", "track_status"]
    field = (df[df.is_clean].groupby("lap_number")["fuel_corr_time_s"].median().reset_index()
             .rename(columns={"fuel_corr_time_s": "field_median_s"}))
    return dict(meta=meta(), laps=_records(df[cols]), field_median=_records(field))


@lru_cache(maxsize=64)
def adjusted_teammates(season: int, rnd: int, kind: str) -> dict:
    """Tyre-mix-adjusted teammate gaps per driver, from the same model as the head-to-head page."""
    df = prepared(season, rnd, kind)
    out = {}
    for team, g in df[df.is_clean].groupby("team"):
        ds = sorted(g["driver"].unique())
        if len(ds) != 2:
            continue
        r = decompose(df, ds[0], ds[1], n_boot=100)
        if "error" in r:
            continue
        a, ci = r["adjusted_gap_s"]["estimate_s"], r["adjusted_gap_s"]["ci95_s"]
        for me, mate, sign in ((ds[0], ds[1], 1), (ds[1], ds[0], -1)):
            lo, hi = sorted((sign * ci[0], sign * ci[1]))
            d = dict(delta=sign * a, ci_low=lo, ci_high=hi, n_a=0, n_b=0)
            out[me] = dict(teammate=mate, delta_s=round(d["delta"], 3), ci_low=round(lo, 3),
                           ci_high=round(hi, 3), verdict=m.verdict(d))
    return out


@app.get("/summary/{season}/{rnd}/{kind}")
def summary(season: int, rnd: int, kind: str):
    """Dashboard payload: one row per driver with results, pace, gaps and consistency."""
    df = prepared(season, rnd, kind)
    res = SRC.results(season, rnd, kind).set_index("driver")
    clean = df[df.is_clean]
    pace_col = "fuel_corr_time_s"
    med = clean.groupby("driver")[pace_col].median()          # raw clean median (not tyre-adjusted)
    eff = pd.Series(driver_effects(df))                        # tyre-mix-adjusted pace
    tm_all = adjusted_teammates(season, rnd, kind)
    best = df[~df["deleted"]].groupby("driver")["lap_time_s"].min()
    sectors = {s: clean.groupby("driver")[s].min() for s in ("s1_s", "s2_s", "s3_s")}
    cons = {r["driver"]: r for r in consistency(df)} if kind in RACE_LIKE else {}
    team_of = df.groupby("driver")["team"].first()
    pole = best.min()
    rows = []
    for drv in med.index:
        tm = tm_all.get(drv)
        r = res.loc[drv] if drv in res.index else None
        rows.append(dict(
            driver=drv, team=team_of[drv],
            grid_pos=_clean(r["grid_pos"]) if r is not None and pd.notna(r["grid_pos"]) else None,
            finish_pos=_clean(r["finish_pos"]) if r is not None else None,
            status=r["status"] if r is not None else None,
            points=_clean(r["points"]) if r is not None else None,
            best_lap_s=_clean(best.get(drv)), gap_to_best_s=_clean(best.get(drv) - pole),
            median_clean_pace_s=_clean(med[drv]), n_clean=int((clean.driver == drv).sum()),
            gap_to_field_best_pace_s=_clean(eff[drv] - eff.min()) if drv in eff.index else None,
            best_sectors={k[:2]: _clean(v.get(drv)) for k, v in sectors.items()},
            consistency=cons.get(drv), teammate=tm))
    rows.sort(key=lambda x: (x["finish_pos"] is None, x["finish_pos"]))
    return dict(meta=meta(), rows=rows,
                sector_leaders={k[:2]: _clean(v.idxmin()) for k, v in sectors.items()})


@app.get("/stints/{season}/{rnd}/{kind}")
def stints(season: int, rnd: int, kind: str):
    df = prepared(season, rnd, kind)
    out = []
    for (drv, st), g in df.groupby(["driver", "stint_number"]):
        s = m.stint_degradation(g)
        out.append(dict(driver=drv, stint=int(st), compound=g["compound"].iloc[0],
                        start_lap=int(g.lap_number.min()), end_lap=int(g.lap_number.max()),
                        start_tyre_age=_clean(g["tyre_age"].iloc[0]), n_laps=len(g), n_clean=s["n_clean"],
                        mean_pace_s=_clean(s["mean"]), best_lap_s=_clean(g["lap_time_s"].min()),
                        deg_s_per_lap=_clean(s["deg"]), deg_se=_clean(s["deg_se"]),
                        reliable=bool(s["n_clean"] >= 8 and not np.isnan(s["deg_se"]))))
    return dict(meta=meta(), stints=out)


@app.get("/consistency/{season}/{rnd}/{kind}")
def consistency_route(season: int, rnd: int, kind: str):
    return dict(meta=meta(), method=BY_ID["consistency"], reliability_note=RELIABILITY_NOTE,
                scores=consistency(prepared(season, rnd, kind)))


@app.get("/quality/{season}/{rnd}/{kind}")
def quality(season: int, rnd: int, kind: str):
    df = prepared(season, rnd, kind)
    return dict(meta=meta(), report=quality_report(df, _total_laps(season, rnd, df) if kind in RACE_LIKE else None))


@app.get("/driver-vs-car/{season}/{rnd}/{a}/{b}")
def driver_vs_car(season: int, rnd: int, a: str, b: str):
    result = decompose(prepared(season, rnd, "R"), a, b)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return dict(meta=meta(), result=result, method=BY_ID["driver_vs_car"])


@app.get("/pit-stops/{season}/{rnd}")
def pit_stops(season: int, rnd: int):
    return dict(meta=meta(), pit_stops=_records(SRC.pit_stops(season, rnd)))


@app.get("/methodology")
def methodology(): return dict(meta=meta(), metrics=METRICS)
