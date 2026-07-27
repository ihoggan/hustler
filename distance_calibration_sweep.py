#!/usr/bin/env python3
"""Distance calibration sweep — the AI distance-calibration measurement rig.

NUMBERING NOTE (r27): the KNOWN_ISSUES entries this refers to have been
renumbered as threads closed. The distance-calibration bug that prompted r25
is now under "Recently fixed"; the live thread about the floor's SHAPE is
KNOWN_ISSUES #2 and the extreme-cut/throw thread is #3. Read those, not the
numbers quoted in the history below.

Not a build — a measurement tool. Third pass. The first (r25) diagnosed
`pot_estimate()`'s old flat `exp(-t_cue/10)` distance decay as the wrong
culprit and the r16 lever-arm term's missing floor as the real one, fitted
`POT_FLOOR = 0.19` from a t_cue x cut-angle grid at a single, fixed d_tp
(0.3 m) on a single corner pocket, and shipped it. The second widened d_tp
(0.15-1.0 m) and found the floor isn't a genuine plateau -- measured pot rate
rises smoothly with the underlying (pre-floor) aim-error term even within the
"floored" region, from ~0.15-0.16 deep in the collapse up to ~0.22-0.28 near
the crossover -- but decided not to chase a curve fit yet, since the residual
(+-0.04 to 0.09) is far smaller than the original bug (up to 30x) and a
smooth fit would need new free parameters against a still-small sample from
one pocket.

That "one pocket" is what this version addresses. Every sweep so far has
used the same corner pocket (`capture_points()[0]`); pocket TYPE was the
third open axis -- corner pockets have jaws either side of
an 81.3 mm mouth, middle pockets have none either side of a wider 100 mm
mouth (`POCKET_MOUTH_M` vs `POCKET_MIDDLE_MOUTH_M`), so there is a real,
unmeasured question of whether the same floor applies to both.

`--pocket-type` (default: both) now selects which of `capture_points()`'s six
pockets to use as the representative for each type -- pocket 0 for corner,
pocket 4 for middle, matching `pot_drill`'s own indexing convention (corners
0-3, middles 4-5) -- and the shot geometry generalises to build off whichever
pocket's own throat axis, not a hardcoded corner diagonal. One geometric
consequence worth knowing before reading results: a middle pocket's throat
axis runs along the table's WIDTH (0.91 m total), not its length (1.82 m),
so a cut_deg of 0 caps out at a much shorter t_cue for middles than for
corners before running off the table -- same `in_table` skip-and-report as
before handles it, but expect far fewer straight-shot middle-pocket cells to
survive than corner ones at the same grid.

Output, prediction and measurement are otherwise unchanged from the d_tp
sweep: `pot_estimate()`'s current (already-floored) prediction against a
real, physically-simulated measured pot rate with a Wilson interval, a
`floored` flag, and a human-readable table plus --jsonl for one JSON row per
cell. This script only measures; it does not change `pot_estimate()`.
"""
import argparse
import json
import math
import random
import sys

import hustler as H

_S2 = math.sqrt(2.0) / 2.0
# direction INTO each pocket, indexed exactly as capture_points() returns them
# -- matches pot_drill's own convention (corners 0-3, middles 4-5).
POCKET_DIN = {
    0: (-_S2, -_S2), 1: (_S2, -_S2), 2: (-_S2, _S2), 3: (_S2, _S2),
    4: (0.0, -1.0), 5: (0.0, 1.0),
}
POCKET_TYPE_IDX = {"corner": 0, "middle": 4}   # one representative of each
DEFAULT_POCKET_TYPES = ("corner", "middle")
DEFAULT_T_CUE = (0.15, 0.3, 0.5, 0.7, 0.9, 1.1, 1.3)
DEFAULT_D_TP = (0.15, 0.3, 0.5, 0.7)
# A middle pocket's throat axis is capped by the table's 0.91 m WIDTH, not its
# 1.82 m length, so it takes a much bigger cut angle (~60-80 deg, verified by
# probe) before a shot reaches the floored regime without running off the
# table. 40/60 added so the middle-pocket rows have a real chance to floor at
# all; corners tolerate the wider range fine (fullness = cos(60) = 0.5, well
# above the 0.10 cut-too-thin rejection).
DEFAULT_CUT_DEG = (0.0, 20.0, 40.0, 60.0)
STUDY_JITTER = H.STUDY_JITTER   # the aim_jitter SHARK/STEADY actually study with


def shot_geometry(pocket_idx, t_cue, d_tp, cut_deg):
    """Cue/object positions for a pot on `capture_points()[pocket_idx]`: the
    OBJECT ball sits `d_tp` out from the pocket on its own throat axis
    (unchanged by cut_deg — a cut shot still sends the object ball straight
    into the pocket), and the CUE ball sits `t_cue` out from the object ball
    along a line `cut_deg` off that same axis. Rotating only the cue leg is
    what actually varies fullness in pot_estimate(); rotating both legs
    together leaves the cue-object and object-pocket lines parallel
    (fullness pinned at 1.0 regardless of cut_deg) and can silently walk the
    cue ball off the table — caught, for the corner case, by the --trials 20
    smoke check scoring 0/20 at cut_deg=30 for both t_cue values tried, an
    unmissable tell once looked at rather than trusted.

    The throat axis comes from `POCKET_DIN[pocket_idx]`, not a hardcoded
    corner diagonal — a corner's runs at 45 degrees between the table's two
    axes (1.82 m length, 0.91 m width); a middle's runs purely along the
    0.91 m width. cut_deg is subtracted (not added) from the throat axis so
    larger cuts rotate the cue leg toward whichever axis has more room —
    for a corner that's the length axis; for a middle, by symmetry, either
    sign works equally, so the same subtraction is used for both rather than
    special-casing it."""
    pc, cap_r = H.capture_points()[pocket_idx]
    din = POCKET_DIN[pocket_idx]
    throat_ang = math.atan2(-din[1], -din[0])   # away from pocket, into the table
    obj = (pc[0] + math.cos(throat_ang) * d_tp,
           pc[1] + math.sin(throat_ang) * d_tp)
    cue_ang = throat_ang - math.radians(cut_deg)
    cue = (obj[0] + math.cos(cue_ang) * t_cue,
           obj[1] + math.sin(cue_ang) * t_cue)
    return cue, obj, pc, cap_r


def in_table(pos, r):
    """True if a ball of radius r centred at pos fits inside the playing
    surface with a ball-radius margin -- a coarse rectangle check, adequate
    here since the sweep's grid is built to stay well clear of the pockets
    themselves (the cushion-nose geometry only matters right at the jaws)."""
    x0, y0, x1, y1 = H.play_rect()
    return (x0 + r) <= pos[0] <= (x1 - r) and (y0 + r) <= pos[1] <= (y1 - r)


def predict(cue, obj, pc, cap_r, r_cue, r_obj, jitter):
    """pot_estimate()'s current (post-r25) prediction for this shot -- already
    floored at POT_FLOOR where the aim-error term alone would have collapsed
    below it. `floored` flags exactly that case: those are the cells this
    sweep exists to check, since anywhere else is just confirming the
    already-validated short/mid-range behaviour is unchanged."""
    est = H.pot_estimate(cue, obj, pc, cap_r, r_cue, r_obj, jitter)
    if est is None:
        return None
    return {"p": est["p"], "t_cue": est["t_cue"], "d_tp": est["d_tp"],
            "floored": abs(est["p"] - H.POT_FLOOR) < 1e-9}


def measure(cue, obj, pc, cap_r, d_tp_nominal, t_cue_nominal, jitter, n, rng):
    """n headless trials of this exact shot, aimed and struck exactly as
    PoolAI does: aim at the ghost ball (not the object-ball centre — only
    equivalent to it at cut_deg=0), angle perturbed by aim_jitter, power from
    the AI's own `min(3.5, 1.0 + 1.1*d)` formula with its own 2% jitter.
    Returns wins out of n potted."""
    rc, ro = H.CFG["CUE_R_M"], H.ball_r()
    est = H.pot_estimate(cue, obj, pc, cap_r, rc, ro, jitter)
    base_ang = math.atan2(est["aim"][1], est["aim"][0])
    d = t_cue_nominal + d_tp_nominal
    base_power = min(3.5, 1.0 + 1.1 * d)
    wins = 0
    for _ in range(n):
        sim = H.Sim(layout="empty")
        sim._add_ball(sim.CUE_ID, cue, "cue")
        oid = sim._add_ball(sim.alloc_id(), obj, "red")
        ang = base_ang + rng.gauss(0.0, jitter)
        power = max(H.CFG["POWER_MIN"], base_power * (1.0 + rng.gauss(0.0, 0.02)))
        sim.strike((math.cos(ang), math.sin(ang)), power)
        sim.run_to_rest(timeout_s=25.0)
        if oid in sim.potted_log:
            wins += 1
    return wins


def run_sweep(pocket_types, t_cue_values, d_tp_values, cut_deg_values, n, seed,
              jsonl_path):
    rc, ro = H.CFG["CUE_R_M"], H.ball_r()
    rng = random.Random(seed)
    rows = []
    print(f"DISTANCE CALIBRATION SWEEP (pocket-type axis) — jitter={STUDY_JITTER} "
          f"rad, POT_FLOOR={H.POT_FLOOR}, n={n} trials/cell, seed={seed}")
    print(f"{'pocket':>7} {'t_cue':>6} {'d_tp':>5} {'cut':>5} {'p_pred':>8} "
          f"{'floored':>8} {'actual':>8} {'95% CI':>17}")
    print(f"{'':>7} {'(m)':>6} {'(m)':>5} {'(deg)':>5} {'(model)':>8} {'':>8} "
          f"{'(n=' + str(n) + ')':>8}")
    for pocket_type in pocket_types:
        pocket_idx = POCKET_TYPE_IDX[pocket_type]
        for d_tp in d_tp_values:
            for cut_deg in cut_deg_values:
                for t_cue in t_cue_values:
                    cue, obj, pc, cap_r = shot_geometry(pocket_idx, t_cue, d_tp,
                                                         cut_deg)
                    if not (in_table(cue, rc) and in_table(obj, ro)):
                        print(f"{pocket_type:>7} {t_cue:6.2f} {d_tp:5.2f} "
                              f"{cut_deg:5.0f}  -- skipped: geometry falls "
                              f"outside the table (cue={cue[0]:.2f},{cue[1]:.2f} "
                              f"obj={obj[0]:.2f},{obj[1]:.2f}) --")
                        continue
                    pred = predict(cue, obj, pc, cap_r, rc, ro, STUDY_JITTER)
                    if pred is None:
                        continue    # degenerate geometry (shouldn't happen here)
                    wins = measure(cue, obj, pc, cap_r, d_tp, t_cue, STUDY_JITTER,
                                    n, rng)
                    actual = wins / n
                    lo, hi = H.wilson_interval(wins, n)
                    print(f"{pocket_type:>7} {t_cue:6.2f} {d_tp:5.2f} "
                          f"{cut_deg:5.0f} {pred['p']:8.3f} "
                          f"{'yes' if pred['floored'] else 'no':>8} {actual:8.3f} "
                          f"[{lo:6.3f},{hi:6.3f}]")
                    rows.append({"pocket_type": pocket_type,
                                 "t_cue": round(t_cue, 4), "d_tp": round(d_tp, 4),
                                 "cut_deg": cut_deg, "jitter": STUDY_JITTER,
                                 "n": n, "wins": wins,
                                 "p_actual": round(actual, 4),
                                 "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
                                 "p_pred": round(pred["p"], 4),
                                 "floored": pred["floored"]})
    if jsonl_path:
        with open(jsonl_path, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        print(f"\nwrote {len(rows)} rows -> {jsonl_path}")
    floored_rows = [r for r in rows if r["floored"]]
    if floored_rows:
        vals = [r["p_actual"] for r in floored_rows]
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        print(f"\nfloored cells: {len(floored_rows)}, measured pot rate "
              f"mean={mean:.3f} sd={variance ** 0.5:.3f} "
              f"(POT_FLOOR={H.POT_FLOOR})")
        by_type = {}
        for r in floored_rows:
            by_type.setdefault(r["pocket_type"], []).append(r["p_actual"])
        print("  by pocket type:", ", ".join(
            f"{pt}: mean={sum(v)/len(v):.3f} (n_cells={len(v)})"
            for pt, v in sorted(by_type.items())))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trials", type=int, default=300,
                     help="Monte Carlo trials per grid cell (default 300)")
    ap.add_argument("--seed", type=int, default=1000, help="RNG seed")
    ap.add_argument("--jsonl", metavar="FILE",
                     help="write one JSON row per cell here, for curve-fitting")
    ap.add_argument("--pocket-type", metavar="TYPE", nargs="+",
                     choices=list(POCKET_TYPE_IDX), default=list(DEFAULT_POCKET_TYPES),
                     help="pocket types to sweep: corner, middle, or both (default)")
    ap.add_argument("--t-cue", metavar="M", type=float, nargs="+",
                     default=list(DEFAULT_T_CUE),
                     help="t_cue grid values in metres")
    ap.add_argument("--d-tp", metavar="M", type=float, nargs="+",
                     default=list(DEFAULT_D_TP),
                     help="d_tp (object-to-pocket distance) grid values in metres")
    ap.add_argument("--cut-deg", metavar="DEG", type=float, nargs="+",
                     default=list(DEFAULT_CUT_DEG),
                     help="cut-angle grid values in degrees")
    args = ap.parse_args()
    run_sweep(args.pocket_type, args.t_cue, args.d_tp, args.cut_deg, args.trials,
              args.seed, args.jsonl)
    sys.exit(0)
