# Roadmap

## Current status: r54 — playable, validated

**Validation snapshot (r49, measured on nix5 and reproduced in a Linux
container):**

| Check | Result |
|---|---|
| `py_compile` (both files) | OK |
| `--selftest` | ALL PASS — 112 assertions |
| `--batch 30` | 0 containment escapes |
| `--smoke` | 90 frames OK |
| `--snap` | md5 `62c87ddb6d1f0ee36f36a71a5000cd5f`, byte-identical to the R6.1 baseline |
| `--aigame 12 --seed 4200` | SHARK 9–3 STEADY (nix5), all games completed cleanly |
| `cushion_path.py` standalone | SELFTEST OK — 36 primitives |

The `--aigame` figure is unchanged, which is the point: r28 through r30 add
tests and human-facing controls and touch no AI code, so the AI must be
untouched. `--snap` staying byte-identical says the same thing about the
rendered scene — the panel is not drawn headlessly, so it proves the *table*
render is untouched and nothing about the picker.
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

`hustler.py` is ~10,830 lines; `cushion_path.py` ~515. The game is two files,
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

**League mode — next, and unscoped by choice.** Single player against a set of
AI opponents across a fixture list, results feeding a standings table
(played/won/lost/points) and a final ranking. This suits what the project is
actually for: the human plays every fixture rather than watching AI play. The
Grannie feeds in — a whitewash, where the winner clears their colours and the
black while the loser pots nothing. Detection is a small check at frame end;
the visual payoff the Maker wants (a granny on the win screen with big text) is
the part that touches the no-asset-files rule and needs a decision, not an
assumption. A code-drawn cartoon keeps the constraint; a photograph breaks it.


> **Cue-ball strike point and tip size (r30) is done.** The SpinPad had the
> power slider's pre-r29 defect to within a rounding error — 0.028 of spin per
> pixel against a two-decimal readout, and `nudge_spin()` did not snap. It now
> snaps to the same 0.01 grid power uses, and the picker moved to its own Spin
> tab at 100 px radius, which is one grid step per pixel exactly. All three
> forks were decided against their original leanings and the reasoning is in
> [CHANGELOG.md](CHANGELOG.md): the picker is on a tab rather than over the
> table, because an overlay sits on the cloth exactly when the table needs
> reading; it snaps to a grid with the seventeen named points drawn as guides
> rather than as snap targets; and the drawn rim *is* the unit circle, with no
> greyed band, because this engine models no miscue limit and the two candidate
> radii for one disagree. Selftests 62 and 63.
>
> Two residuals, neither pursued. The engine still models no tip, squirt or
> swerve, so the advisory ring at 0.75 R is a drawn note and nothing reads it.
> And the picker's own layout is only checkable by instrumenting the real panel
> builder, which is the blind spot below.

**Visual training overlay / coach mode — SHELVED.** Scoped in detail below
and deliberately set aside. Its dependency was discharged when the strike
point shipped at r30, but the Maker has since chosen a different form for the
same idea: rather than drawing predictions on the baize while you play, the
game records what you actually did and tells you afterwards. Everything below
this paragraph is still worth reading for what was settled — particularly that
the overlay must not assert a miscue limit the engine does not model — but it
is not a work item. **AI learning is shelved too:** the AI stays
fixed-parameter emergent, and nothing adapts itself between games.

One thing r30 adds to the list of settled constraints: the picker asserts no
miscue limit, because the engine has none. A coach overlay must not either.

What exists today is the r14 aim overlay (toggle `G`, or the button on the Game tab): one shot, one
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

### The live direction — shot log, profiles, tournament (r32-r34)

What the Maker actually wants from here, in their words: record every shot;
give each player a profile that improves over time; let a human's accumulated
style drive an AI opponent; and build up to a tournament where humans and AIs
compete to be Hustler Ranked #1.

**Built and shipped.** A per-shot ledger (`~/hustler_shots.jsonl`) carrying
provenance — human or AI, practice or tournament, called or not, and which of
the two difficulty models produced the prediction — plus the raw geometry of
every shot: cue ball, object ball and the whole table layout in metres. Angles
are derived from those on read, never stored, so a statistic that turns out to
have been computed wrongly is a function to rewrite rather than data to
migrate. Called shots are nominated on a scale model of the table in the Spin
tab, and a lamp in the status strip says whether the call came off. `--stats`
reports accuracy banded by approach angle, distance and spin family. The solo
clearance rules are built and tested: any colour in any order, black last,
fouls cost ten seconds, black-before-the-colours ends the run.

**Two findings that shape what comes next.** A human aiming through the HUD
has near-zero aim error — measured at 0.14 degrees against the study AI's 0.63
— because the overlay tells them where to aim. Cloning a style from that would
produce an AI that never misses. A human's style therefore lives in shot
SELECTION, not execution, and `PoolAI._search(..., execute=False)` already
enumerates every shot that was available at each decision point. And no choice
of spin can rescue a missed direct pot, so "what would have worked" analysis
must not offer one.

> **Logging the leave (r35) is done, and it absorbed item 2.** Rows now carry
> `cue_rest`, `leave_layout`, `cue_trail` and `drop_pockets`; the drop pocket
> is read off the sensor that fired rather than inferred from a last position,
> so recording which pocket swallowed which ball came with it rather than
> after it. `STUDY_SCHEMA` is 5. Nothing visible changed — no `--stats`
> section, deliberately, so the reading is designed against real rows.
> One residual, tracked at [KNOWN_ISSUES.md](KNOWN_ISSUES.md) #4:
> `shot_accuracy` still scores on the ball rather than the pocket. The data is
> now there; tightening it would re-base a figure already read off a real
> session and would mix schema 4 and schema 5 rows on one scale, so the
> pocket-accurate number will arrive alongside the existing one.

> **Geometry on uncalled shots (r36) is done.** The object ball now comes from
> r35's contact trail and the target pocket from the recorded drop pocket, or
> from the departure line where the ball did not drop — with a 50mm refusal
> threshold so a shot that was not a pot attempt records no target rather than
> a plausible wrong one. Derived on read, so it works on shots already logged:
> 59 of the 67 rows in the first real session now carry a target, up from 12.

> **Solo mode (r37) is done.** A fourth mode: rack, study the table, and the
> clock starts on the first strike. Any colour in any order, black last; fouls
> cost ten seconds; an early black ends the run. The clock switches off and the
> run resets without re-racking. `solo` is a third shot-log tag. The eighteen
> `mode == 0` tests are gone — `mode_intents()` answers from a mode's name and
> self-test 84 pins the whole table, so a fifth mode fails the build until it is
> classified.

> **The break is marked (r39).** Rows carry `break_shot`, observed at the
> table rather than inferred from a full rack. A `--stats` break section —
> pot rate, scratch rate and how far the pack spread, split by power — is
> deliberately NOT built yet: on the day it shipped there were zero flagged
> breaks, and a table built on the nine inferred ones would have looked
> authoritative and been partly guesswork. It goes in once real breaks have
> accumulated.

> **The aim dial (r40) is done.** Radius 100 where it fits (0.573 deg/px,
> against 1.51 before), its own Aim tab plus a Shot-tab copy, plain degree
> ticks every 10 with every third labelled, and a 0.01 snap shared with the
> nudge buttons. All three shot controls now reach the precision they display.

> **Shot and scratch diagnosis (r43/r44) is done, and it mostly consisted of
> reading data that was already there.** No new field was written for either.
> r43 found the pot rate was flattering the player: `shot_target` refuses to
> name a pocket when the departure line points nowhere near one, which is right
> for a safety and wrong for a shot missed so badly it stopped looking like an
> attempt — 22 such rows were being dropped from the denominator, worth 5.3
> points. Both denominators are now reported and the gap between them is the
> uncertainty. Every band grew its 95% Wilson interval, which `wilson_interval()`
> had been able to supply since r15 without the player-facing report ever asking.
> r44 added the foul section: fouls are derived from `potted` and
> `first_contact`, so the whole history reports, and solo is counted separately
> because solo is the only mode where a foul is charged.

> **Sessions (r45) are done.** Human rows carry `session` and `t`; schema 7;
> `--stats` gains a BY SESSION block. A session is one run of the program, not
> one day. The guard matters more than the feature: the study JSONL is
> byte-identical for a fixed seed, which is how r17 proved three optimisations
> behaviour-preserving, and a timestamp in the shared record builder would have
> retired that technique without failing a test. Assertion 96 fails if the
> fields ever move off the human path.

> **The Grannie (r46) is done** — the first piece of league mode. Judged on the
> colour that never went down rather than on who potted it, which needs no new
> tracking at all. The permanent record arrives with profiles at r47.

**LEAGUE MODE is under way, and the Maker has now set the requirements.**
A league of **eight** (expandable), **one frame per fixture** (expandable). The
Maker is the only human; every other player is AI. They play only their own
fixtures and **AI-vs-AI games auto-resolve in real physics** — measured at
~3.7s per frame on one core, so a single round-robin's 21 AI fixtures is about
78 seconds before any multi-core help. Timing r17's Pool on real hardware is
finally worth doing.

Then **play-offs** — quarter-finals, semi-finals, final — with a trophy added
to the winner's profile, and a Grannie recorded there too. **Every player,
human and AI, carries a tracked profile with stats**, keyed per player, so
anyone else playing the game gets their own career rather than joining this
one. **Rankings** are wanted alongside the league, and are not yet scoped.

A **start menu / career mode** hosts all of it. That is not decoration: the tab
strip divides the panel evenly and centres labels with no shrinking, so at 1.5x
a seventh tab gets a 55px cell while "League" renders at 78 — there is no room
for a League tab, and a standings table and a knockout bracket never belonged
in a 260px column anyway. **The menu must be gated `if not smoke:`** — `--snap`
runs `run_gui(smoke=True)` and saves the presented frame, so an ungated menu
would rewrite the sacred baseline.

Mid-frame **save and resume** is wanted, and is cheaper than it sounds: save
only at rest between shots and there are no velocities to store, because they
are all zero. `serialise_layout()` already stores positions in metres and is
covered by selftest 37 — that plus the rules state on `Game` is a resumable
frame.

Increments: r46 Grannie ✔ → r47 readout to the band ✔ → r48 profiles ✔ →
r49 menu/career shell → r50 league, fixtures, auto-resolve, resume →
r51 play-offs and trophies → rankings.

Still queued behind it: the style fit from shot selection, and tournament
mode.
The Maker has points they want to discuss. It has been offered three times as a
side option and they have never yet set out their own requirements, so the
first job is to hear them.

What is known so far: the human plays every fixture against a ladder of AI
opponents, results feed a standings table, and everyone is ranked at the end.
The Grannie belongs here — and its visual payoff, a granny on the win screen,
is the one part that touches the no-asset-files rule, so it needs an explicit
decision rather than an assumption.

Most of the substrate exists. A ladder of opponents is a list of
`(aim_jitter, threshold, greed, caution)` tuples, and r18 made skill a clean
independent dial. `rate_ci()`, `attempt_population()` and `sessions()` give a
standings table honest uncertainty for free. The old blocker — "standings only
make sense once the turn-handover bug is fixed" — was cleared at r23 and is
covered by selftest 52, with r28's play-through test driving a whole frame.

Two questions to settle early: where league state lives, since a league spans
sessions and needs to survive a restart; and whether AI-vs-AI fixtures are
simulated when the human is not playing, or whether only the human's results
drive the table. The second changes the whole shape of the feature.

Still queued behind it: profile writing and a ranking display carrying its
Wilson bounds (which league mode may absorb), the style fit from shot
selection, and tournament mode.

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
