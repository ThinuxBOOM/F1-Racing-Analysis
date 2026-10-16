import os, sys
os.environ["DATA_SOURCE"] = "mock"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ingest"))
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
import api
from analysis.telemetry import (
    synthesize_telemetry, detect_corners, corner_deltas, circuit_layout)

c = TestClient(api.app)


def test_synthesis_is_deterministic_and_shaped():
    a = synthesize_telemetry("Demo Ring North", 5.2, "DA1", 5, 2099, 1)
    b = synthesize_telemetry("Demo Ring North", 5.2, "DA1", 5, 2099, 1)
    assert a.equals(b)
    assert list(a.columns) == ["distance_m", "speed", "throttle", "brake", "gear", "drs", "x", "y"]
    assert len(a) > 150
    # faster car package should be faster on average than a slow one
    fast = synthesize_telemetry("Demo Ring North", 5.2, "DA1", 5, car_bonus_kmh=7.0,
                                driver_apex_bonus_kmh=1.5, noise_sd_kmh=0.0)
    slow = synthesize_telemetry("Demo Ring North", 5.2, "DA1", 5, car_bonus_kmh=-7.0,
                                driver_apex_bonus_kmh=-1.5, noise_sd_kmh=0.0)
    assert fast["speed"].mean() > slow["speed"].mean() + 2.0


def test_corner_detection_finds_layout_corners():
    tele = synthesize_telemetry("Demo Ring North", 5.2, "DA1", 5, noise_sd_kmh=0.2)
    layout = circuit_layout("Demo Ring North", 5200.0)
    corners = detect_corners(tele)
    # detector should recover most true corners (allow ±200 m on distance)
    assert len(corners) >= max(len(layout) - 2, 4)
    for dist, _, _ in layout[:3]:
        assert any(abs(k["apex_m"] - dist) < 200 for k in corners), dist
    k0 = corners[0]
    assert k0["entry_m"] < k0["apex_m"] < k0["exit_m"]
    assert k0["apex_kmh"] < k0["entry_kmh"]


def test_corner_deltas_sign_and_magnitude():
    base_kw = dict(circuit="Demo Ring North", length_km=5.2, season=2099, rnd=1)
    a = synthesize_telemetry(driver="DA1", lap_number=10, car_bonus_kmh=0.0,
                             driver_apex_bonus_kmh=0.0, noise_sd_kmh=0.0, **base_kw)
    b = synthesize_telemetry(driver="DR2", lap_number=10, car_bonus_kmh=-9.0,
                             driver_apex_bonus_kmh=-2.0, noise_sd_kmh=0.0, **base_kw)
    d = corner_deltas(a, b, "A", "B")
    assert d["n_corners"] > 0
    # B is slower everywhere -> negative speed deltas, positive time delta
    assert d["mean_speed_delta_kmh"] < -1.0
    assert d["predicted_lap_delta_s"] > 0
    apex_deltas = [row["apex_delta_kmh"] for row in d["corners"]]
    assert sum(apex_deltas) / len(apex_deltas) < -0.5
    # per-corner: B never faster by more than the grid quantisation (70 km/h floor clips hairpins)
    for row in d["corners"]:
        assert row["apex_delta_kmh"] <= 0.5


def test_telemetry_endpoints_and_meta():
    # pick a real clean lap from the mock race
    laps = c.get("/pace/2099/1/R").json()["laps"]
    clean = [l for l in laps if l["is_clean"] and l["driver"] == "DA1"]
    assert clean
    lap_no = clean[len(clean) // 2]["lap_number"]
    j = c.get(f"/telemetry/2099/1/R/DA1/{lap_no}").json()
    assert j["meta"]["is_mock"] is True
    assert len(j["samples"]) > 100
    assert len(j["corners"]) >= 4
    assert {"distance_m", "speed", "throttle", "x", "y"} <= set(j["samples"][0])
    k = c.get(f"/corner-deltas/2099/1/R/DA1/{lap_no}/DR2/{lap_no}").json()
    assert k["meta"]["is_mock"] is True
    assert k["result"]["n_corners"] > 0
    assert c.get("/telemetry/2099/1/R/XXX/999").status_code == 404


def test_resample_telemetry_pure_function():
    from ingest import resample_telemetry
    dist = np.arange(0, 1000, 10, dtype=float)
    car = pd.DataFrame(dict(Distance=dist, Speed=300 - dist * 0.05,
                            Throttle=100, Brake=0, nGear=7, DRS=0, RPM=12000))
    pos = pd.DataFrame(dict(Distance=dist, X=dist, Y=np.sin(dist / 100) * 500))
    out = resample_telemetry(car, pos, step_m=25)
    assert set(out.columns) == {"distance_m", "speed", "throttle", "brake",
                                "gear", "rpm", "drs", "x", "y"}
    assert len(out) == 40
    assert out["distance_m"].iloc[0] == 0
    # speed should fall with distance
    assert out["speed"].iloc[0] > out["speed"].iloc[-1]
