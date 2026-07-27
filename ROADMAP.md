# Roadmap

## Current status: r27 — playable, validated

**Validation snapshot (r27):**

| Check | Result |
|---|---|
| `py_compile` (both files) | OK |
| `--selftest` | ALL PASS — 67 assertions |
| `--batch 30` | 0 containment escapes |
| `--smoke` | 90 frames OK |
| `--snap` | md5 `62c87ddb6d1f0ee36f36a71a5000cd5f`, byte-identical to the R6.1 baseline |
| `--aigame 12 --seed 4200` | SHARK 9–3 STEADY, all games completed cleanly |
| `cushion_path.py` standalone | SELFTEST OK — 36 primitives |

The `--aigame` figure is unchanged from the pre-r27 run on the same machine,
which is the point: r27 touches sandbox and the rules layer, so the AI must be
untouched. **Record which machine an `--aigame` number came from.** The physics
is float-heavy and the result is platform-sensitive; the r25/r26 figures
recorded here previously (SHARK 4–8 and 5–7) did not reproduce elsewhere on the
same code, so treat a seeded score as a regression check against one machine
rather than an absolute. `--snap` staying byte-identical confirms nothing about
rendering moved.

`hustler.py` is ~6,130 lines; `cushion_path.py` ~515. The game is two files,
no assets, no dependencies beyond pygame and pymunk; the two measurement
scripts alongside it are tools, not part of the game.

> **Note on older revision tags.** This file previously tracked "R6.x" graphics
> increments and a GL renderer. Both are long since resolved: the tabbed panel
> and full-screen window shipped, and the GL path was removed entirely at R6.10
> after an unresolved black-screen bug on real hardware. Classic (software)
> pygame is the only renderer, and reintroducing GL would be a fresh build
> rather than a revert. See [CHANGELOG.md](CHANGELOG.md) for what actually
> happened.

---

## What the project is actually for

Worth stating plainly, because it determines what belongs on this list:
**the primary use is single player** — setting the balls up and potting them
yourself. The AI-vs-AI mode exists because it was a good way to stress-test the
physics, and it remains genuinely interesting, but it is a secondary interest.

Features that improve the experience of standing at the table should generally
outrank features that improve AI-vs-AI study.

---

## Open work

Nothing here is committed. Each item is listed with what it would involve and
what it depends on, so a session can start from an informed choice rather than
a blank page.

### Near-term candidates

**Scripted play-through tests.** All four r23 bugs escaped the entire validation
chain because that chain has no test that plays a whole frame — and so did the
r27 chamber bug, which makes five. Driving a
complete game through the rules engine and asserting turn, visit, spin and
placement state at each step would close the gap. Arguably the highest-value
item on this list, since it protects everything else.

> **AI distance calibration (r25/r26/r27) is done.** `pot_estimate()`'s distance
> floor was fitted and shipped at r25; STEADY's attempt threshold was moved
> clear of it at r26 after `floor_threshold_audit.py` showed the two sitting
> on the same side of `POT_FLOOR` was changing 27% of all AI shots, not an
> edge case. Two small residuals remain, tracked but not pursued further for
> now — see [KNOWN_ISSUES.md](KNOWN_ISSUES.md) #2 and #3. Selftest 59 (r27)
> guards the threshold-above-floor invariant if `POT_FLOOR` is ever re-derived.

### Larger features under discussion

**Visual training overlay / coach mode.** A richer aiming display inspired by
real coaching tools: multi-segment paths including cushion rebounds, a cut-angle
readout at the ghost ball, and a per-ball indication of which pocket each ball
naturally belongs to. Several open design questions remain (which geometry to
reflect against, how many bounces to trust, whether the table read should
account for cue-ball position). Note that the physics applies spin as an impulse
at contact and models no in-flight curve, so a projected path must not draw one.
The r24 jaws-placement work built the primitives this would reflect against —
`dist_point_segment` and the cached `nose_loop_m()` cushion-nose polyline — so
the "which geometry" question is already half-answered: reflect off the real
nose loop, not a rectangle.

**League mode.** Single player against a series of AI opponents across a fixture
list, with results feeding a standings table and a final ranking. Fits the
single-player focus well, and the AI personality system already provides a clean
difficulty ladder — skill (aim jitter) is an independent parameter from strategy,
so a range of opponents is just a range of values.

**The "Grannie".** A Scottish whitewash: one player clears all their colours and
the black while the opponent pots nothing. Detect it at frame end and announce
it. Small once frame tracking is trusted.

### Deferred

**Snooker.** Raised as a possible future direction given what's now known about
tangent-true pocket geometry. Not scoped.

**Table appearance.** The pockets *play* correctly — the tangent-true geometry
does its job — but the top-down flat rendering doesn't read like a real pocket
to the eye, because a real one is a three-dimensional object with a shelf,
undercut jaws and a shadow gradient into the throat. This is a rendering problem
rather than a geometry problem, and past attempts to fix it by adjusting outline
shapes made it worse. Any attempt should also respect the no-asset-files rule.

**Larger-N AI studies.** The parallel-games speedup has never been timed on real
multi-core hardware; verify it before relying on it for bigger runs.

---

## Working practice

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow. In short:
decision brief → sign-off → build → validate, with one new self-test assertion
per feature and the full chain re-run every time.
