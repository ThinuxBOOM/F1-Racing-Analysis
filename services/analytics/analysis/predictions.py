"""Transparent predictions with intervals. MODEL ESTIMATE, never certain.

Method: leave-one-round-out ridge mixed model (same specification as
analysis/mixed.py). To predict round T, fit on all other rounds, then
predicted relative pace = driver_rating + car_rating (circuit and intercept
cancel in gaps). The predicted gap to field-best and its 95% interval come
from the round-bootstrap distribution of (driver+car) effects.

Backtest: when round T has observed data, report mean absolute error of
predicted gaps vs observed tyre-adjusted gaps, so users see calibration.
Future rounds (no observed laps) return predictions with intervals and a
note that accuracy is unknown until observed.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from analysis.mixed import fit_mixed, mixed_with_intervals


def predict_round(frames: dict[int, pd.DataFrame], target: int,
                  n_boot: int = 120, seed: int = 99) -> dict:
    rounds = sorted(frames)
    train = {r: df for r, df in frames.items() if r != target}
    if not train:
        return dict(error="no training rounds (need at least one other round)")
    res = mixed_with_intervals(train, n_boot=n_boot, seed=seed)
    if "error" in res:
        return res
    # predicted relative pace = driver + car
    preds = {}
    for d in res["drivers"]:
        # find team
        team = None
        for t, members in res["team_members"].items():
            if d in members:
                team = t
                break
        dv, cv = res["drivers"][d], res["cars"][team or ""]
        est = dv["estimate_s"] + cv["estimate_s"]
        # combine intervals conservatively: sum of half-widths
        hw = (dv["ci95_s"][1] - dv["ci95_s"][0]) / 2 + (cv["ci95_s"][1] - cv["ci95_s"][0]) / 2
        preds[d] = dict(estimate_s=round(est, 3),
                        ci95_s=[round(est - hw, 3), round(est + hw, 3)],
                        team=team)
    # centre on predicted best
    best = min(v["estimate_s"] for v in preds.values())
    for d in preds:
        e = preds[d]["estimate_s"]
        lo, hi = preds[d]["ci95_s"]
        preds[d] = dict(team=preds[d]["team"], gap_to_pred_best_s=round(e - best, 3),
                        ci95_s=[round(lo - best, 3), round(hi - best, 3)])
    order = sorted(preds, key=lambda d: preds[d]["gap_to_pred_best_s"])
    out = dict(target_round=int(target), trained_on=sorted(train),
               predictions={d: preds[d] for d in order},
               label="MODEL ESTIMATE with 95% intervals. Lower gap = faster.",
               n_train_rounds=len(train))
    # backtest if observed
    if target in frames:
        from analysis.decomposition import driver_effects
        try:
            eff = driver_effects(frames[target])
            if eff:
                emin = min(eff.values())
                obs = {d: eff[d] - emin for d in eff}
                errs = [abs(preds[d]["gap_to_pred_best_s"] - obs[d])
                        for d in preds if d in obs]
                if errs:
                    out["backtest_mae_s"] = round(float(np.mean(errs)), 3)
                    out["backtest_note"] = ("Mean |predicted gap - observed tyre-adjusted gap| "
                                            "on the held-out round. Lower is better; compare to ~0.1-0.3 s typical gaps.")
        except Exception:
            pass
    else:
        out["backtest_note"] = "Target round has no observed laps yet; accuracy unknown until observed."
    return out
