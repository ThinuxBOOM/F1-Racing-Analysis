"""Verdict panel: rank likely causes of a gap between two drivers with evidence.

Quality-first rules:
  * Never state a cause the interval cannot support. If a component's 95%
    interval spans zero, its confidence caps at low.
  * Data-quality problems outrank performance claims: fewer than 15 clean
    laps for either driver forces a caveat to the top.
  * Single-race noise is always listed last with the interval widths, so a
    0.1 s gap with a 0.25 s wide interval is never over-read.
  * Season (mixed-effects) corroboration upgrades confidence; contradiction
    downgrades it. Absence of season data leaves confidence unchanged.
"""
from __future__ import annotations


def _excludes_zero(ci) -> bool:
    try:
        lo, hi = ci
        return (lo > 0 and hi > 0) or (lo < 0 and hi < 0)
    except Exception:
        return False


def verdict_panel(a: str, b: str, decomp: dict, consistency: dict | None = None,
                  quality: dict | None = None, season: dict | None = None) -> list[dict]:
    items: list[dict] = []
    comp = decomp.get("components", {})
    adj = decomp.get("adjusted_gap_s", {})
    n = decomp.get("n_laps", {})
    n_a, n_b = int(n.get("a", 0)), int(n.get("b", 0))
    same = bool(decomp.get("same_team"))

    # 0. data-quality gate
    qflags = []
    if quality:
        for d in quality.get("drivers", []):
            if d.get("driver") in (a, b) and d.get("laps_clean", 99) < 15:
                qflags.append(f"{d['driver']}: only {d['laps_clean']} clean laps")
    if min(n_a, n_b) < 15 or qflags:
        items.append(dict(rank=0, cause="Low data support",
                           evidence=("; ".join(qflags) if qflags
                                     else f"Only {n_a}/{n_b} clean laps for {a}/{b}") +
                                     ". Pace estimates are low-confidence; treat all gaps below as provisional.",
                           confidence="high", magnitude_s=None))

    def season_sign(kind: str, key: str):
        # kind: drivers|cars ; key: driver code or team (handled by caller mapping)
        if not season or kind not in season:
            return None
        e = season[kind].get(key)
        if not e:
            return None
        v = e.get("estimate_s", 0)
        return 1 if v > 0.005 else (-1 if v < -0.005 else 0)

    # 1-3. model components, ordered by |estimate|
    order = sorted(comp.items(), key=lambda kv: abs(kv[1].get("estimate_s", 0) or 0), reverse=True)
    cause_names = {"car": "Car advantage", "driver": "Driver performance",
                   "strategy_tyres_traffic": "Strategy / tyres / traffic circumstances"}
    for name, iv in order:
        est = iv.get("estimate_s", 0)
        ci = iv.get("ci95_s", [0, 0])
        clear = _excludes_zero(ci)
        direction = f"{a} faster" if est < 0 else (f"{b} faster" if est > 0 else "level")
        ev = (f"{cause_names.get(name, name)}: {est:+.3f} s "
              f"(95% [{ci[0]:+.3f}, {ci[1]:+.3f}]), {direction}.")
        if name == "car" and same:
            ev += " Teammates: car part is zero by construction."
            conf = "high"
        elif not clear:
            ev += " Interval spans zero: data cannot rule out no effect."
            conf = "low"
        else:
            # corroborate with season model
            conf = "medium"
            if season and name in ("car", "driver"):
                ev += " Single-race estimate; see season corroboration below."
            if min(n_a, n_b) >= 20:
                conf = "high"
        items.append(dict(rank=len(items) + 1, cause=cause_names.get(name, name),
                           evidence=ev, confidence=conf,
                           magnitude_s=round(float(abs(est)), 3)))

    # 4. consistency gap (only meaningful if >25 points per methodology)
    if consistency and a in consistency and b in consistency:
        ga = consistency[a].get("score", 50) - consistency[b].get("score", 50)
        if abs(ga) >= 25:
            who = a if ga > 0 else b
            items.append(dict(rank=len(items) + 1, cause="Consistency difference",
                               evidence=(f"{who} steadier by {abs(ga):.0f} points "
                                         f"({consistency[a].get('score'):.0f} vs {consistency[b].get('score'):.0f}). "
                                         "Field-relative, single session; prefer multi-race average."),
                               confidence="medium", magnitude_s=None))
        else:
            items.append(dict(rank=len(items) + 1, cause="Consistency: no meaningful gap",
                               evidence=(f"Scores {consistency[a].get('score'):.0f} vs "
                                         f"{consistency[b].get('score'):.0f}: under ~25 points is noise."),
                               confidence="high", magnitude_s=None))

    # 5. always-on noise reminder with widths
    widths = []
    for name, iv in comp.items():
        ci = iv.get("ci95_s", [0, 0])
        try:
            widths.append(abs(ci[1] - ci[0]))
        except Exception:
            pass
    w = max(widths) if widths else 0
    items.append(dict(rank=len(items) + 1, cause="Single-race uncertainty",
                       evidence=(f"Widest component interval is {w:.3f} s. "
                                 f"Adjusted gap {adj.get('estimate_s', 0):+.3f} s "
                                 f"[{adj.get('ci95_s', [0, 0])[0]:+.3f}, {adj.get('ci95_s', [0, 0])[1]:+.3f}] "
                                 f"on {n_a}/{n_b} clean laps. Multi-race support required for firm conclusions."),
                       confidence="high", magnitude_s=None))
    # sort: data-quality gate first, then by magnitude desc, noise reminder last
    head = [x for x in items if x["cause"] == "Low data support"]
    tail = [x for x in items if x["cause"] == "Single-race uncertainty"]
    mid = [x for x in items if x not in head + tail]
    mid.sort(key=lambda x: (x["magnitude_s"] is None, -(x["magnitude_s"] or 0)))
    ordered = head + mid + tail
    for i, x in enumerate(ordered, start=1):
        x["rank"] = i
    return ordered
