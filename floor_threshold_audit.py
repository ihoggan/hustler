#!/usr/bin/env python3
"""Floor/threshold audit — does POT_FLOOR sitting above both AI
personalities' attempt threshold actually change real play?

This is the tool that measured the r26 bug. That thread is now closed and
lives under "Recently fixed" in KNOWN_ISSUES (it was #2 while open — the
numbering has since moved on, so don't chase the old number). Selftest 59
guards the invariant it established; re-run this if POT_FLOOR is ever
re-derived.

Not a build — a measurement tool, and a different KIND of measurement from
`distance_calibration_sweep.py`. That script tests `pot_estimate()` against
synthetic geometry in isolation; #2 is a question about REAL PLAY -- how
often the AI's shot search actually lands in the floored regime, and whether
being floored is what causes it to attempt a pot rather than play a safety.
Answering that needs real games, not another synthetic grid.

Method: monkey-patches `PoolAI.choose` to observe every real decision across
N headless AI-vs-AI games (`play_ai_game`, same engine `--aigame` uses).
Whenever the AI's chosen shot is a pot sitting exactly on POT_FLOOR, it
re-runs `_search(sim, legal_colours, cp, execute=False)` -- side-effect-free,
confirmed by reading `_search`: with execute=False it returns before
`_choose_spin`/`_execute`, so it touches neither `self.rng` nor the board --
with `POT_FLOOR` temporarily patched to 0.0, to see what the AI would have
chosen WITHOUT the floor's rescue. That's the counterfactual the question asks for:
would this specific shot have been a safety instead?

This still isn't the full picture: it answers "does the floor change THIS
decision", not "is 0.19 the right number for either personality's risk
tolerance" -- that second question is a design judgement, not something a
game log can settle by itself."""
import argparse
import sys
from collections import defaultdict

import hustler as H

_real_choose = H.PoolAI.choose
_EPS = 1e-9


def _new_stats():
    return {"total_shots": 0, "pots": 0, "safeties": 0, "floored_pots": 0,
            "would_be_safety": 0, "would_be_other_pot": 0, "would_be_none": 0}


def audit_games(n, seed0, max_shots, verbose):
    games = 0
    by_name = defaultdict(_new_stats)
    examples = []

    def patched_choose(self, sim, legal_colours):
        shot = _real_choose(self, sim, legal_colours)
        if shot is None:
            return shot
        stats = by_name[self.name]
        stats["total_shots"] += 1
        if shot["type"] == "safety":
            stats["safeties"] += 1
        elif shot["type"] == "pot":
            stats["pots"] += 1
            if abs(shot["p"] - H.POT_FLOOR) < _EPS:
                stats["floored_pots"] += 1
                cue = sim.cue()
                cp = (cue.position.x, cue.position.y)
                saved_floor = H.POT_FLOOR
                H.POT_FLOOR = 0.0
                try:
                    counterfactual = self._search(sim, legal_colours, cp,
                                                   execute=False)
                finally:
                    H.POT_FLOOR = saved_floor
                if counterfactual is None:
                    stats["would_be_none"] += 1
                    verdict = "no legal target at all"
                elif counterfactual["type"] == "safety":
                    stats["would_be_safety"] += 1
                    verdict = "SAFETY (floor changed this decision)"
                else:
                    stats["would_be_other_pot"] += 1
                    verdict = (f"still a pot (p_aim={counterfactual['p']:.3f} "
                               f"already cleared threshold {self.threshold})")
                if len(examples) < 12:
                    examples.append((self.name, shot["target"], shot["pocket"],
                                      verdict))
        return shot

    H.PoolAI.choose = patched_choose
    try:
        for i in range(n):
            H.play_ai_game(seed=seed0 + i, max_shots=max_shots)
            games += 1
    finally:
        H.PoolAI.choose = _real_choose

    print(f"FLOOR/THRESHOLD AUDIT — {games} real AI-vs-AI games "
          f"(seed {seed0}..{seed0 + n - 1}), POT_FLOOR={H.POT_FLOOR}")
    ais = default_ais_thresholds()
    for name, stats in sorted(by_name.items()):
        thr = ais.get(name, "?")
        print(f"\n  {name} (threshold={thr}):")
        print(f"    total shot decisions : {stats['total_shots']}")
        print(f"    pots chosen          : {stats['pots']} "
              f"({100 * stats['pots'] / max(1, stats['total_shots']):.1f}%)")
        print(f"    safeties chosen      : {stats['safeties']} "
              f"({100 * stats['safeties'] / max(1, stats['total_shots']):.1f}%)")
        print(f"    of those pots, sitting exactly on POT_FLOOR: "
              f"{stats['floored_pots']} "
              f"({100 * stats['floored_pots'] / max(1, stats['pots']):.1f}% of "
              f"pots, {100 * stats['floored_pots'] / max(1, stats['total_shots']):.1f}%"
              f" of all shots)")
        if stats["floored_pots"]:
            fp = stats["floored_pots"]
            print(f"    counterfactual (POT_FLOOR=0) for those {fp} floored pots:")
            print(f"      would have been a SAFETY instead : "
                  f"{stats['would_be_safety']} "
                  f"({100 * stats['would_be_safety'] / fp:.1f}%)")
            print(f"      would still have been SOME pot   : "
                  f"{stats['would_be_other_pot']} "
                  f"({100 * stats['would_be_other_pot'] / fp:.1f}%)")
            print(f"      no legal target existed at all   : "
                  f"{stats['would_be_none']}")
    if verbose and examples:
        print("\n  sample floored decisions:")
        for name, target, pocket, verdict in examples:
            print(f"    {name}: target={target} pocket={pocket} -> {verdict}")
    return by_name


def default_ais_thresholds():
    return {a.name: a.threshold for a in H.default_ais()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=50, help="number of games (default 50)")
    ap.add_argument("--seed", type=int, default=1000, help="starting seed")
    ap.add_argument("--max-shots", type=int, default=300)
    ap.add_argument("-v", "--verbose", action="store_true",
                     help="print sample floored decisions")
    args = ap.parse_args()
    audit_games(args.n, args.seed, args.max_shots, args.verbose)
    sys.exit(0)
