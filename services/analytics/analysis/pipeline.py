"""Turn a raw laps frame into an analysis-ready frame (clean flags + fuel correction)."""
from __future__ import annotations
import pandas as pd
import metrics as m


def prepare(laps: pd.DataFrame, total_laps: int, race_like: bool = True) -> pd.DataFrame:
    df = laps.copy()
    df["deleted"] = df["deleted"].fillna(False).astype(bool)
    df["pit_in"] = df["pit_in"].fillna(False).astype(bool)
    df["pit_out"] = df["pit_out"].fillna(False).astype(bool)
    df = m.flag_clean_laps(df)
    df["fuel_corr_time_s"] = m.fuel_correct(df, total_laps) if race_like else df["lap_time_s"]
    return df
