import os, sys
os.environ["DATA_SOURCE"] = "mock"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient
import api

c = TestClient(api.app)
RACE = "/{}/2099/1/R"


def test_meta_labels_demo():
    j = c.get("/meta").json()
    assert j["is_mock"] is True and "DEMO" in j["notice"]


def test_every_payload_carries_meta():
    for path in ["/seasons", "/events/2099", "/summary/2099/1/R", "/stints/2099/1/R",
                 "/consistency/2099/1/R", "/quality/2099/1/R", "/pit-stops/2099/1", "/methodology"]:
        r = c.get(path); assert r.status_code == 200, path
        assert r.json()["meta"]["is_mock"] is True, path


def test_summary_shape():
    rows = c.get("/summary/2099/1/R").json()["rows"]
    assert len(rows) == 10
    r0 = rows[0]
    assert r0["finish_pos"] == 1 and r0["teammate"]["verdict"]
    assert set(r0["best_sectors"]) == {"s1", "s2", "s3"}


def test_quali_summary_and_pace():
    assert c.get("/summary/2099/1/Q").status_code == 200
    j = c.get("/pace/2099/1/R").json()
    assert len(j["laps"]) > 400 and len(j["field_median"]) > 30


def test_decomposition_endpoint_and_errors():
    j = c.get("/driver-vs-car/2099/1/DA1/DR2").json()
    assert "MODEL ESTIMATE" in j["result"]["label"]
    assert c.get("/driver-vs-car/2099/1/XXX/DR2").status_code == 404
    assert c.get("/pace/2099/9/R").status_code == 404


def test_adjusted_pace_gap_tracks_truth():
    """Dashboard pace gaps are tyre-mix adjusted; they should follow the hidden true pace
    (car + driver offset) far better than raw medians do, across several rounds."""
    import numpy as np
    from datasource.mock import MockSource, DRIVERS
    truth = {d: MockSource().truth["car"][t] + off for d, (t, off, _) in DRIVERS.items()}
    corrs = []
    for rnd in (1, 2, 3):
        rows = c.get(f"/summary/2099/{rnd}/R").json()["rows"]
        g = {r["driver"]: r["gap_to_field_best_pace_s"] for r in rows}
        ds = list(g)
        corrs.append(np.corrcoef([g[d] for d in ds], [truth[d] for d in ds])[0, 1])
    assert np.mean(corrs) > 0.95, corrs


def test_consistency_endpoint_warns_about_noise():
    j = c.get("/consistency/2099/1/R").json()
    assert "noise" in j["reliability_note"] and len(j["scores"]) >= 8
