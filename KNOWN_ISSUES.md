# Known Issues

The honest state of the open threads as of r62. None of these stop the game
being playable. Each is written up with its diagnosis so the next person to
touch it (quite possibly future me) starts from the answer, not the symptom.

---

## 1. Full-screen at startup can run slowly on some systems

**Symptom:** the game can be sluggish or jerky when it starts full-screen, even
where a manually-maximised window runs smoothly.

**Diagnosis:** rendering is pure software (no GPU acceleration). A borderless
window created at full desktop resolution can land on an unaccelerated blit path
on some desktop environments, where a window the OS resizes to the same size
stays accelerated. Same pixel count, very different speed. A wedged compositor
or graphics driver can make it worse, and a reboot often clears that.

**Workarounds today:** reboot if it appears after the system's been up a while;
or start windowed and press `F11` to go full-screen once running.

**Options for a proper fix (not yet applied):** start windowed by default;
render at a fixed internal resolution and scale the finished frame up to fill
the screen (fewer pixels drawn, still full-screen); or add scaling/vsync flags
to the full-screen mode to try to keep the accelerated path.

**Worth knowing before adding features:** this is a real performance ceiling.
Anything that draws or recalculates every frame — a richer aiming overlay, a
per-ball table read — should compute once when the balls come to rest and cache
the result, rather than recomputing while you line the shot up.

---

## 2. The flat floor is a reasonable average, not an exact fit

Updated twice now. The first widened sweep (d_tp 0.15-0.7 m, n=300/cell)
suggested the floor might drift down as d_tp grows (0.7 m read ~10% low). A
follow-up at n=1500/cell over d_tp 0.7-1.0 m did not confirm that: the
per-d_tp means came back 0.177 / 0.206 / 0.234 / 0.222 — noisier, and if
anything drifting *up*, not down. d_tp is not the variable that matters.

What the extra precision found instead: recomputing the underlying aim-error
term (`p_aim`, pre-floor) for every floored cell across both sweeps and
sorting by it shows measured pot rate rising smoothly with `p_aim` even
*within* the floored region — from ~0.15-0.16 in the deepest, most-collapsed
cells (p_aim near 0) up to ~0.22-0.28 right at the point a shot first crosses
into floored territory. `POT_FLOOR = 0.19` is the reasonable single-number
average of that curve, not a genuine plateau — it under-predicts by up to
~0.09 near the crossover and over-predicts by up to ~0.04 at the extreme.

Both errors are far smaller than the pre-r25 bug (which ran up to 30x off,
not ±20-40%), so this is a second-order shape question, not a repeat of the
original problem. Decided not to chase further for now: fitting that curve
would need 2-3 new free parameters against the ~24 data points gathered so
far, on one corner pocket — a real overfitting risk on the same "fitted, not
derived" budget that produced the current fix.

**Pocket type is now tested, and answers the question this issue opened
with: it isn't a significant factor.** `distance_calibration_sweep.py` gained
a `--pocket-type` axis (corner vs. middle — capture_points()[0] and [4],
`pot_drill`'s own convention) and swept both at n=300/cell, 137 valid cells.
The raw pooled means looked different at first (corner 0.136, middle 0.099),
but that turned out to be a sampling artifact, not a pocket-type effect: a
middle pocket's throat axis is capped by the table's 0.91 m WIDTH rather
than its 1.82 m length, so the middle-pocket cells that survive geometrically
skew toward deeper, more-collapsed shots than the corner cells do — and
depth of collapse (the `p_aim` shape from above), not pocket type, is what
actually drives the number. Directly comparing cells with IDENTICAL t_cue,
d_tp and cut angle on both pocket types (7 matched pairs) found no
statistically distinguishable difference in six of them, and only one
borderline case. Conclusion: don't model pocket type as a separate factor;
the existing p_aim-shape question above already covers it.

---

## 3. A short, thin cut can measure 0% while reading as the floor's safest case

Surfaced by the same pocket-type sweep, and distinct from #2: at t_cue=0.15 m
with a 60-degree cut and d_tp 0.5 or 0.7 m, measured pot rate is **0/300** —
Wilson CI [0.000, 0.013] — reproduced on both a corner and a middle pocket.
That's a genuinely different shape from the rest of the floored region
(which reads 0.15-0.28 depending on how deep the collapse is, per #2): it's
not just "low," it measures as never happening.

What makes this worth its own entry rather than folding into #2: `lever`
(the r16 term) treats t_cue -> 0 as the BEST case, unconditionally — point-
blank range is where the model is most confident. This cell is the shortest
t_cue in the whole grid, and it's the one that fails outright.

**Diagnosed, by stepping through individual trials rather than running
another statistical sweep.** The initial guess — the cue ball's own path
fouling the object ball's line, a "kiss" — doesn't hold up: logging the
object ball's own departure angle right after contact (settled, not the
instantaneous collision velocity) shows it is ALREADY off the ideal
object-to-pocket line by several degrees, well before the cue ball could be
involved. Ball shapes carry `friction=0.05` (confirmed by inspecting the
pymunk shapes directly) — small, but real ball-to-ball friction, which
produces genuine "throw": a thin-cut collision drags the object ball's
departure angle away from the pure geometric ghost-ball line by an amount
that grows as the cut gets thinner. At this cut (fullness = 0.195, barely
above the 0.10 rejection floor), 10 trials at fixed geometry with only the
random aim jitter varying showed departure-angle deviations of 0.5-12
degrees against a pocket that only tolerates about 3.7 degrees
(`asin(cap_r/d_tp)`) — and the deviation did NOT scale cleanly with aim
error: two trials with aim error under 0.06 degrees (as close to a "perfect"
hit as the jitter model allows) still deviated by 0.5-2.8 degrees, which a
pure aim-angle-error model has no way to produce. `pot_estimate()`'s
ghost-ball geometry models zero-friction, zero-throw contact; the simulation
correctly does not. The gap between them is throw, and it isn't currently
represented anywhere in the estimate — only cut-thinness's effect on
*aim-error amplification* is (`max(fullness, 0.15)`), not its effect on throw
itself.

**Measured, and it doesn't reach that far.** Two checks, not one. First, a
deterministic zero-jitter probe (single trial per angle, no randomness to
average out) at cut 0/5/.../60 degrees, t_cue 0.3 and 0.7 m, d_tp 0.3 m: pure
throw bias stayed under ~2.5 degrees through cut=50, comfortably inside the
pocket's +-6.2-degree tolerance at that d_tp, then jumped to several degrees
past cut=60. Second, and more decisively: the existing large-sample data
(n=300/cell) already covers cut=0/20/40/60 across many t_cue/d_tp
combinations, and a fresh n=300/cell run filled in cut=15/25/30 specifically.
Tracking the actual/predicted ratio across cut angle for each fixed
(t_cue, d_tp): from 15 to 30 degrees the ratio moves inconsistently — up in
some rows, down in others, by amounts consistent with sampling noise (e.g.
(t_cue=0.7, d_tp=0.3): 0.89 / 1.01 / 1.26; (t_cue=0.9, d_tp=0.5): 0.67 / 0.72
/ 0.77). No row shows a clean decline. By cut=60, nearly every row does —
sharply (0.75, 0.38, 0.00, 0.42, 0.44, ...).

**Conclusion: throw is real but narrow.** It is not a meaningful contributor
to #2's near-crossover/deep-extreme shape mismatch — that data was gathered
almost entirely at cuts <= 30 degrees, exactly the range this check just
cleared. It only becomes a pot-crushing factor once cuts get thin enough to
approach the fullness=0.10 rejection edge (roughly 40-60+ degrees) — which is
to say, it matters precisely in the extreme-cut regime this entry describes,
and nowhere else that's been measured so far. Modelling it explicitly in
`pot_estimate()` would only pay off for shot selection right at that extreme
edge, not for the floor's general accuracy.

---

## 4. A called shot scores on the ball, not the pocket

`shot_accuracy` counts a call as made when the nominated BALL goes down. It
does not check that the ball went down the nominated POCKET.

As of r35 the log **does** record the drop pocket, so the information is now
there — this is a reader that has not been written yet, rather than data that
does not exist. It was left deliberately: tightening `shot_accuracy` would
silently re-base a figure already read off a real session, and would put rows
written under schema 4 (no drop pocket) and schema 5 on the same scale. Pooling
across a provenance boundary is the exact failure the provenance fields exist
to prevent.

So a ball called into the top-left and rattled into the middle still scores.
The pocket-accurate figure will arrive as its own number alongside the existing
one, with the shot-diagnosis work, so nothing that exists changes meaning.

## 5. The schema's `foul` field is never filled in on a human shot — FIXED at r55

**Closed.** The diagnosis below was right and the dismissal was wrong. It was
filed as "only bites in game modes, and the log has no game-mode rows" — then
the league arrived, fifty tournament rows were written, and every one of them
logged a null foul in exactly the mode the Maker would now be playing most.

The fix is the one the diagnosis implied: the row is HELD rather than written
above the game block, and flushed once `on_rest()` has decided the foul and
written the event. `flush_human_row()` uses the same fouls-delta the AI study
path has always used. Sandbox and solo rows still go straight out — there is no
Game to wait for, and r44's `foul_summary()` derives solo fouls from `potted`
and `first_contact` regardless.

**Lesson worth keeping:** "harmless because nothing exercises it" is a statement
with a shelf life. This one expired the moment a feature started exercising it.

### The original diagnosis, kept for the record

**Symptom:** `foul` is null on every human row in the log — all 244 of them at
r44, including rows written by the newest schema version. `event` is null too.

**Diagnosis, and it is two different things wearing one label.**

`event` is correct. It is passed `game.last_event`, and `game` is `None` in
solo and practice — there is no rules engine running in those modes, so there
is genuinely no event to record. Nothing to fix.

`foul` is a real gap, but not one a missing argument would explain. The human
log write sits **above** the game block in the frame loop, deliberately: it is
not gated on `game`, because sandbox has no `Game` object and sandbox is where
practice frames happen. That means at the moment the row is written,
`game.on_rest(sim)` has not yet run for this shot — the foul has not been
decided. Passing `game.fouls` there would read the *previous* shot's count, and
`game.last_event` in a game mode would carry the previous shot's event rather
than nothing at all. So the fix is not a one-liner; it needs either the record
back-patched after `on_rest`, or the write moved below the game block without
breaking the sandbox path it was put above for.

**Why it is not urgent.** In solo, a foul is fully derivable from fields the log
already carries — `solo_apply_shot` defines one as the cue ball potted or
nothing hit at all, and both are recorded. r44's `foul_summary()` reports them
from history rather than from the day it shipped. The gap only bites in game
modes 1 and 2, where a foul depends on rules that cannot be reconstructed from
the row, and the log currently holds **no game-mode rows at all** (140 solo,
104 practice).

**What to do when it matters:** the first time a frame is played against an
opponent with logging on, this becomes real. Fix it then, and note that the
`event` field in that mode is not merely absent but *stale*, which is worse —
that conclusion is read from the code and has never been tested against a real
game-mode row, because there aren't any.

---

## 6. `league_ai()` returns `None` for a name not on the ladder — FIXED at r60

**Symptom:** none in normal play. Found by a test harness, not by playing.

**Diagnosis:** `league_ai(nickname)` returns `None` for any name not in
`LEAGUE_LADDER`, and `play_ai_game(names=...)` hands that straight to
`ai.choose(...)`, so a fixture involving an off-ladder name dies with
`AttributeError: 'NoneType' object has no attribute 'choose'` rather than saying
which name it did not recognise.

**IT WAS REACHABLE, AND THIS DIAGNOSIS WAS WRONG (corrected r60).** The
`--league` CLI took the human's name from `HUSTLER_PLAYER`, defaulting to the
literal "PLAYER" — so the pending list excluded nobody, and `--league resolve`
tried to play the Maker's own seven fixtures and crashed. Fixed at r60 by
screening on the LADDER rather than on who the human is, refusing unrostered
names by name in `play_ai_game`, and defaulting the human to the profile store's
`kind == "human"` entry. Assertion 118 pins all three. The original reasoning is
kept below because the way it was wrong is instructive: it was true of the menu
and false of the CLI, and "harmless because nothing exercises it" lasted three
releases.

**The original (incorrect) reasoning:** the human's name is never on the ladder, and
both `league_pending_ai()` and `playoff_pending_ai()` exclude every fixture the
human is in — so the only names that reach `play_ai_game` come from the ladder
by construction. The crash needs a league whose players include a third name
that is neither the human nor a ladder entry, which nothing can currently
create.

**Why it is written down anyway:** r55's lesson, in as many words — *"harmless
because nothing exercises it" is a statement with a shelf life*. KNOWN_ISSUES #5
was filed at r44 on exactly that reasoning, and the league then produced fifty
rows in the mode it broke. The league file is tracked precisely so the Maker can
hand-edit it, and the reader tolerates hand edits by design; a typo'd nickname is
the obvious way in.

**The fix when it is wanted:** refuse the fixture with the offending name in the
message rather than resolving it, in the same posture as r53's seat check, which
says *"X is not on the ladder"* instead of quietly seating somebody else.

---

## 7. The live SOLO line overflows the narrow strip (not the band)

**Symptom:** in the fallback status strip — not the band the readout normally
uses — the running solo line is cut off on the right.

**Diagnosis:** measured at r57. `SOLO 4:34.3   6 colours + black  (2 fouls)` is
**344px at 1.0 scale against a 240px strip budget**, and 559px against 370px at
1.5. It predates r57 and is not caused by it. Since r47 the readout lives in the
band above the table, where the budget is 996–1734px and it fits comfortably, so
this only bites when the band cannot be used.

**What r57 did about it:** did not make it worse. The personal-best suffix is
width-aware and is dropped rather than appended when the line will not take it —
without that guard the same line would have gone to 448px at 1.0 scale.

**The fix when it is wanted:** shorten the fields for the strip case only
(`6 col + black`), or let `wrap_fields` split this line rather than emit one
over-wide field. Both are cosmetic and neither is urgent while the band is the
normal path.

---

## 8. The banner never named the mode in Sandbox or Solo — FIXED at r65

**Symptom:** the Maker, on shipped r64.1: in Sandbox the banner "rests on Ball
in Hand — Drag Cue in Baulk" and the word "Sandbox" never appears. In Solo the
mode is likewise never named.

**Diagnosis:** two faults stacked, and the second was only found by re-running
the frame loop after fixing the first.

The resting line was taken as `status_lines2[0]`. That slot holds the
mode-or-names line only in a **game** frame — in Sandbox it is the ball count,
in Solo the clock — so `banner_line()` was never reached in half the modes. The
banner was built and tested in a YOU vs AI frame, the one arrangement where the
wiring happens to be right, and assertion 123 tested `banner_line()` in
isolation, so it passed for the whole of r64 and r64.1 while nothing called it.

Solo was worse than a wrong word. The clock ticks ten times a second, so the
resting line changed at 10Hz and every change restarted the roll. Measured over
600 frames: `roll_frac` never once reached 1.0 (max **0.313**, mean 0.132). The
banner sat permanently a third of the way through a roll. This is why Fork 1B
(Solo keeping the clock in the banner) was withdrawn rather than offered.

**And fixing that was not enough.** Ball-in-hand is a persistent *state*, and
r64 re-pushed any transient once its dwell expired — so it re-armed forever and
the banner still never returned to "Sandbox". A resting-line fix on its own
changed nothing the Maker could see.

**The fix:** `band_lines()` derives the resting line from the mode always and
routes persistent facts to the sub-line (whose `if game is not None` gate is
gone). `banner_new_msgs()` triggers on the rising edge, so a state announces
once, rolls away and gives the banner back, while staying readable in the
sub-line. Measured after: Sandbox settles on "Sandbox" at 2.6s; Solo's roll
completes 460 frames of 480.

**The lesson worth keeping:** an assertion on a pure helper proves the helper,
not that anything calls it. Assertion 124 asserts the split the render actually
consumes.

---

## Recently fixed

Resolved in r23–r27 — kept here briefly because the diagnoses are worth having
if anything similar shows up again. Full descriptions are in the changelog.

- **A second solo clearance could be dropped in silence (r58, introduced r57).**
  The run state was six separate locals and only `do_rack` reset all six;
  `do_cycle_mode` and `do_reset_solo` reset three each. Reaching SOLO by any
  route but pressing T carried `recorded` over, so the next clearance found the
  once-only guard already set and was never written. Fixed structurally: one
  constructor, one reset, three call sites, and the state can no longer be
  half-reset. Assertion 116 pins all three routes.

- **The last row of the league table was never drawn (r56).** The standings box
  in the career menu was 214 scaled units at 24 a row, which fits a header and
  seven rows — of eight. The row that fell off was the bottom seed, which for
  the whole of season 1 was the Maker's own, so the highlight colour marking
  their line had never once rendered. Fixed by deriving the box height from the
  number of players and the panel height from the stack of widgets, rather than
  hand-totalling offsets inside a box fixed at 560 units.

- **The Resume button had the footer text printed over it (r56).** Resume ran
  636→670 while the two footer lines were positioned from the panel bottom at
  634 and 654, and the footers draw last — 36px of overlap at 1.0 scale, 54px at
  1.5. Same root cause as the row above, and the same fix: the footers get rects
  from the same cursor as everything else.

- **A season was never reproducible (r56).** `league_resolve_ai()` seeded each
  fixture from `abs(hash(key))` and documented the result as reproducible.
  CPython salts string hashing per process, so the same fixture drew 106203,
  62979 and 49318 on three consecutive runs. Order-independence within a single
  run was real, which is why it never looked wrong. Replaced with
  `stable_seed()` over CRC32, and the self-test pins a literal value rather than
  checking the function against itself.

- **A shot played without a call carried no pot geometry (r36).** `shot_pre`
  resolved the object ball from the *nominated* ball, so an uncalled shot had no
  object position and therefore no cut angle, distance or approach angle — 55 of
  67 rows on the first real r35 session, including every shot of the best game.
  Fixed by reading rather than writing: the object ball comes from r35's contact
  trail, and the target pocket from the recorded drop pocket where the ball went
  down, or from the line it departed on where it did not. No schema change, so
  it works on shots already logged. Self-test 83.

- **The shot log recorded the table before a shot, never after (r35).** Every
  row carried the cue ball, the object ball and the whole layout as they stood
  at the moment of striking, and nothing carried the other end — where the cue
  came to rest, what it touched on the way, or which pocket swallowed a potted
  ball. "Why did the white go down" was therefore unanswerable from the log,
  and the shot-diagnosis work was blocked behind it. Rows now carry `cue_rest`,
  `leave_layout`, `cue_trail` and `drop_pockets`; `STUDY_SCHEMA` is 5. The
  trail is de-duplicated at source, which is not a detail: post_solve fires
  once per substep, so an ordinary shot generated fifteen cue-cushion callbacks
  for four real rebounds. Selftest 82.

- **The potted-ball chamber never cleared in sandbox (r27).** Re-rack (`T`),
  reset (`R`) and clear (`C`) all rebuilt the table but left the previous
  frame's balls in the chamber, which then accumulated across frames.
  `potted_all` (the game-scoped history the chamber reads, added at r22) has
  always carried a comment promising "only a rebuild/new rack resets it" —
  nothing ever did. Invisible in the game modes, which build a whole new
  simulation on a re-rack; sandbox is the only path that reuses one, and it is
  where the game is mainly played. Fixed with `reset_potted_history()`, called
  from `clear_objects()` and from `rebuild()` **only when no ball positions are
  carried over** — a rebuild *with* positions is a live slider (ball radius,
  cushion elasticity, rolling friction) and the frame in progress, chamber
  included, must survive it. Selftest 58 pins both halves.
- **`POT_FLOOR` sat above both AI personalities' attempt threshold (r26).**
  Left over from the r25 fix below: `POT_FLOOR` (0.19) was higher than both
  SHARK's (0.10) and STEADY's (0.18) "confident enough to attempt" threshold,
  so any long/thin shot that collapsed to the floor cleared both thresholds
  identically regardless of how different those numbers were meant to be.
  `floor_threshold_audit.py`, a new tool, watched 50 real AI-vs-AI games and
  measured it: 30.6% of ALL shots were floored pots, and 88.7% of those would
  have been a safety instead without the floor — not a rare case, roughly one
  shot in three. SHARK's threshold (0.10) is left alone, since an aggressive
  personality attempting a genuine ~19% shot is in-character; STEADY's moves
  to 0.24, clear of the floor. Re-measuring confirms it: STEADY now shows 0%
  floored pots and its safety rate rose from a blended ~9% to 41.8%; SHARK is
  unchanged. A personality-tuning fix, not a `pot_estimate()` change.
- **The AI was too cautious at distance (r25).** A dead-straight pot from
  about two-thirds of a table length was rated at roughly 9% when it actually
  drops more like 19-20% of the time, so the AI declined a lot of makeable
  long shots. `pot_estimate()`'s distance term had no floor and decayed
  toward true zero; `distance_calibration_sweep.py` fired 300 real,
  physically simulated shots per cell across a t_cue/cut-angle grid and
  measured a pot rate flat at ~19% from about 0.9 m out, regardless of
  exactly how bad the shot got within that range. `POT_FLOOR = 0.19` now
  clamps the prediction to that measured floor instead of letting it
  collapse — fitted against the Monte Carlo rig, per the fix this issue
  always called for, not derived and hoped for. Left two follow-up threads,
  chased down above (#2) and to r26 (the threshold interaction).
- **Couldn't place a ball on the pocket jaws in custom mode (r24).** The
  placement test treated the table as a rectangle, which walls off the pocket
  mouths (there is no cushion across a mouth). It now tests against the real
  tangent-true cushion-nose polyline — inside the loop and a ball-radius clear
  of every edge — handling rails and mouths in one rule, no special cases. An
  earlier "exempt the mouths" attempt leaked along the side rails and was
  reverted; the polyline approach has no such failure mode, and the regression
  guard that caught it is still in the suite.
- **Cue ball couldn't be repositioned after a scratch or on the break (r23).**
  The simulation auto-respotted the white before the rules layer could offer you
  the placement. Fixed with an explicit flag set by whoever builds the
  simulation, so the physics layer still knows nothing about the rules layer.
- **Potting your last colour handed the table back (r23)** on a phantom foul.
- **Spin didn't reset between shots (r23).**
- **Sandbox had no ball-in-hand concept (r23)**, so solo play couldn't place the
  white.

---

## A note on how these were found

None of the four r23 bugs were caught by the validation chain — not by the
self-test suite, not by the batch containment run, not by the smoke render or
the byte-identical screenshot check. All four were found by sitting down and
playing a game. The r27 chamber bug makes five: it was spotted in a screenshot
of an ordinary frame, where the chamber showed three reds against a table
missing one ball.

That's worth remembering when adding tests. The suite is very good at pure
functions and physics invariants, and blind to whether a turn passes to the
right player. A scripted play-through test — drive a whole frame through the
rules engine and assert the turn, visit, spin and placement state at each step —
would cover the gap these four fell into.
