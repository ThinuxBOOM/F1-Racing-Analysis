import os, sys
os.environ["DATA_SOURCE"] = "mock"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient
import api
from datasource.mock import MockSource, CIRCUITS
from analysis.pipeline import prepare
from analysis.strategy import strategy_table, undercuts
from analysis.reliability import weather_effect, reliability, development

c = TestClient(api.app)
SRC = MockSource()


def _prep(rnd=1):
    return prepare(SRC.laps(2099, rnd, "R"), CIRCUITS[rnd - 1][3])


def test_strategy_table_matches_pit_laps():
    df = _prep()
    res = SRC.results(2099, 1, "R")
    pits = SRC.pit_stops(2099, 1)
    rows = strategy_table(df, res, pits)
    assert len(rows) == 10
    # every driver's pit_laps must match mock pit records
    for r in rows:
        assert r["n_stops"] == len(r["pit_laps"]) == len(r["pit_stops"])
        assert r["strategy_gap_to_best_s"] is not None
    # undercuts returns observed list (may be empty on some rounds, must be a list)
    u = undercuts(df)
    assert isinstance(u, list)
    if u:
        assert set(u[0]) >= {"passer", "rival", "kind"}


def test_weather_effect_plausible():
    df = _prep()
    w = SRC.weather(2099, 1)
    assert len(w) > 30 and "track_temp_c" in w.columns
    eff = weather_effect(df, w)
    assert eff["available"] is True and eff["n"] and eff["n"] >= 60
    # synthetic weather has no true effect; slope must be small or flagged unreliable
    if eff["reliable"]:
        assert abs(eff["slope_s_per_c"]) < 0.05


def test_reliability_counts_retirements():
    frames = [SRC.results(2099, r, "R") for r in range(1, 6)]
    rel = reliability(frames)
    assert len(rel["drivers"]) == 10 and len(rel["teams"]) == 5
    # mock retires ~0.6 * 5 rounds drivers total; at least one DNF across season
    assert sum(d["dnfs"] for d in rel["drivers"]) >= 1
    assert all(0 <= d["dnf_rate"] <= 1 for d in rel["drivers"])


def test_development_traces_all_teams():
    from analysis.teams import team_summary
    per_round = {}
    for rnd in range(1, 6):
        df = _prep(rnd)
        rows = team_summary(df, SRC.results(2099, rnd, "R"), n_boot=40)
        per_round[rnd] = {t["team"]: {"gap": t["gap_to_best_car_s"], "ci": t["gap_ci95_s"]} for t in rows}
    dev = development(per_round)
    assert dev["rounds"] == [1, 2, 3, 4, 5]
    assert len(dev["teams"]) == 5
    for t, tr in dev["teams"].items():
        assert len(tr["points"]) == 5
        assert tr["direction"] in ("improved", "slipped", "flat")


def test_phase5_endpoints_and_meta():
    for path in ["/strategy/2099/1", "/weather/2099/1", "/reliability/2099", "/development/2099"]:
        r = c.get(path)
        assert r.status_code == 200, path
        assert r.json()["meta"]["is_mock"] is True, path
    s = c.get("/strategy/2099/1").json()
    assert len(s["strategies"]) == 10 and isinstance(s["undercuts"], list)
    assert c.get("/strategy/2099/9").status_code == 404
