import numpy as np, pandas as pd, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import metrics as m


def synth(driver, base, deg, n=40, seed=0, total=60):
    rng = np.random.default_rng(seed)
    lap = np.arange(2, 2 + n)
    t = base + deg * (lap - 2) - m.FUEL_EFFECT_S_PER_LAP * (lap - 2) + rng.normal(0, 0.12, n)
    return pd.DataFrame(dict(driver=driver, lap_number=lap, lap_time_s=t, tyre_age=lap - 1,
                             pit_in=False, pit_out=False, track_status="1", deleted=False))


def test_deg_recovered():
    df = synth("AAA", 90.0, 0.06)
    df = m.flag_clean_laps(df)
    df["fuel_corr_time_s"] = m.fuel_correct(df, total_laps=60)
    out = m.stint_degradation(df)
    assert abs(out["deg"] - 0.06) < 0.02
    assert out["deg_se"] > 0


def test_cleaning_flags():
    df = synth("AAA", 90.0, 0.0, n=10)
    df.loc[3, "pit_in"] = True
    df.loc[4, "track_status"] = "4"
    df.loc[5, "lap_time_s"] = 200.0
    df = m.flag_clean_laps(df)
    reasons = set(df["exclude_reason"].dropna())
    assert {"in_out", "sc_vsc_yellow", "slow"} <= reasons


def test_teammate_delta_detects_gap():
    rng = np.random.default_rng(1)
    a = pd.Series(90.0 + rng.normal(0, 0.2, 40))
    b = pd.Series(90.25 + rng.normal(0, 0.2, 40))
    d = m.teammate_delta(a, b)
    assert d["delta"] < 0 and d["ci_high"] < 0
    assert "Driver A" in m.verdict(d)


def test_teammate_delta_no_gap():
    rng = np.random.default_rng(2)
    a = pd.Series(90.0 + rng.normal(0, 0.3, 30))
    b = pd.Series(90.0 + rng.normal(0, 0.3, 30))
    d = m.teammate_delta(a, b)
    assert d["ci_low"] <= 0 <= d["ci_high"]
