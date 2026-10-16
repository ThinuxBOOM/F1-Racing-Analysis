"""Strategy analysis: pit strategy, undercut/overcut, effectiveness. Observed + MODEL ESTIMATE.

Definitions (also in methodology):
  * Pit loss: pit-lane duration vs running at median clean pace. Observed.
  * Undercut attempt: driver pits earlier than a rival they trailed, and is
    ahead within 3 laps after their stop. Observed from positions + pit laps.
  * Strategy effectiveness: ranks observed strategies (compound sequences) by
    median fuel-corrected clean pace of their users. MODEL ESTIMATE only in
    that pace is tyre-adjusted; the ranking itself is observed ordering.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def strategy_table(prepared: pd.DataFrame, results: pd.DataFrame,
                   pits: pd.DataFrame) -> list[dict]:
    clean = prepared[prepared["is_clean"]]
    med_pace = (clean.groupby("driver")["fuel_corr_time_s"].median().to_dict()
                if len(clean) else {})
    rows = []
    for drv, g in prepared.groupby("driver"):
        g = g.sort_values("lap_number")
        stops = sorted(g[g["pit_in"]]["lap_number"].astype(int).tolist())
        seq = []
        for _, s in g.groupby("stint_number"):
            comp = s["compound"].iloc[0]
            seq.append(str(comp))
        team = g["team"].iloc[0]
        n_clean = int((g["is_clean"]).sum())
        rows.append(dict(
            driver=drv, team=str(team), n_stops=len(stops), pit_laps=stops,
            compounds=seq, strategy=" > ".join(seq) if seq else "?",
            n_clean=n_clean,
            median_adj_pace_s=None if drv not in med_pace or med_pace[drv] != med_pace[drv]
            else round(float(med_pace[drv]), 3),
        ))
    # effectiveness: rank strategies by mean of users' median pace
    strat_pace: dict[str, list[float]] = {}
    for r in rows:
        if r["median_adj_pace_s"] is not None:
            strat_pace.setdefault(r["strategy"], []).append(r["median_adj_pace_s"])
    strat_rank = {s: float(np.mean(v)) for s, v in strat_pace.items()}
    best = min(strat_rank.values()) if strat_rank else 0
    for r in rows:
        r["strategy_gap_to_best_s"] = (round(strat_rank[r["strategy"]] - best, 3)
                                       if r["strategy"] in strat_rank else None)
    # attach pit positions
    pit_by_driver = {d: list(p.sort_values("lap").to_dict("records"))
                     for d, p in pits.groupby("driver")} if pits is not None and len(pits) else {}
    for r in rows:
        r["pit_stops"] = [{k: (None if pd.isna(v) else v) for k, v in p.items()
                           if k in ("lap", "duration_s", "position_before", "position_after")}
                          for p in pit_by_driver.get(r["driver"], [])]
    rows.sort(key=lambda r: (r["median_adj_pace_s"] is None, r["median_adj_pace_s"] or 0))
    return rows


def undercuts(prepared: pd.DataFrame) -> list[dict]:
    """Detect undercut attempts: A pits, rival pits later, A ahead within 3 laps.

    Uses the position column (running order). Returns list with attempt,
    success flag, laps involved. Observed; no modelling.
    """
    if "position" not in prepared.columns:
        return []
    piv = prepared.pivot_table(index="lap_number", columns="driver",
                               values="position", aggfunc="first").sort_index()
    pit_laps: dict[str, list[int]] = {}
    for drv, g in prepared.groupby("driver"):
        pit_laps[drv] = sorted(g[g["pit_in"]]["lap_number"].astype(int).tolist())
    out = []
    drivers = list(pit_laps)
    for a in drivers:
        for b in drivers:
            if a == b:
                continue
            for la in pit_laps[a]:
                # rival pits later (overcut window) within 6 laps
                later = [lb for lb in pit_laps[b] if 0 < lb - la <= 6]
                if not later:
                    continue
                lb = min(later)
                # A trailed B before A's stop?
                try:
                    before_a = piv.loc[la - 1, a] if (la - 1) in piv.index else None
                    before_b = piv.loc[la - 1, b] if (la - 1) in piv.index else None
                    after_a = piv.loc[min(lb + 3, piv.index.max()), a]
                    after_b = piv.loc[min(lb + 3, piv.index.max()), b]
                except Exception:
                    continue
                if pd.isna(before_a) or pd.isna(before_b) or pd.isna(after_a) or pd.isna(after_b):
                    continue
                if before_a > before_b and after_a < after_b:
                    out.append(dict(passer=a, rival=b, pass_lap=int(la), rival_pit_lap=int(lb),
                                    before=f"P{int(before_a)} vs P{int(before_b)}",
                                    after=f"P{int(after_a)} vs P{int(after_b)}",
                                    kind="undercut"))
    # dedupe: keep earliest per pair
    seen, uniq = set(), []
    for u in sorted(out, key=lambda x: x["pass_lap"]):
        k = (u["passer"], u["rival"])
        if k not in seen:
            seen.add(k)
            uniq.append(u)
    return uniq
