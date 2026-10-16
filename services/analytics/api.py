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
from fastapi.middleware.gzip import GZipMiddleware

import metrics as m
from datasource import get_source
from analysis.pipeline import prepare
from analysis.consistency import consistency, RELIABILITY_NOTE
from analysis.decomposition import decompose, driver_effects
from analysis.quality import quality_report
from analysis.methodology import METRICS, BY_ID
from analysis.teams import team_summary, ASSUMPTIONS as TEAM_ASSUMPTIONS
from analysis.tyres import tyre_report
from analysis.season import season_standings, circuit_characteristics
from analysis.telemetry import detect_corners, corner_deltas
from analysis.fuel import estimate_fuel, FALLBACK_FUEL
from analysis.mixed import mixed_with_intervals
from analysis.verdict import verdict_panel
from analysis.strategy import strategy_table, undercuts
from analysis.reliability import weather_effect, reliability, development
from analysis.predictions import predict_round

app = FastAPI(title="F1 Performance Analytics API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["GET"])
app.add_middleware(GZipMiddleware, minimum_size=1000)
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


@app.get("/teams/{season}/{rnd}/{kind}")
def teams(season: int, rnd: int, kind: str):
    """Per-team aggregates: observed points/positions + MODEL ESTIMATE car pace."""
    df = prepared(season, rnd, kind)
    res = SRC.results(season, rnd, kind)
    rows = team_summary(df, res)
    return dict(meta=meta(), teams=rows, assumptions=TEAM_ASSUMPTIONS,
                label="Car pace is a MODEL ESTIMATE (mean of tyre-adjusted driver effects). Points/positions are observed.")


@app.get("/tyres/{season}/{rnd}/{kind}")
def tyres(season: int, rnd: int, kind: str):
    """Per-compound pace offsets (adjusted) and degradation. Offsets are MODEL ESTIMATES."""
    df = prepared(season, rnd, kind)
    return dict(meta=meta(), compounds=tyre_report(df),
                label="Adjusted offsets remove driver/car/tyre-age mix; raw medians do not.",
                method=BY_ID.get("tyre_compound"))


@app.get("/standings/{season}")
def standings(season: int):
    """Season driver and team standings from observed results across all rounds."""
    ev = SRC.events(season)
    if ev.empty:
        raise HTTPException(404, f"no events for season {season}")
    frames = []
    for r in ev["round"].tolist():
        try:
            frames.append(SRC.results(season, int(r), "R"))
        except Exception:
            continue
    return dict(meta=meta(), standings=season_standings(frames))


@app.get("/circuits/{season}")
def circuits(season: int):
    """Data-derived circuit characteristics per round. Braking/full-throttle need telemetry."""
    ev = SRC.events(season)
    if ev.empty:
        raise HTTPException(404, f"no events for season {season}")
    out = []
    for _, e in ev.iterrows():
        rnd = int(e["round"])
        try:
            df = prepared(season, rnd, "R")
        except HTTPException:
            try:
                df = prepared(season, rnd, "Q")
            except HTTPException:
                continue
        # reliable stint slopes for mean degradation
        deg_rows = []
        for (_, _st), g in df.groupby(["driver", "stint_number"]):
            s = m.stint_degradation(g)
            import math
            if s["n_clean"] >= 8 and s["deg"] == s["deg"] and s["deg_se"] == s["deg_se"]:
                deg_rows.append(dict(deg_s_per_lap=float(s["deg"]), reliable=True))
        out.append(circuit_characteristics(dict(
            circuit=e.get("circuit"), name=e.get("name"), round=rnd,
            length_km=None if pd.isna(e.get("length_km")) else float(e.get("length_km")),
            total_laps=None if pd.isna(e.get("total_laps")) else int(e.get("total_laps"))), df, deg_rows))
    return dict(meta=meta(), circuits=out)


@app.get("/races/{season}/{rnd}")
def races(season: int, rnd: int):
    """Combined race header for the Races page: event, results, pits, quality flags."""
    ev = SRC.events(season)
    row = ev[ev["round"] == rnd]
    if row.empty:
        raise HTTPException(404, f"no event for {season} round {rnd}")
    e = row.iloc[0].to_dict()
    clean_e = {k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in e.items()}
    try:
        df = prepared(season, rnd, "R")
        kind_used = "R"
    except HTTPException:
        df = prepared(season, rnd, "Q")
        kind_used = "Q"
    res = SRC.results(season, rnd, kind_used)
    q = quality_report(df, _total_laps(season, rnd, df) if kind_used in RACE_LIKE else None)
    pits = SRC.pit_stops(season, rnd)
    return dict(meta=meta(), event={k: _clean(v) for k, v in clean_e.items()},
                kind=kind_used, results=_records(res), pit_stops=_records(pits),
                quality=q)


@app.get("/telemetry/{season}/{rnd}/{kind}/{driver}/{lap}")
def telemetry(season: int, rnd: int, kind: str, driver: str, lap: int):
    """Distance-aligned telemetry for one lap + detected corners.

    Samples are on a 25 m grid for payload size (storage is 5 m). Corner
    detection is generic and works on real FastF1 traces.
    """
    if not hasattr(SRC, "telemetry"):
        raise HTTPException(501, "telemetry not supported by this data source")
    tele = SRC.telemetry(season, rnd, kind, driver, int(lap))  # type: ignore[attr-defined]
    if tele is None or len(tele) == 0:
        raise HTTPException(404, f"no telemetry for {driver} lap {lap}")
    corners = detect_corners(tele)
    slim = tele[["distance_m", "speed", "throttle", "brake", "gear", "drs", "x", "y"]]
    return dict(meta=meta(), driver=driver, lap=int(lap),
                samples=_records(slim), corners=corners,
                label="Synthetic trace on mock source; measured trace on FastF1 source. Corners are detected, not official.")


@app.get("/corner-deltas/{season}/{rnd}/{kind}/{a}/{lap_a}/{b}/{lap_b}")
def corner_deltas_route(season: int, rnd: int, kind: str, a: str, lap_a: int, b: str, lap_b: int):
    """Per-corner entry/apex/exit + time deltas between two laps (B - A)."""
    if not hasattr(SRC, "telemetry"):
        raise HTTPException(501, "telemetry not supported by this data source")
    ta = SRC.telemetry(season, rnd, kind, a, int(lap_a))  # type: ignore[attr-defined]
    tb = SRC.telemetry(season, rnd, kind, b, int(lap_b))  # type: ignore[attr-defined]
    if ta is None or len(ta) == 0 or tb is None or len(tb) == 0:
        raise HTTPException(404, "one or both laps have no telemetry")
    d = corner_deltas(ta, tb, label_a=f"{a} lap {lap_a}", label_b=f"{b} lap {lap_b}")
    return dict(meta=meta(), result=d, method=BY_ID.get("corner_analysis"))


def _frames_with_fuel(season: int, kind: str = "R") -> tuple[dict[int, pd.DataFrame], dict[int, dict]]:
    """Prepared frames per round, refuel-corrected with per-circuit estimate where reliable."""
    return _frames_with_fuel_cached(season, kind)


@lru_cache(maxsize=8)
def _frames_with_fuel_cached(season: int, kind: str) -> tuple[dict[int, pd.DataFrame], dict[int, dict]]:
    ev = SRC.events(season)
    frames: dict[int, pd.DataFrame] = {}
    fuels: dict[int, dict] = {}
    for r in ev["round"].tolist():
        rnd = int(r)
        try:
            df = prepared(season, rnd, kind)
        except HTTPException:
            continue
        laps = SRC.laps(season, rnd, kind)
        total = _total_laps(season, rnd, laps)
        fest = estimate_fuel(df, total)
        fuels[rnd] = fest
        if fest.get("reliable") and fest.get("fuel_s_per_lap"):
            f = float(fest["fuel_s_per_lap"])
            df = df.copy()
            df["fuel_corr_time_s"] = df["lap_time_s"] - f * (total - df["lap_number"])
            df["fuel_used_s_per_lap"] = f
        else:
            df = df.copy()
            df["fuel_used_s_per_lap"] = FALLBACK_FUEL
        frames[rnd] = df
    if not frames:
        raise HTTPException(404, f"no {kind} laps for season {season}")
    return frames, fuels


@app.get("/fuel/{season}/{rnd}")
def fuel_route(season: int, rnd: int, kind: str = "R"):
    """Per-circuit fuel-burn estimate with reliability flag. Falls back to 0.035."""
    df = prepared(season, rnd, kind)
    laps = SRC.laps(season, rnd, kind)
    est = estimate_fuel(df, _total_laps(season, rnd, laps))
    return dict(meta=meta(), round=rnd, kind=kind, estimate=est,
                method=BY_ID.get("fuel_corrected_time"))


@app.get("/mixed-effects/{season}")
def mixed_effects(season: int, kind: str = "R"):
    """Season driver/car ratings from the ridge mixed model with round-bootstrap intervals."""
    return _mixed_cached(season, kind)


@lru_cache(maxsize=8)
def _mixed_cached(season: int, kind: str):
    frames, fuels = _frames_with_fuel(season, kind)
    res = mixed_with_intervals(frames)
    if "error" in res:
        raise HTTPException(404, res["error"])
    return dict(meta=meta(), kind=kind, result=res, fuel_per_round=fuels,
                method=BY_ID.get("mixed_effects"))


@app.get("/verdict/{season}/{rnd}/{a}/{b}")
def verdict(season: int, rnd: int, a: str, b: str):
    """Ranked likely causes of the gap between two drivers, with evidence and confidence."""
    df = prepared(season, rnd, "R")
    d = decompose(df, a, b)
    if "error" in d:
        raise HTTPException(404, d["error"])
    cons_list = consistency(df)
    cons = {c["driver"]: c for c in cons_list}
    q = quality_report(df, _total_laps(season, rnd, df))
    try:
        frames, _ = _frames_with_fuel(season, "R")
        seas = mixed_with_intervals(frames, n_boot=120)
        seas = None if "error" in seas else seas
    except HTTPException:
        seas = None
    panel = verdict_panel(a, b, d, cons, q, seas)
    return dict(meta=meta(), driver_a=a, driver_b=b, panel=panel,
                adjusted_gap_s=d.get("adjusted_gap_s"), total_raw_gap_s=d.get("total_raw_gap_s"),
                assumptions=d.get("assumptions", []))


@app.get("/strategy/{season}/{rnd}")
def strategy(season: int, rnd: int, kind: str = "R"):
    """Pit strategy, undercuts and effectiveness for one race."""
    df = prepared(season, rnd, kind)
    res = SRC.results(season, rnd, kind)
    pits = SRC.pit_stops(season, rnd)
    return dict(meta=meta(), strategies=strategy_table(df, res, pits),
                undercuts=undercuts(df),
                label="Strategies and positions observed; effectiveness pace is tyre-adjusted estimate.")


@app.get("/weather/{season}/{rnd}")
def weather_route(season: int, rnd: int, kind: str = "R"):
    """Weather-effect estimate: residual pace vs track temperature."""
    df = prepared(season, rnd, kind)
    try:
        w = SRC.weather(season, rnd, kind)  # type: ignore[attr-defined]
    except Exception:
        w = None
    eff = weather_effect(df, w)
    sample = []
    if w is not None and len(w):
        ww = w.head(90)
        sample = [{k: _clean(v) for k, v in r.items()} for r in ww.to_dict("records")]
    return dict(meta=meta(), effect=eff, weather=sample,
                method=BY_ID.get("weather_effect"))


@app.get("/reliability/{season}")
def reliability_route(season: int):
    """DNF counts and laps-completed distribution across the season. Observed."""
    ev = SRC.events(season)
    frames = []
    for r in ev["round"].tolist():
        try:
            frames.append(SRC.results(season, int(r), "R"))
        except Exception:
            continue
    return dict(meta=meta(), reliability=reliability(frames))


@app.get("/development/{season}")
def development_route(season: int, kind: str = "R"):
    """Per-round car gaps traced across the season with development slopes."""
    ev = SRC.events(season)
    per_round: dict[int, dict[str, dict]] = {}
    for r in ev["round"].tolist():
        rnd = int(r)
        try:
            df = prepared(season, rnd, kind)
            res = SRC.results(season, rnd, kind)
        except HTTPException:
            continue
        rows = team_summary(df, res, n_boot=80)
        per_round[rnd] = {t["team"]: {"gap": t["gap_to_best_car_s"], "ci": t["gap_ci95_s"]}
                          for t in rows}
    return dict(meta=meta(), development=development(per_round),
                method=BY_ID.get("season_development"))


@app.get("/predictions/{season}/{rnd}")
def predictions_route(season: int, rnd: int, kind: str = "R"):
    """Leave-one-round-out predicted gaps with intervals + backtest MAE when observed."""
    return _predictions_cached(season, int(rnd), kind)


@lru_cache(maxsize=32)
def _predictions_cached(season: int, rnd: int, kind: str):
    frames, _ = _frames_with_fuel(season, kind)
    res = predict_round(frames, int(rnd), n_boot=80)
    if "error" in res:
        raise HTTPException(404, res["error"])
    return dict(meta=meta(), kind=kind, result=res, method=BY_ID.get("prediction"))
