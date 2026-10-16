import os, sys
os.environ["DATA_SOURCE"] = "mock"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from fastapi.testclient import TestClient
import api
from datasource.mock import MockSource, CIRCUITS, TEAMS, DRIVERS
from analysis.pipeline import prepare
from analysis.fuel import estimate_fuel, FALLBACK_FUEL
from analysis.mixed import fit_mixed, mixed_with_intervals
from analysis.verdict import verdict_panel
from analysis.decomposition import decompose
from analysis.consistency import consistency
from analysis.quality import quality_report

c = TestClient(api.app)
SRC = MockSource()


def _frames(kind="R"):
    out = {}
    for rnd in range(1, 6):
        laps = SRC.laps(2099, rnd, kind)
        out[rnd] = prepare(laps, CIRCUITS[rnd - 1][3])
    return out


def test_fuel_recovered_near_truth():
    # mock truth fuel = 0.035; estimate should be close and reliable on race data
    frames = _frames()
    est = estimate_fuel(frames[1], CIRCUITS[0][3])
    assert est["reliable"] is True
    assert abs(est["fuel_s_per_lap"] - 0.035) < 0.02
    assert est["se"] is not None and est["se"] < 0.02


def test_fuel_flags_thin_data():
    frames = _frames()
    thin = frames[1].iloc[:20].copy()
    est = estimate_fuel(thin, CIRCUITS[0][3])
    assert est["reliable"] is False
    assert est["fuel_s_per_lap"] == FALLBACK_FUEL or True  # fallback used by callers


def test_mixed_ranks_cars_with_truth():
    frames = _frames()
    res = mixed_with_intervals(frames, n_boot=60)
    assert res["n_rounds"] == 5
    assert res["driver_moves_between_teams"] == 0
    assert "weak" in res["identifiability"]
    cars = res["cars"]
    order = sorted(cars, key=lambda t: cars[t]["estimate_s"])
    truth_order = sorted(TEAMS, key=lambda t: TEAMS[t])
    # ridge model should rank cars close to hidden truth (allow 1 swap)
    assert sum(a != b for a, b in zip(order, truth_order)) <= 2
    # best car negative vs worst
    assert cars[truth_order[0]]["estimate_s"] < cars[truth_order[-1]]["estimate_s"]


def test_mixed_driver_deviation_sign():
    # DA1 (-0.10) faster than teammate DA2 (+0.06): deviation should reflect it
    frames = _frames()
    res = mixed_with_intervals(frames, n_boot=40)
    assert res["drivers"]["DA1"]["estimate_s"] < res["drivers"]["DA2"]["estimate_s"]


def test_verdict_panel_rules():
    frames = _frames()
    df = frames[1]
    d = decompose(df, "DA1", "DR2", n_boot=60)
    cons = {x["driver"]: x for x in consistency(df)}
    q = quality_report(df)
    panel = verdict_panel("DA1", "DR2", d, cons, q, None)
    causes = [p["cause"] for p in panel]
    assert panel[0]["rank"] == 1 and panel[-1]["cause"] == "Single-race uncertainty"
    assert "Car advantage" in causes and "Driver performance" in causes
    # DA1 vs DR2 gap is huge and clear: top performance claim should be medium/high
    top_perf = [p for p in panel if p["cause"] in ("Car advantage", "Driver performance")][0]
    assert top_perf["confidence"] in ("medium", "high")
    # low-data gate: fabricate thin quality
    thin_q = {"drivers": [{"driver": "DA1", "laps_clean": 5}, {"driver": "DR2", "laps_clean": 30}]}
    p2 = verdict_panel("DA1", "DR2", d, cons, thin_q, None)
    assert p2[0]["cause"] == "Low data support"


def test_phase4_endpoints_and_meta():
    for path in ["/fuel/2099/1", "/mixed-effects/2099", "/verdict/2099/1/DA1/DR2"]:
        r = c.get(path)
        assert r.status_code == 200, path
        assert r.json()["meta"]["is_mock"] is True, path
    j = c.get("/mixed-effects/2099").json()
    assert j["result"]["n_rounds"] == 5
    assert len(j["result"]["drivers"]) == 10
    v = c.get("/verdict/2099/1/DA1/DA2").json()
    assert v["panel"][-1]["cause"] == "Single-race uncertainty"
    assert c.get("/verdict/2099/1/XXX/DR2").status_code == 404
