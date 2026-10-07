"""Data-quality detector. Reports what was excluded and why, so users know when data is thin."""
from __future__ import annotations
import pandas as pd

REASON_LABEL = {"no_time": "missing lap time", "lap1": "lap 1", "in_out": "pit in/out lap",
                "sc_vsc_yellow": "neutralised (SC/VSC/yellow/red)", "deleted": "time deleted",
                "slow": "outlier (>7% off own median)"}


def quality_report(prepared: pd.DataFrame, expected_laps: int | None = None) -> dict:
    rows = []
    for drv, g in prepared.groupby("driver"):
        present = len(g)
        counts = g["exclude_reason"].value_counts().to_dict()
        clean = int(g["is_clean"].sum())
        exp = expected_laps if expected_laps else int(g["lap_number"].max())
        rows.append(dict(driver=drv, team=g["team"].iloc[0], laps_expected=exp,
                         laps_present=present, laps_clean=clean,
                         laps_missing_from_feed=max(exp - present, 0) if expected_laps else 0,
                         completeness=round(clean / present, 3) if present else 0.0,
                         excluded={REASON_LABEL.get(k, k): int(v) for k, v in counts.items()}))
    comp = [r["completeness"] for r in rows]
    flags = []
    for r in rows:
        if r["laps_clean"] < 15:
            flags.append(f"{r['driver']}: only {r['laps_clean']} clean laps; pace estimates are low-confidence")
    return dict(drivers=rows, mean_completeness=round(sum(comp) / len(comp), 3) if comp else 0.0, flags=flags)
