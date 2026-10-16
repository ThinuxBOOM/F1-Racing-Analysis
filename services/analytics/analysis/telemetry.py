"""Telemetry synthesis, corner detection and corner deltas. MODEL ESTIMATE.

Real telemetry comes from FastF1 (2018+) and is stored in the `telemetry`
table at 5 m steps (see services/ingest/ingest.py ingest_telemetry). The mock
source synthesises deterministic distance-aligned traces on demand so the
frontend and tests work without a database.

Synthesis is clearly labelled: speed traces use fictional corner layouts per
circuit, with car offsets raising straight-line speed and driver offsets
raising apex speed. Noise scales with the driver's hidden consistency sd.

Corner detection is generic (works on real or synthetic traces):
  1. smooth speed (moving average, window 3)
  2. local minima below (median - 15 km/h), separated by >= 200 m
  3. braking start: walk back until longitudinal decel < 8 km/h per 25 m
     or throttle returns to 100
  4. exit: walk forward until speed recovers to 95% of the surrounding
     straight max or throttle is 100 for 3 consecutive samples

Deltas compare two laps on a common distance grid. Distances are aligned by
the start/finish line; sub-sample alignment error (~25 m grid) is disclosed
in the methodology entry.
"""
from __future__ import annotations
import hashlib
import numpy as np
import pandas as pd

STEP_M = 25          # API grid (storage uses 5 m; see ingest)
MIN_CORNER_SEP_M = 200
APEX_DROP_KMH = 15


def _seed(*parts) -> int:
    h = hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:8], 16)


def circuit_layout(circuit: str, length_m: float, n_corners: int | None = None):
    """Deterministic fictional corner layout for a circuit.

    Returns list of (distance_m, apex_kmh, length_m) sorted by distance.
    Apex speeds 85-165 km/h; corner length 150-400 m.
    """
    rng = np.random.default_rng(_seed("layout", circuit))
    n = n_corners or int(rng.integers(8, 13))
    # keep corners away from start/finish (first/last 300 m are straight)
    locs = np.sort(rng.uniform(300, max(length_m - 300, 600), n))
    # enforce separation
    fixed = []
    for d in locs:
        if all(abs(d - x) > MIN_CORNER_SEP_M for x in fixed):
            fixed.append(float(d))
    out = []
    for d in fixed:
        apex = float(rng.uniform(85, 165))
        clen = float(rng.uniform(150, 400))
        out.append((d, apex, clen))
    return sorted(out)


def synthesize_telemetry(circuit: str, length_km: float, driver: str,
                         lap_number: int, season: int = 2099, rnd: int = 1,
                         car_bonus_kmh: float = 0.0, driver_apex_bonus_kmh: float = 0.0,
                         noise_sd_kmh: float = 1.2, step_m: int = STEP_M) -> pd.DataFrame:
    """Deterministic synthetic telemetry for one lap.

    car_bonus raises straight speed; driver bonus raises apex speed (better
    drivers carry more apex speed). Returns columns: distance_m, speed,
    throttle, brake, gear, drs, x, y.
    """
    length_m = float(length_km) * 1000.0
    dist = np.arange(0, length_m, step_m)
    n = len(dist)
    rng = np.random.default_rng(_seed("tele", season, rnd, driver, lap_number))
    corners = circuit_layout(circuit, length_m)

    top_speed = 312 + car_bonus_kmh + rng.normal(0, 1.0)
    speed = np.full(n, top_speed)

    # shape corners as Gaussian dips
    for d_c, apex, clen in corners:
        sigma = clen / 2.4
        dip = (top_speed - (apex + driver_apex_bonus_kmh))
        speed -= dip * np.exp(-0.5 * ((dist - d_c) / sigma) ** 2)

    speed += rng.normal(0, noise_sd_kmh, n)
    speed = np.clip(speed, 70, 355)

    # throttle/brake from longitudinal gradient
    grad = np.gradient(speed)  # kmh per step
    brake = grad < -1.2
    throttle = np.where(brake, 0, 100).astype(float)
    # partial throttle just after apex (traction)
    for d_c, apex, clen in corners:
        mask = (dist > d_c) & (dist < d_c + clen * 0.6)
        throttle[mask] = 65
    gear = np.clip((speed / 42).astype(int), 1, 8)
    # DRS on the two longest straights (gaps between corners)
    drs = np.zeros(n, dtype=int)
    bounds = [0] + [d for d, _, _ in corners] + [length_m]
    gaps = sorted(((bounds[i + 1] - bounds[i], i) for i in range(len(bounds) - 1)), reverse=True)[:2]
    for _, gi in gaps:
        m = (dist >= bounds[gi] + 60) & (dist < bounds[gi + 1] - 60)
        # only where fast
        m &= speed > top_speed - 12
        drs[m] = 1

    # track shape: deformed circle so each circuit looks different
    r0 = length_m / (2 * np.pi)
    phase = (_seed("phase", circuit) % 360) / 360 * 2 * np.pi
    stretch = 0.75 + (_seed("stretch", circuit) % 50) / 100  # 0.75-1.24
    theta = 2 * np.pi * dist / length_m + phase
    # add corner wiggles so the map is not a plain oval
    wiggle = np.zeros(n)
    for d_c, _, clen in corners:
        wiggle += 0.18 * r0 * np.exp(-0.5 * ((dist - d_c) / (clen)) ** 2) * np.sin(theta * 3)
    x = (r0 * np.cos(theta)) * stretch + wiggle * 0.3
    y = r0 * np.sin(theta) + wiggle
    return pd.DataFrame(dict(distance_m=dist.astype(float), speed=np.round(speed, 1),
                             throttle=throttle, brake=brake, gear=gear, drs=drs,
                             x=np.round(x, 1), y=np.round(y, 1)))


def detect_corners(tele: pd.DataFrame) -> list[dict]:
    """Generic corner detector from a speed trace. Returns list of dicts with
    corner number, entry/apex/exit distances and speeds, and time loss vs
    straight-line reference."""
    if tele.empty or len(tele) < 10:
        return []
    df = tele.sort_values("distance_m").reset_index(drop=True)
    s = df["speed"].to_numpy(float)
    d = df["distance_m"].to_numpy(float)
    step = float(np.median(np.diff(d))) if len(d) > 1 else STEP_M
    # smooth
    ker = np.ones(3) / 3
    sm = np.convolve(s, ker, mode="same")
    med = float(np.median(sm))
    # local minima below threshold
    cands = []
    for i in range(2, len(sm) - 2):
        if sm[i] < med - APEX_DROP_KMH and sm[i] <= sm[i - 1] and sm[i] <= sm[i + 1] \
                and sm[i] < sm[i - 2] and sm[i] < sm[i + 2]:
            cands.append(i)
    # enforce separation: keep deepest within each window
    corners = []
    for i in cands:
        if corners and d[i] - corners[-1][0] < MIN_CORNER_SEP_M:
            # keep the slower apex
            if sm[i] < sm[corners[-1][1]]:
                corners[-1] = (d[i], i)
            continue
        corners.append((d[i], i))
    out = []
    thr = df["throttle"].to_numpy(float) if "throttle" in df else np.full(len(df), 100.0)
    for num, (d_apex, i_apex) in enumerate(corners, start=1):
        # braking start: walk back while decelerating hard or braking
        i_entry = i_apex
        while i_entry > 0:
            decel = sm[i_entry] - sm[i_entry - 1]
            if decel > -0.4 and thr[i_entry] >= 100:
                break
            i_entry -= 1
            if d_apex - d[i_entry] > 600:
                break
        # exit: walk forward until near straight speed
        # straight reference = max of 400 m window after apex
        ahead = sm[i_apex:min(len(sm), i_apex + int(400 / step))]
        ref = float(ahead.max()) if len(ahead) else med
        i_exit = i_apex
        while i_exit < len(sm) - 1:
            if sm[i_exit] >= 0.95 * ref and thr[min(i_exit + 1, len(thr) - 1)] >= 100:
                # require 3 consecutive full-throttle
                if all(thr[min(i_exit + k, len(thr) - 1)] >= 100 for k in range(3)):
                    break
            i_exit += 1
            if d[i_exit] - d_apex > 600:
                break
        v_entry, v_apex, v_exit = float(s[i_entry]), float(s[i_apex]), float(s[i_exit])
        # time through corner vs at reference speed
        seg = np.arange(i_entry, i_exit + 1)
        # time = sum(step / v) with v in m/s
        v_ms = np.clip(s[seg] * 1000 / 3600, 1, None)
        t_actual = float(np.sum(step / v_ms))
        v_ref_ms = max(ref * 1000 / 3600, 1)
        t_ref = float((d[i_exit] - d[i_entry]) / v_ref_ms) if d[i_exit] > d[i_entry] else 0.0
        out.append(dict(
            corner=num,
            entry_m=round(float(d[i_entry]), 1), apex_m=round(float(d_apex), 1),
            exit_m=round(float(d[i_exit]), 1),
            entry_kmh=round(v_entry, 1), apex_kmh=round(v_apex, 1), exit_kmh=round(v_exit, 1),
            length_m=round(float(d[i_exit] - d[i_entry]), 1),
            time_loss_s=round(t_actual - t_ref, 3),
        ))
    return out


def align_traces(a: pd.DataFrame, b: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Interpolate two traces onto a common distance grid. Returns
    (grid, speed_a, speed_b)."""
    lo = max(float(a["distance_m"].min()), float(b["distance_m"].min()))
    hi = min(float(a["distance_m"].max()), float(b["distance_m"].max()))
    grid = np.arange(lo, hi, STEP_M)
    sa = np.interp(grid, a["distance_m"].to_numpy(float), a["speed"].to_numpy(float))
    sb = np.interp(grid, b["distance_m"].to_numpy(float), b["speed"].to_numpy(float))
    return grid, sa, sb


def corner_deltas(tele_a: pd.DataFrame, tele_b: pd.DataFrame,
                  label_a: str = "A", label_b: str = "B") -> dict:
    """Per-corner entry/apex/exit speed deltas (B - A) and corner time deltas.

    Positive speed delta = B faster. Positive time delta = B slower through
    the corner. Uses detector on trace A for corner windows, then reads both
    traces at those windows so corners line up even if the detector jitters.
    """
    corners = detect_corners(tele_a)
    if not corners:
        # fall back to detector on B
        corners = detect_corners(tele_b)
    grid, sa, sb = align_traces(tele_a, tele_b)
    rows = []
    for c in corners:
        def at(dist_m, arr):
            idx = int(np.clip(np.searchsorted(grid, dist_m), 0, len(grid) - 1))
            return float(arr[idx])
        ea, aa, xa = at(c["entry_m"], sa), at(c["apex_m"], sa), at(c["exit_m"], sa)
        eb, ab, xb = at(c["entry_m"], sb), at(c["apex_m"], sb), at(c["exit_m"], sb)
        # corner time on grid segment
        m = (grid >= c["entry_m"]) & (grid <= c["exit_m"])
        seg = grid[m]
        ta = float(np.sum(STEP_M / np.clip(sa[m] * 1000 / 3600, 1, None))) if m.sum() else 0.0
        tb = float(np.sum(STEP_M / np.clip(sb[m] * 1000 / 3600, 1, None))) if m.sum() else 0.0
        rows.append(dict(
            corner=c["corner"], entry_m=c["entry_m"], apex_m=c["apex_m"], exit_m=c["exit_m"],
            entry_delta_kmh=round(eb - ea, 1), apex_delta_kmh=round(ab - aa, 1),
            exit_delta_kmh=round(xb - xa, 1),
            time_delta_s=round(tb - ta, 3),
            a_entry_kmh=round(ea, 1), b_entry_kmh=round(eb, 1),
            a_apex_kmh=round(aa, 1), b_apex_kmh=round(ab, 1),
        ))
    # overall: mean speed diff + predicted lap-time diff from integration
    ta_full = float(np.sum(STEP_M / np.clip(sa * 1000 / 3600, 1, None)))
    tb_full = float(np.sum(STEP_M / np.clip(sb * 1000 / 3600, 1, None)))
    return dict(corners=rows, n_corners=len(rows),
                mean_speed_delta_kmh=round(float(np.mean(sb - sa)), 2) if len(grid) else 0.0,
                predicted_lap_delta_s=round(tb_full - ta_full, 3),
                labels=dict(a=label_a, b=label_b),
                alignment_note=f"Aligned on {STEP_M} m grid; sub-sample alignment error ~±{STEP_M/2:.0f} m.")
