import os, sys
os.environ["DATA_SOURCE"] = "mock"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient
import api
from datasource.mock import MockSource, CIRCUITS
from analysis.pipeline import prepare
from analysis.predictions import predict_round

c = TestClient(api.app)
SRC = MockSource()


def _frames():
    return {r: prepare(SRC.laps(2099, r, "R"), CIRCUITS[r - 1][3]) for r in range(1, 6)}


def test_predictions_rank_and_backtest():
    out = predict_round(_frames(), 1, n_boot=40)
    assert out["trained_on"] == [2, 3, 4, 5]
    assert len(out["predictions"]) == 10
    assert "backtest_mae_s" in out
    # MAE should be modest on synthetic data (< 0.3 s)
    assert out["backtest_mae_s"] < 0.3
    # predicted order should roughly follow truth (allow 3 swaps from held-out noise)
    from datasource.mock import TEAMS, DRIVERS
    truth = {d: TEAMS[t] + off for d, (t, off, _) in DRIVERS.items()}
    pred_order = sorted(out["predictions"], key=lambda d: out["predictions"][d]["gap_to_pred_best_s"])
    truth_order = sorted(truth, key=lambda d: truth[d])
    assert sum(a != b for a, b in zip(pred_order, truth_order)) <= 6
    # every prediction carries an interval
    for d, p in out["predictions"].items():
        assert p["ci95_s"][0] <= p["gap_to_pred_best_s"] <= p["ci95_s"][1]


def test_predictions_endpoint_and_meta():
    r = c.get("/predictions/2099/1")
    assert r.status_code == 200
    j = r.json()
    assert j["meta"]["is_mock"] is True
    assert j["result"]["target_round"] == 1
    assert "MODEL ESTIMATE" in j["result"]["label"]
    # future round (no observed laps) still predicts, with a no-backtest note
    f = c.get("/predictions/2099/9").json()
    assert "no observed laps" in f["result"].get("backtest_note", "").lower() or "backtest_mae_s" not in f["result"]
