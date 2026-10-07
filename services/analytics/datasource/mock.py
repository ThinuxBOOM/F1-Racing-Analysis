"""DEMO DATA GENERATOR. Everything here is synthetic.

Teams, drivers and circuits are fictional on purpose, so nothing can be mistaken for real
results. Output uses the exact frame schema of real sources (see base.py). The generator keeps
its hidden ground truth (true car/driver offsets) in `truth`, which lets tests check that the
analytics recover known answers. `truth` is never exposed through the API.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from .base import LAP_COLUMNS, RESULT_COLUMNS, PIT_COLUMNS, EVENT_COLUMNS

SEASON = 2099                     # obviously not a real season
FUEL_S_PER_LAP = 0.035
COMPOUND = {                      # offset vs medium (s), degradation (s per lap of age)
    "SOFT": (-0.55, 0.095), "MEDIUM": (0.0, 0.055), "HARD": (0.45, 0.030),
}
POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]

TEAMS = {                         # true car offset in s/lap relative to the reference car
    "Demo Aero Works": -0.35, "Demo Dynamics": -0.15, "Demo Motorsport": 0.0,
    "Demo Velocity": 0.20, "Demo Racing Co": 0.45,
}
DRIVERS = {                       # code: (team, true driver offset s/lap, consistency sd s)
    "DA1": ("Demo Aero Works", -0.10, 0.11), "DA2": ("Demo Aero Works", 0.06, 0.16),
    "DD1": ("Demo Dynamics", -0.04, 0.13), "DD2": ("Demo Dynamics", 0.09, 0.19),
    "DM1": ("Demo Motorsport", -0.07, 0.12), "DM2": ("Demo Motorsport", 0.05, 0.15),
    "DV1": ("Demo Velocity", 0.02, 0.14), "DV2": ("Demo Velocity", -0.02, 0.22),
    "DR1": ("Demo Racing Co", 0.00, 0.17), "DR2": ("Demo Racing Co", 0.12, 0.20),
}
CIRCUITS = [  # name, country, base lap (s), laps, length km, sector fractions
    ("Demo Ring North", "Fictionia", 88.0, 52, 5.2, (0.30, 0.38, 0.32)),
    ("Demo Park Speedway", "Fictionia", 79.5, 58, 4.6, (0.36, 0.30, 0.34)),
    ("Demo Harbour Street", "Mockland", 101.0, 48, 5.9, (0.28, 0.40, 0.32)),
    ("Demo Hills", "Mockland", 84.0, 55, 4.9, (0.33, 0.34, 0.33)),
    ("Demo Grand Loop", "Synthia", 92.5, 50, 5.4, (0.31, 0.36, 0.33)),
]


class MockSource:
    name = "mock"
    is_mock = True

    def __init__(self, seed: int = 2099):
        self.seed = seed
        self.truth = {"car": dict(TEAMS), "driver": {d: v[1] for d, v in DRIVERS.items()},
                      "consistency_sd": {d: v[2] for d, v in DRIVERS.items()}}
        self._laps, self._results, self._pits = {}, {}, []
        self._build()

    # ------------------------------------------------------------ public API
    def seasons(self): return [SEASON]

    def events(self, season):
        rows = [dict(season=SEASON, round=i + 1, name=f"Demo Grand Prix {i + 1}", circuit=c[0],
                     country=c[1], total_laps=c[3], length_km=c[4]) for i, c in enumerate(CIRCUITS)]
        return pd.DataFrame(rows, columns=EVENT_COLUMNS)

    def laps(self, season, rnd, kind):
        return self._laps.get((rnd, kind), pd.DataFrame(columns=LAP_COLUMNS)).copy()

    def results(self, season, rnd, kind):
        return self._results.get((rnd, kind), pd.DataFrame(columns=RESULT_COLUMNS)).copy()

    def pit_stops(self, season, rnd):
        df = pd.DataFrame(self._pits, columns=PIT_COLUMNS)
        return df[df["round"] == rnd].copy()

    # ------------------------------------------------------------ generation
    def _build(self):
        rng = np.random.default_rng(self.seed)
        for r, (cname, _, base, nlaps, _, frac) in enumerate(CIRCUITS, start=1):
            q_laps, q_res = self._quali(rng, r, base, frac)
            self._laps[(r, "Q")], self._results[(r, "Q")] = q_laps, q_res
            grid = q_res.set_index("driver")["finish_pos"].to_dict()
            rl, rr = self._race(rng, r, base, nlaps, frac, grid)
            self._laps[(r, "R")], self._results[(r, "R")] = rl, rr

    def _sector_split(self, code, frac, lap, rng):
        bias = np.random.default_rng(sum(map(ord, code))).normal(0, 0.05, 3)
        bias -= bias.mean()
        s1 = frac[0] * lap + bias[0] + rng.normal(0, 0.03)
        s2 = frac[1] * lap + bias[1] + rng.normal(0, 0.03)
        return s1, s2, lap - s1 - s2

    def _quali(self, rng, rnd, base, frac):
        rows, best = [], {}
        for code, (team, d_off, sd) in DRIVERS.items():
            for i in range(8):                    # out, push, in, out, push, in, out, push
                kind = ("out", "push", "in")[i % 3]
                if kind == "push":
                    evo = -0.04 * i               # track evolution
                    t = base + self.truth["car"][team] * 1.6 + d_off * 1.6 + evo + abs(rng.normal(0, sd * 1.4))
                else:
                    t = base + 14 + rng.normal(0, 1.0)
                s1, s2, s3 = self._sector_split(code, frac, t, rng)
                deleted = bool(kind == "push" and rng.random() < 0.04)
                rows.append(dict(season=SEASON, round=rnd, kind="Q", driver=code, team=team,
                                 lap_number=i + 1, lap_time_s=t, s1_s=s1, s2_s=s2, s3_s=s3,
                                 speed_st=rng.normal(312 - self.truth["car"][team] * 8, 2),
                                 compound="SOFT", tyre_age=1 if kind != "push" else 2, stint_number=i // 3 + 1,
                                 position=None, pit_in=kind == "in", pit_out=kind == "out",
                                 track_status="1", deleted=deleted))
                if kind == "push" and not deleted:
                    best[code] = min(best.get(code, 1e9), t)
        df = pd.DataFrame(rows, columns=LAP_COLUMNS)
        order = sorted(best, key=best.get)
        res = pd.DataFrame([dict(season=SEASON, round=rnd, kind="Q", driver=c, team=DRIVERS[c][0],
                                 grid_pos=None, finish_pos=i + 1, status="Finished", points=0,
                                 laps_completed=8) for i, c in enumerate(order)], columns=RESULT_COLUMNS)
        return df, res

    def _race(self, rng, rnd, base, nlaps, frac, grid):
        sc_start = int(rng.integers(14, nlaps - 20)); sc_laps = set(range(sc_start, sc_start + 3))
        rows, pits, totals, dnf = [], [], {}, {}
        victim = rng.choice(list(DRIVERS)) if rng.random() < 0.6 else None
        for code, (team, d_off, sd) in DRIVERS.items():
            n_stops = int(rng.choice([1, 2], p=[0.55, 0.45]))
            pit_laps = sorted(rng.choice(np.arange(10, nlaps - 8), n_stops, replace=False).tolist())
            if any(abs(a - b) < 8 for a, b in zip(pit_laps, pit_laps[1:])): pit_laps = [nlaps // 2]
            comps = list(rng.choice(["SOFT", "MEDIUM", "HARD"], len(pit_laps) + 1))
            stint, age, cum = 1, 1, 0.0
            last = nlaps if code != victim else int(rng.integers(nlaps // 3, nlaps - 5))
            for lap in range(1, last + 1):
                comp = comps[stint - 1]
                off, deg = COMPOUND[comp]
                t = (base + self.truth["car"][team] + d_off + off + deg * age
                     + FUEL_S_PER_LAP * (nlaps - lap) + rng.normal(0, sd))
                if rng.random() < 0.10: t += rng.uniform(0.3, 0.9)      # traffic
                status = "1"
                if lap in sc_laps: t += 26.0; status = "4"
                if lap == 1: t += 6.0
                pit_in = lap in pit_laps
                pit_out = (lap - 1) in pit_laps
                if pit_in: t += 2.0
                if pit_out: t += 19.5 + rng.normal(0, 0.6)
                if rng.random() < 0.006: lap_time = None                  # missing timing sample
                else: lap_time = t
                s1, s2, s3 = self._sector_split(code, frac, t, rng) if lap_time else (None,) * 3
                rows.append(dict(season=SEASON, round=rnd, kind="R", driver=code, team=team,
                                 lap_number=lap, lap_time_s=lap_time, s1_s=s1, s2_s=s2, s3_s=s3,
                                 speed_st=rng.normal(312 - self.truth["car"][team] * 8, 2),
                                 compound=comp, tyre_age=age, stint_number=stint, position=None,
                                 pit_in=pit_in, pit_out=pit_out, track_status=status, deleted=False))
                cum += t
                if pit_in:
                    pits.append(dict(season=SEASON, round=rnd, driver=code, lap=lap,
                                     duration_s=21.5 + rng.normal(0, 0.7), position_before=None, position_after=None))
                    stint += 1; age = 1
                else:
                    age += 1
            totals[code] = (last, cum)
            dnf[code] = code == victim
        df = pd.DataFrame(rows, columns=LAP_COLUMNS)
        # running positions from cumulative elapsed time per lap
        df["_t"] = df["lap_time_s"].fillna(df.groupby("driver")["lap_time_s"].transform("median"))
        df["_cum"] = df.groupby("driver")["_t"].cumsum()
        df["position"] = df.groupby("lap_number")["_cum"].rank(method="first").astype(int)
        df = df.drop(columns=["_t", "_cum"])
        pos = df.set_index(["driver", "lap_number"])["position"].to_dict()
        for p_ in pits:
            p_["position_before"] = pos.get((p_["driver"], p_["lap"]))
            p_["position_after"] = pos.get((p_["driver"], p_["lap"] + 1), pos.get((p_["driver"], p_["lap"])))
        order = sorted(totals, key=lambda c: (-totals[c][0], totals[c][1]))
        res = pd.DataFrame([dict(season=SEASON, round=rnd, kind="R", driver=c, team=DRIVERS[c][0],
                                 grid_pos=grid[c], finish_pos=i + 1,
                                 status="Retired (mechanical)" if dnf[c] else "Finished",
                                 points=POINTS[i] if i < len(POINTS) and not dnf[c] else 0,
                                 laps_completed=totals[c][0]) for i, c in enumerate(order)],
                           columns=RESULT_COLUMNS)
        self._pits.extend(pits)
        return df, res
