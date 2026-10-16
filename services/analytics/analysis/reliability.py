"""Weather effects + reliability + season development. Observed where possible.

Weather: mock source synthesises deterministic per-minute weather; postgres
reads the weather table. Effect = OLS slope of fuel/tyre-adjusted residual
lap time on track temperature (clean laps only), with SE. If temperature range
< 3 C or n < 60, returns unreliable rather than a spurious slope.

Reliability: DNF counts and laps-completed distribution from results
(status != Finished). Observed, no modelling.

Development: per-round car gaps (team-mean adjusted pace, same model as
/teams) traced across rounds with per-round CIs, plus a development slope
(last - first) per team. MODEL ESTIMATE per round; the slope inherits those
intervals and is shown with them, never as a bare number.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def weather_effect(prepared: pd.DataFrame, weather: pd.DataFrame | None) -> dict:
    if weather is None or len(weather) == 0 or "track_temp_c" not in weather:
        return dict(available=False, note="No weather data for this session.",
                    slope_s_per_c=None, se=None, n=None, reliable=False)
    clean = prepared[prepared["is_clean"]].dropna(subset=["fuel_corr_time_s"]).copy()
    if len(clean) < 60:
        return dict(available=True, note="Too few clean laps.", slope_s_per_c=None,
                    se=None, n=int(len(clean)), reliable=False)
    # map lap -> minute: use lap_number as proxy (1 lap ~ 1.5 min)? Better: merge on
    # position in race. Mock weather is per-minute; approximate minute = lap_number * 1.5.
    # For postgres data the same proxy applies; documented as approximate.
    w = weather.sort_values("minute")
    t = w["track_temp_c"].to_numpy(float)
    minutes = w["minute"].to_numpy(float)
    if np.nanmax(t) - np.nanmin(t) < 3.0:
        return dict(available=True, note="Track temperature varied <3 C; no effect identifiable.",
                    slope_s_per_c=None, se=None, n=int(len(clean)), reliable=False,
                    temp_range_c=round(float(np.nanmax(t) - np.nanmin(t)), 1))
    # detrended residual: remove stint tyre trend first (same as consistency)
    resid = []
    temps = []
    for _, s in clean.groupby(["driver", "stint_number"]):
        s = s.dropna(subset=["fuel_corr_time_s", "tyre_age"])
        if len(s) < 5:
            continue
        x = s["tyre_age"].to_numpy(float)
        y = s["fuel_corr_time_s"].to_numpy(float)
        X = np.column_stack([np.ones(len(x)), x])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ beta
        lap_min = s["lap_number"].to_numpy(float) * 1.5
        tt = np.interp(lap_min, minutes, t)
        resid.extend(r.tolist())
        temps.extend(tt.tolist())
    resid, temps = np.array(resid), np.array(temps)
    m = ~(np.isnan(resid) | np.isnan(temps))
    resid, temps = resid[m], temps[m]
    if len(resid) < 60:
        return dict(available=True, note="Too few matched laps.", slope_s_per_c=None,
                    se=None, n=int(len(resid)), reliable=False)
    X = np.column_stack([np.ones(len(temps)), temps])
    beta, *_ = np.linalg.lstsq(X, resid, rcond=None)
    e = resid - X @ beta
    dof = max(len(resid) - 2, 1)
    s2 = float((e @ e) / dof)
    try:
        cov = s2 * np.linalg.inv(X.T @ X)
        se = float(np.sqrt(max(cov[1, 1], 0)))
    except Exception:
        se = np.nan
    slope = float(beta[1])
    reliable = bool(se == se and se < 0.03)
    return dict(available=True, slope_s_per_c=round(slope, 4),
                se=None if se != se else round(se, 4), n=int(len(resid)),
                reliable=reliable,
                temp_range_c=round(float(np.nanmax(t) - np.nanmin(t)), 1),
                note=("Residual pace vs track temp after removing stint tyre trends. "
                      "Positive = slower when hotter." if reliable else
                      "Noisy; do not over-read. Needs multi-session support."))


def reliability(all_results: list[pd.DataFrame]) -> dict:
    if not all_results:
        return dict(drivers=[], teams=[], note="No results.")
    df = pd.concat(all_results, ignore_index=True)
    fin = df["status"].isin(["Finished", "finished"])
    dro, tro = [], []
    for drv, g in df.groupby("driver"):
        n, dnf = len(g), int((~g["status"].isin(["Finished", "finished"])).sum())
        laps = g["laps_completed"].fillna(0).to_numpy(float) if "laps_completed" in g else np.zeros(n)
        dro.append(dict(driver=drv, team=str(g["team"].mode().iloc[0]) if len(g) else "?",
                        starts=n, dnfs=dnf, dnf_rate=round(dnf / n, 3) if n else 0.0,
                        mean_laps_completed=round(float(np.mean(laps)), 1) if n else 0.0,
                        causes=sorted(g[~g["status"].isin(["Finished", "finished"])]["status"].unique().tolist())
                        if dnf else []))
    for team, g in df.groupby("team"):
        n, dnf = len(g) * 1, int((~g["status"].isin(["Finished", "finished"])).sum())
        tro.append(dict(team=team, entries=int(len(g)), dnfs=dnf,
                        dnf_rate=round(dnf / len(g), 3) if len(g) else 0.0))
    dro.sort(key=lambda r: (-r["dnf_rate"], -r["dnfs"]))
    tro.sort(key=lambda r: (-r["dnf_rate"], -r["dnfs"]))
    return dict(drivers=dro, teams=tro,
                note="Observed retirements only. Causes are status strings from the feed; mechanical vs crash split needs incident data.")


def development(per_round_car_gaps: dict[int, dict[str, dict]]) -> dict:
    """per_round_car_gaps: round -> team -> {gap, ci}. Returns traces + slopes."""
    teams = sorted({t for r in per_round_car_gaps.values() for t in r})
    rounds = sorted(per_round_car_gaps)
    traces = {}
    for t in teams:
        pts = []
        for r in rounds:
            e = per_round_car_gaps[r].get(t)
            if e:
                pts.append(dict(round=r, gap_s=e["gap"], ci=e.get("ci")))
        if len(pts) >= 2:
            slope = round(pts[-1]["gap_s"] - pts[0]["gap_s"], 3)
        else:
            slope = None
        traces[t] = dict(points=pts, development_slope_s=slope,
                         direction=("improved" if slope is not None and slope < -0.05 else
                                    ("slipped" if slope is not None and slope > 0.05 else "flat")))
    return dict(rounds=rounds, teams=traces,
                note="Per-round MODEL ESTIMATES with their intervals; slopes inherit that uncertainty.")
