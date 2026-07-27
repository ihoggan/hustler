# Roadmap

## Current status: r29 — playable, validated

**Validation snapshot (r29, measured on nix5 and reproduced in a Linux
container):**

| Check | Result |
|---|---|
| `py_compile` (both files) | OK |
| `--selftest` | ALL PASS — 69 assertions |
| `--batch 30` | 0 containment escapes |
| `--smoke` | 90 frames OK |
| `--snap` | md5 `62c87ddb6d1f0ee36f36a71a5000cd5f`, byte-identical to the R6.1 baseline |
| `--aigame 12 --seed 4200` | SHARK 9–3 STEADY (nix5), all games completed cleanly |
| `cushion_path.py` standalone | SELFTEST OK — 36 primitives |

The `--aigame` figure is unchanged from the pre-r28 run, which is the point:
r28 adds a test and touches no game code, so the AI must be untouched.
**Record which machine an `--aigame` number came from.** A seeded score is a
regression check against one build on one machine, not an absolute — it says
"nothing moved since last time here", and nothing more.

The r25/r26 figures recorded here previously (SHARK 4–8 and 5–7) do not
reproduce on the current code and remain **unexplained**. That was once written
up as platform sensitivity in the floating-point physics; that explanation has
since been tested and does not hold — nix5 and an x86-64 Linux container return
identical results, game for game, on identical bytes. A documentation artefact
(a figure recorded from a build that was not quite what shipped) is the more
likely story, but it is a guess and is labelled as one. Note that both machines
share an architecture and a libc, so genuine cross-platform determinism is
untested, and CI does not run `--aigame`. `--snap` staying byte-identical
confirms nothing about rendering moved.

`hustler.py` is ~6,360 lines; `cushion_path.py` ~515. The game is two files,
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

**Scripted play-through tests — first increment SHIPPED at r28.** All four r23
bugs escaped the entire validation chain because that chain had no test that
played a whole frame, and so did the r27 chamber bug, which makes five.
Selftest 60 now drives an eight-shot frame through the rules engine and asserts
eleven named invariants covering turn, visit, spin and placement state after
every shot. Shot outcomes are synthesised against a real `Sim` rather than
played out in physics, which keeps it deterministic and fast; the stated cost
is that it tests the rules against the events the engine is *believed* to emit
and cannot catch the physics emitting something else.

The natural follow-on is a **random-walk fuzzer** over generated frames
asserting those same invariants never break. The invariants are now written
down and mutation-proven, so the fuzzer has something trustworthy to assert
against — it is the most likely route to a sixth bug.

> **AI distance calibration (r25/r26/r27) is done.** `pot_estimate()`'s distance
> floor was fitted and shipped at r25; STEADY's attempt threshold was moved
> clear of it at r26 after `floor_threshold_audit.py` showed the two sitting
> on the same side of `POT_FLOOR` was changing 27% of all AI shots, not an
> edge case. Two small residuals remain, tracked but not pursued further for
> now — see [KNOWN_ISSUES.md](KNOWN_ISSUES.md) #2 and #3. Selftest 59 (r27)
> guards the threshold-above-floor invariant if `POT_FLOOR` is ever re-derived.

### Larger features under discussion

**Visual training overlay / coach mode.** Scoped, not built. This is the next
substantial feature, and it is aimed squarely at how the game is actually used
— single player, setting the balls up and potting them. What exists today is
the r14 aim overlay (toggle `G`, or the button on the Game tab): one shot, one
contact, no cushions. It draws a tapered cue-to-ghost line tinted by pot
chance, a translucent shaded ghost ball, the object-ball line to the pocket, a
target-pocket glow that lights only when the pot is on, the tangent departure
line, and a spin-aware predicted cue rest. Coach mode is a **second tier on
that existing toggle**, not a parallel system, and its control belongs beside
the existing one on the Game tab.

*Wanted, in four parts:*

1. **Multi-segment paths** — object-ball trajectory and cue-ball cushion
   rebounds, colour-coded so cue path, impact point, target line and subsequent
   bounces are distinguishable.
2. **Ghost ball with a cut-angle readout in degrees**, updating live with aim,
   and split trajectory vectors drawn on the cloth.
3. **Cushion-first aiming** — mirroring the target through the cushion to find
   the aim point on the rail, as taught for pots that cannot be played
   directly. This is a *different mode* from rebound-after-contact, though it
   reuses the same reflection helper.
4. **A table read** — a per-ball indication of which pocket each ball naturally
   belongs to, across the whole table rather than only the ball being aimed at.

*What is already settled:*

- **Reflect off the real cushion, not a rectangle.** `estimate_leave()`
  currently reflects off a rectangle via `reflect_off_rect` and stops after one
  bounce. A rectangle would be wrong precisely at the pockets, where the 22 mm
  knuckle arcs and C1 jaws are the entire story. The r24 jaws-placement work
  already built what this needs: the cached `nose_loop_m()` cushion-nose
  polyline and `dist_point_segment`.
- **Never draw a curve.** Spin is an impulse at contact only — a follow kick at
  ball contact, a side kick along the tangent at cushion contact — and the cue
  ball travels dead straight between contacts. Confirmed by reading the source.
  Coaching diagrams that show side spin "curving" a shot are describing
  squirt and swerve, which this physics does not model.
- **Use `pot_assessment()`, never `pot_estimate()`.** The first is the human
  model and takes the actual aim error; the second is the AI model and is known
  to be over-harsh at distance (see Open questions).
- **Cap the prediction at cue plus first object ball plus cushions.** A break is
  multi-body and chaotic; drawing a secondary scatter fan would be fiction
  dressed as a projection. Coaching diagrams draw it illustratively — we cannot.
- **Respect the performance ceiling.** Rendering is pure software and full-screen
  can already land on an unaccelerated blit path (Known issues #1). A table read
  is roughly 15 balls × 6 pockets plus corridor checks; compute it on rest or on
  change and cache it, never per frame.
- **Design grammar** drawn from real coaching diagrams: dashed lines read as
  *projection* rather than as objects; high chroma against the cloth; a glowing
  marker at every contact point; a perpendicular tick to show the 90°
  cue/object relationship after contact.

*Open questions, genuinely undecided:*

- How many bounces to trust before the prediction stops being honest.
- Whether the table read is **cue-independent** (fixed by table geometry — the
  ball-to-pocket line and whether the knuckles shadow it) or **cue-dependent**
  (cut angle and pot chance from where the white actually is). "Nearest" and
  "easiest" are not the same thing, and easiest is the coaching-correct one: a
  ball six inches from a pocket but the wrong side of the jaw is near-impossible,
  while a dead-straight ball four feet out is easy.
- How to avoid visual spaghetti — fifteen balls each drawing a line to a pocket
  is unreadable. Likely a full line only for the aimed or hovered ball, and a
  small marker for the rest.
- Whether reference imagery lives anywhere in the repo. The no-asset-files rule
  governs what the *game* loads at runtime; documentation images are arguably a
  different question, but it is a decision to take rather than assume.

*Build order suggestion:* the cushion reflection against the real nose loop is
increment 1, because parts 1 and 3 both depend on it and the primitives already
exist. The panel has no automated visual check (see the note in the handoff),
so every increment needs an eyeball at the keyboard as well as the chain.

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
