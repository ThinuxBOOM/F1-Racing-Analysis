import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from datasource.mock import MockSource, CIRCUITS
from analysis.pipeline import prepare
from analysis.decomposition import decompose
from analysis.consistency import consistency
from analysis.quality import quality_report

SRC = MockSource()


def race(rnd=1):
    laps = SRC.laps(2099, rnd, "R")
    return prepare(laps, CIRCUITS[rnd - 1][3])


def test_mock_schema_and_label():
    assert SRC.is_mock and SRC.name == "mock"
    from datasource.base import LAP_COLUMNS
    assert list(SRC.laps(2099, 1, "R").columns) == LAP_COLUMNS


def test_quality_detects_exclusions():
    q = quality_report(race(), expected_laps=CIRCUITS[0][3])
    assert 0.5 < q["mean_completeness"] < 1.0
    assert any("pit in/out lap" in d["excluded"] for d in q["drivers"])
    assert any("neutralised (SC/VSC/yellow/red)" in d["excluded"] for d in q["drivers"])


def test_decomposition_total_matches_truth():
    # DA1 (car -0.35, driver -0.10) vs DR2 (car 0.45, driver 0.12): true pace gap = -0.80 - 0.22 + ... = -1.02
    truth = (SRC.truth["car"]["Demo Aero Works"] + SRC.truth["driver"]["DA1"]) - \
            (SRC.truth["car"]["Demo Racing Co"] + SRC.truth["driver"]["DR2"])
    d = decompose(race(), "DA1", "DR2", n_boot=120)
    lo, hi = d["adjusted_gap_s"]["ci95_s"]
    assert abs(d["adjusted_gap_s"]["estimate_s"] - truth) < 0.12
    assert lo - 0.05 <= truth <= hi + 0.05
    comp = d["components"]
    # car part must carry most of the gap, and parts must sum to the raw gap
    assert abs(comp["car"]["estimate_s"]) > abs(comp["driver"]["estimate_s"])
    parts = sum(v["estimate_s"] for v in comp.values())
    assert abs(parts - d["total_raw_gap_s"]) < 0.01
    assert "MODEL ESTIMATE" in d["label"]


def test_decomposition_teammates_have_zero_car_part():
    """Teammates share a car, so the car part is exactly zero by construction. A single race
    gives a noisy driver estimate (CI ~0.25 s wide), so we check calibration across rounds
    instead of one point: the true gap (-0.16) should fall inside most intervals, and the
    average over rounds should be close to it."""
    truth = SRC.truth["driver"]["DA1"] - SRC.truth["driver"]["DA2"]
    ests, covered = [], 0
    for r in range(1, 6):
        d = decompose(race(r), "DA1", "DA2", n_boot=100)
        assert d["same_team"] and abs(d["components"]["car"]["estimate_s"]) < 1e-9
        c = d["components"]["driver"]
        ests.append(c["estimate_s"])
        covered += c["ci95_s"][0] <= truth <= c["ci95_s"][1]
    assert covered >= 4
    assert abs(np.mean(ests) - truth) < 0.06


def test_consistency_ranks_noisy_driver_lower():
    # pool several races for stability; DV2 (sd .22) should score below DA1 (sd .11)
    scores = {}
    for r in (1, 2, 3):
        for row in consistency(race(r)):
            scores.setdefault(row["driver"], []).append(row["score"])
    avg = {k: np.mean(v) for k, v in scores.items()}
    assert avg["DA1"] > avg["DV2"]
    assert all(0 <= s <= 100 for s in avg.values())
