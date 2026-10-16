"""Season-level aggregates: standings, team points, circuit characteristics.

All standings are observed facts (sums of points / finishes). Circuit
characteristics are computed from timing data only — never hand-labelled:
  * avg_speed_kmh = length_km / median clean fuel-corrected lap * 3600
  * mean_deg = mean of reliable stint degradation slopes at that round
  * overtaking_index = total position changes between consecutive laps
    divided by race laps (0 = processional). Uses the position column.
Braking-zone / full-throttle shares need telemetry and are returned as None.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def season_standings(all_results: list[pd.DataFrame]) -> dict:
    """all_results: list of results frames (one per round) with columns
    driver, team, finish_pos, points, status."""
    if not all_results:
        return dict(drivers=[], teams=[])
    df = pd.concat(all_results, ignore_index=True)
    # driver standings
    drv_rows = []
    for drv, g in df.groupby("driver"):
        team = g["team"].mode().iloc[0] if len(g) else "?"
        pts = float(g["points"].fillna(0).sum())
        wins = int((g["finish_pos"] == 1).sum())
        podiums = int((g["finish_pos"] <= 3).sum())
        starts = int(len(g))
        dnfs = int((~g["status"].isin(["Finished", "finished"])).sum()) if "status" in g else 0
        drv_rows.append(dict(driver=drv, team=str(team), points=pts, wins=wins,
                             podiums=podiums, starts=starts, dnfs=dnfs))
    drv_rows.sort(key=lambda r: (-r["points"], -r["wins"]))
    # team standings
    team_rows = []
    for team, g in df.groupby("team"):
        pts = float(g["points"].fillna(0).sum())
        wins = int((g["finish_pos"] == 1).sum())
        team_rows.append(dict(team=team, points=pts, wins=wins,
                              drivers=sorted(g["driver"].unique().tolist())))
    team_rows.sort(key=lambda r: -r["points"])
    return dict(drivers=drv_rows, teams=team_rows)


def circuit_characteristics(event: dict, prepared: pd.DataFrame,
                            stints: list[dict] | None = None) -> dict:
    """event: dict with circuit, length_km, total_laps. prepared: analysis-ready
    laps frame for that round. stints: optional stint rows with deg values."""
    clean = prepared[prepared["is_clean"]].dropna(subset=["fuel_corr_time_s"])
    med = float(clean["fuel_corr_time_s"].median()) if len(clean) else None
    length = event.get("length_km")
    avg_speed = round(float(length) / med * 3600, 1) if med and length else None
    degs = []
    if stints:
        for s in stints:
            v = s.get("deg_s_per_lap")
            if v is not None and s.get("reliable"):
                degs.append(v)
    mean_deg = round(float(np.mean(degs)), 4) if degs else None
    # overtaking index: position changes per lap
    overtakes = None
    if "position" in prepared.columns and "lap_number" in prepared.columns:
        try:
            piv = prepared.pivot_table(index="lap_number", columns="driver",
                                       values="position", aggfunc="first")
            piv = piv.sort_index()
            changes = 0
            laps_compared = 0
            prev = None
            for _, row in piv.iterrows():
                if prev is not None:
                    # count drivers whose position changed and who were present both laps
                    both = row.notna() & prev.notna()
                    if both.sum() >= 2:
                        changes += int((row[both] != prev[both]).sum() // 2)
                        laps_compared += 1
                prev = row
            if laps_compared:
                overtakes = round(changes / laps_compared, 3)
        except Exception:
            overtakes = None
    return dict(
        circuit=event.get("circuit"),
        name=event.get("name"),
        round=event.get("round"),
        length_km=length,
        total_laps=event.get("total_laps"),
        avg_speed_kmh=avg_speed,
        mean_deg_s_per_lap=mean_deg,
        overtake_index=overtakes,
        braking_zones=None,
        full_throttle_pct=None,
        telemetry_note="Braking zones and full-throttle share need telemetry (Phase 3).",
    )
