import os, sys
os.environ["DATA_SOURCE"] = "mock"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from fastapi.testclient import TestClient
import api
from datasource.mock import MockSource
from analysis.pipeline import prepare
from analysis.teams import team_summary
from analysis.tyres import tyre_report, compound_offsets
from analysis.season import season_standings, circuit_characteristics

c = TestClient(api.app)
SRC = MockSource()


def test_teams_endpoint_shape_and_car_gap():
    j = c.get("/teams/2099/1/R").json()
    assert j["meta"]["is_mock"] is True
    assert len(j["teams"]) == 5
    t0 = j["teams"][0]
    assert t0["gap_to_best_car_s"] == 0.0
    assert "MODEL ESTIMATE" in j["label"]
    # best car should be Demo Aero Works (true car -0.35)
    assert t0["team"] == "Demo Aero Works"
    assert len(t0["gap_ci95_s"]) == 2


def test_team_summary_matches_truth_order():
    from datasource.mock import TEAMS
    laps = SRC.laps(2099, 1, "R")
    df = prepare(laps, 52)
    res = SRC.results(2099, 1, "R")
    rows = team_summary(df, res, n_boot=60)
    order = [r["team"] for r in rows]
    truth_order = sorted(TEAMS, key=lambda t: TEAMS[t])
    # resolved car pace should rank teams close to hidden truth (allow 1 swap from noise)
    assert sum(a != b for a, b in zip(order, truth_order)) <= 2


def test_tyres_endpoint_and_offsets():
    j = c.get("/tyres/2099/1/R").json()
    assert j["meta"]["is_mock"] is True
    comps = {r["compound"]: r for r in j["compounds"]}
    assert set(comps) >= {"SOFT", "MEDIUM", "HARD"}
    # SOFT should be fastest adjusted (most negative), HARD slowest
    assert comps["SOFT"]["adjusted_offset_vs_medium_s"] < 0
    assert comps["HARD"]["adjusted_offset_vs_medium_s"] > 0
    # offsets should be near mock truth (-0.55, +0.45) within 0.25
    assert abs(comps["SOFT"]["adjusted_offset_vs_medium_s"] - (-0.55)) < 0.25
    assert abs(comps["HARD"]["adjusted_offset_vs_medium_s"] - 0.45) < 0.25


def test_standings_endpoint_sums_points():
    j = c.get("/standings/2099").json()
    assert j["meta"]["is_mock"] is True
    assert len(j["standings"]["drivers"]) == 10
    assert len(j["standings"]["teams"]) == 5
    tot = sum(d["points"] for d in j["standings"]["drivers"])
    # 5 races * (25+18+15+12+10+8+6+4+2+1=101) minus DNF zeros, must be <= 505
    assert 0 < tot <= 505


def test_circuits_endpoint_derived():
    j = c.get("/circuits/2099").json()
    assert len(j["circuits"]) == 5
    c0 = j["circuits"][0]
    assert c0["avg_speed_kmh"] and 150 < c0["avg_speed_kmh"] < 350
    assert c0["braking_zones"] is None  # telemetry-only, never guessed
    assert c0["mean_deg_s_per_lap"] is not None


def test_races_endpoint_combines_sources():
    j = c.get("/races/2099/1").json()
    assert j["event"]["round"] == 1
    assert len(j["results"]) == 10
    assert "drivers" in j["quality"]
    assert isinstance(j["pit_stops"], list)


def test_every_new_payload_carries_meta():
    for path in ["/teams/2099/1/R", "/tyres/2099/1/R", "/standings/2099",
                 "/circuits/2099", "/races/2099/1"]:
        r = c.get(path)
        assert r.status_code == 200, path
        assert r.json()["meta"]["is_mock"] is True, path
