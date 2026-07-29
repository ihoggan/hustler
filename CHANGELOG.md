# Changelog

A plain-language history of how HUSTLER came together. Revision tags (R6, r15,
etc.) are the internal build markers used during development.

---

## r33 — calling your shot (current)

The first visible half of the stats work. A scale model of the table now sits
in the Spin tab: click a ball, click a pocket, take the shot. That nomination
is what makes a result meaningful — without it, "did it go in" has no answer,
because nothing knows where it was supposed to go.

The model is not a drawing of a table. It is the actual `nose_loop_m()`
cushion polyline and the actual `capture_points()`, scaled down, so the jaws
sit exactly where they sit on the full-size table. A mini table with invented
pockets would misplace the one feature that decides whether a pot survives.
Both axes take the same scale, for the same reason: stretched to fill its box,
a click would land on different geometry from the one under the cursor.

Nomination is HUD-only, like every other shot parameter. The widget converts
its own pixels, never a table click, so R6.6 is untouched.

A click that lands nowhere near a ball or a pocket nominates nothing rather
than snapping to whatever happened to be closest. A call the player never made
is worse than no call at all — an unnominated shot logs honestly as
`intent: "none"` and is excluded from accuracy, while a wrong nomination is
data that looks right.

Shooting without calling is allowed and always will be. The shot fires
normally and records with no intent; it still contributes its geometry and its
outcome. Calling can be switched off entirely.

**One thing this exposed:** sandbox has no shot-completed event at all.
`pending` is only ever set when a `Game` exists, so in mode 0 — which is
precisely where the practice frames happen — nothing ever resolved a shot. The
logging carries its own flag rather than borrowing one that was never going to
fire.

Rows land in `~/hustler_shots.jsonl`, appended, one per shot, and the write is
best-effort by design: a full or unwritable disk costs a row and never a shot.

**r33.1 adds the indicator that should have been there from the start.** A
session of real play found the gap immediately: there was no way to tell
whether a shot had been nominated, or whether anything had been recorded. A
control whose effect is invisible is a control you cannot trust — and a half
nomination, a ball chosen without a pocket, silently recorded as un-nominated:
an honest row, but not the one the player believed they were making. A small
lamp now sits in the persistent status strip, readable from every tab
including the one where the shot is actually taken, and reads dark for off,
red for armed, amber for a ball without a pocket, green for ready, and flashes
when a row lands.

**r33.2 adds `--stats`.** The log existed and was filling up correctly, but
there was no way to read it without writing a script, which is a poor place to
leave a feature whose whole point is telling you how you are playing. The
summary reports called-shot accuracy banded by approach angle and by distance,
and finishes with the spread of your aim error — which is the same quantity as
the AI's `aim_jitter`, measured rather than assumed, and eventually the number
a human profile gets cloned from. Practice and tournament are reported on
separate lines rather than pooled, and a log with no called shots says so
plainly instead of printing a confident 0.0% over nothing.

Validation: 79 assertions, 0 containment escapes over 30 batch strikes, 90
smoke frames, `--snap` byte-identical, `--aigame 12 --seed 4200` unchanged at
SHARK 9–3. Probed at three window sizes with zero widget overlaps; the caller
is omitted outright at the F11 windowed size rather than drawn off the panel.

---

## r32 — the shot ledger

Groundwork, and it changes nothing you can see. Nothing in the game calls any
of it yet: the file plays exactly as r31.1 did. What it adds is the shape the
data will be recorded in, decided and tested before a single row exists —
because a schema is the one thing that cannot be fixed afterwards. Shots
logged under an ambiguous model can never be disambiguated later; you cannot
recover, a year on, whether a given miss was a miss or a well-judged safety.

**Every row now carries provenance.** Four fields decide which records may
legitimately be added together: `source` (human or ai), `mode` (practice or
tournament), `intent` (called or none), and `p_model` — which of the two
difficulty functions produced the predicted pot chance. Each exists because
pooling across it would be a quiet lie. A human aims by typing a number into
the HUD and has no applied jitter; the AI does. In practice the player sets
the balls up themselves, so a practice pot rate measures which shots they
chose to rehearse rather than how well they play. An un-nominated shot has no
declared goal, and scoring a safety as a failed pot is the exact mistake that
cost r19 through r21 a five-hypothesis rabbit hole. And the two difficulty
models have drifted apart — different thinness term, different distance decay
— so their numbers are not on one scale.

**Aim error is now measurable, which is the interesting part.** The AI's
`aim_jitter` is noise we add, so we know it. A human's execution is exact —
the cue goes precisely where the angle says — which means all of a human's
error lives in judgement, and it is one specific number: the gap between the
angle they chose and the angle that would have potted the ball they nominated.
The spread of that over many shots *is* their aim_jitter, on the same axis r18
established for the AI personalities. It is only meaningful on a called shot,
so it returns nothing without a nomination rather than inventing a plausible
zero.

**Profiles store identity and completed frames. Nothing else.** Every
statistic — pot rate, win rate, aim spread, whatever nobody has thought of yet
— is derived from the log on read. That is what makes it safe to create
profiles before any real data exists. Store computed aggregates instead and
the day a statistic turns out to have been wrong, every profile on disk is
wrong with it. r16 found `pot_estimate` had been five times over-confident and
every conclusion drawn from it was discarded; functions over a raw log get
rewritten and re-run, stored numbers get migrated or lost.

An abandoned or crashed frame writes nothing at all. Telling a rage quit from
a power cut is not reliably possible, and a forfeit inferred from an orphaned
marker would punish the wrong player often enough to matter — so only whole,
clean games count.

**r32.1 adds the half that was missing.** The first cut recorded the cut angle
and the distance to the pocket, and stopped there — so a ball half a metre out
tight against the cushion and one half a metre out in open baize produced
identical rows. On a table with these knuckles they are not remotely the same
shot. Rather than bolt on another derived number, the rows now carry the raw
positions: the cue ball, the object ball, and the whole table layout in metres
at the moment of striking. Every angle is derived from those on read, including
the one that turns out to matter — how far round from the pocket's own mouth
axis the ball was sitting. Over four logged AI frames the pot rate runs 59%
within ten degrees of the mouth and 5% beyond thirty. Distance alone could
never have shown that.

Two things surfaced only by running the pipeline on real games rather than
fixtures. The accuracy check compared a nominated BALL against a list of
potted COLOURS, so it could never match anything and quietly scored every
shot a miss. And the AI, which does nominate a ball and a pocket before every
pot, was throwing the ball id away — its own shots were unscoreable by the
very statistic being built for them. Both are fixed; AI pot shots are now
recorded as the called shots they always were.

One known limitation, recorded rather than hidden: a shot scores as made when
the nominated ball goes down, not when it goes down the nominated pocket. The
sim does not currently record which pocket swallowed which ball.

Four assertions, mutation-tested ten ways. One of those mutants survived the
first attempt: the test that guards against counting un-nominated shots as
missed pots had no un-nominated shot in its fixture, so the guard could be
deleted with the assertion still passing. The fixture has one now.

Validation: 76 assertions, 0 containment escapes over 30 batch strikes, 90
smoke frames, `--snap` byte-identical, `--aigame 12 --seed 4200` unchanged at
SHARK 9–3.

---

## r31 — a hardening pass, and a reset that never reset

No new features. Before anything else went in, the repository was audited end
to end for the class of thing that does not announce itself: code that runs
without error and does nothing, checks that cannot fail, and guards that have
quietly been reporting green over a real problem.

**The bug.** `do_rack()` carried `finale = None`, but omitted `finale` from
its `nonlocal` list. In Python that makes the name local for the whole
function, so the reset wrote to a throwaway and the enclosing value was never
touched. Racking during the slow-mo black finale left the win animation
playing over the fresh rack until it aged out on its own. Cosmetic, and it
healed itself in about a second — but it is the second time this exact shape
has landed. At r23 the HUD's spin values were re-sent every shot for the same
reason. Nothing in the validation chain can see it, because there is nothing
wrong with the code except which variable it wrote to.

So the fix is not the one-line `nonlocal`. It is selftest 72, which reads the
compiled code objects and asserts that no nested function inside `run_gui`
assigns a piece of the enclosing state without declaring it — a leaked name
lands in the nested function's `co_varnames` when it belongs in
`co_freevars`. That guards the class rather than the instance. The assertion
carries a deliberately planted leak alongside the real check, so a clean
result cannot be a check that simply never fired; mutation testing showed the
first version of that canary was one level deep and still passed when the
detector's recursion was removed, so it is nested two deep now.

**Two assertions were being computed and thrown away.** The impact-sound test
built `ok31i_polymer` and `ok31i_lp` and never passed them to `check()`. The
comment above them said, in as many words, that these properties get asserted
rather than merely described — and then they were not. Both passed once wired
in, so nothing was hiding, but the properties that separate a polymer knock
from a glass plink had been unguarded since r8.2: noise-dominated, partials
below 1500 Hz, inharmonic, dead inside 20 ms. The sound could have been
retuned back to a plink with the whole chain green. A variable built for an
assertion and never consumed is a test that cannot fail.

**CI counted nothing.** It ran `--selftest` and trusted the exit code. Exit
codes are correct, so a genuine failure did fail the build — but a stale or
truncated file whose remaining assertions all pass exits 0 and turns the
workflow green, which is precisely how an R7-era file once survived every
check. The workflow now asserts the assertion count and the cushion-path
primitive count, both as named environment variables that must be bumped
deliberately. The upkeep is the guard. Checked against an older build: it
reports 69 assertions against an expected 72, and is caught.

**And the lint job had been green over a red check.** `isort` was failing and
`continue-on-error` was hiding it. It is clean now and blocking — and in
r31.1 the last soft failure went with it. No step in the workflow carries
`continue-on-error` any more.

black was removed rather than fixed. Its diff on this repository runs to 1353
removals against 2469 additions, roughly a third of `hustler.py`, and 251 of
those lines are aligned inline comments — including the configuration table
where the alignment is doing real work explaining the physics constants.
Enforcing it would bury every future change under a reformat, which is the
same problem the line-ending normalisation had just removed. pyflakes took the
slot instead, and earned it: pyflakes is what found the `finale` bug in the
first place, by reporting a local variable assigned and never used. A cosmetic
check that can never pass was swapped for a semantic one that already caught
something. The two measurement scripts, tracked since r26 and never checked by
anything, are now compiled and linted with the rest.

Also: three dead locals and three placeholder-free f-strings removed, the dev
extras in `setup.py` corrected to the tools actually used, an unreferenced
104 KB image dropped, and the re-entry prompt in the handoff strengthened to
quote the file md5s and the assertion count — it had been weaker than the one
actually in use, and would not have caught the stale copy that the real one
did.

Validation: 72 assertions, 0 containment escapes over 30 batch strikes, 90
smoke frames, `--snap` byte-identical, `--aigame 12 --seed 4200` unchanged at
SHARK 9–3.

---

## r30 — a contact point you can name

Aim got fine adjustment at r10 and power at r29. Spin was the last of the three
shot parameters still set by eye, and it had the same defect to within a
rounding error: the pad is 36 px in radius, so one pixel of movement is 0.028
of spin against a readout formatted to two decimals. It displayed hundredths it
could not reach. Worse, `nudge_spin()` did not snap where `nudge_power()` did,
so a spin could be placed finely by dragging and then walked 0.3572, 0.3672,
0.3772 — tracking correctly in the readout while never once being round. A
value you cannot write down is a value you cannot play again.

Three decisions shaped the fix, and the first two were reversals.

**The picker lives on its own tab, not over the table.** Drawing it on the
baize would have given it 200–300 px and cost no panel space, which is what
first recommended it. It was rejected for a better reason than it was proposed:
an overlay sits on the cloth exactly when the table needs reading. A fifth tab
costs a click, and the persistent status strip already shows the live spin
readout on every tab, so the value is never out of sight while it is being set.

**The rim of the drawn ball *is* the unit circle.** The plan had been to draw a
whole ball with the unstrikeable outer band greyed, teaching the real
constraint. That was dropped on measurement. This engine models no tip, no
miscue limit, no squirt and no swerve — those words appear nowhere in the
source — and `spin_pad_map()`'s unit circle already means *maximum usable
spin*. Greying an outer band would have asserted a miscue radius nothing here
has measured: the conventional half-ball rule says 0.5 R, a training cue ball's
outer printed ring measures about 0.75 R through 21° of photographic tilt, and
the two disagree. It would also have cost half the picker's linear resolution
for no gain in truth. So the rim means "the most spin this engine can apply",
which is exactly true, and the teaching point survives as a dashed advisory
ring at 0.75 labelled as a real-cue note — drawn, not enforced.

**It snaps to the same 0.01 grid power uses**, on both axes, with the seventeen
named contact points drawn as labelled guides rather than as snap targets. A
seventeen-point snap would have made the picker discrete while the r10 nudge
buttons stayed continuous — two value spaces inside one control, which is the
shape of several bugs in this project's history.

Order matters, and it is the opposite way round from what feels natural: snap
first, clamp second. A 45° maximum is (0.7071, 0.7071); snapping that to the
grid gives (0.71, 0.71), whose magnitude is 1.0041 — more spin than the pad's
own budget allows. Clamping afterwards pulls it back to exactly 1.0. The
deliberate consequence is that rim values sit on the circle rather than on the
grid.

The picker is 100 px in radius, and that number is chosen rather than left
over: 1/100 is 0.0100 of spin per pixel, exactly the snap step, so every value
on the grid is reachable by dragging and no pixel is wasted. The cursor is now
drawn at true tip scale — 20% of the ball's radius, measured from that same
training ball — instead of the old hardcoded 5 px dot at 13.9%. The tip's size
is precisely why fine spin placement is hard in reality, and drawing it
honestly is part of the point. It is an outline rather than a disc so it cannot
hide the guide underneath it.

Adding a fifth tab set a trap that was caught before it bit. `custom_active()`
tested `panel_tab == 3`; inserting Spin after Shot moved Custom to 4, and
custom-mode mouse-table ball placement would have started firing on the Spin
tab with the entire validation chain still green. Tabs are now resolved by name.

**r30.1** fixed two things found by playing it. The Shoot button had been moved
up by a wrong constant and overlapped the aim row by 10 px — the `y += 34` it
replaced was never "the separation gap", it was the row's own 22 px height plus
a 12 px gap, and the comment got read instead of the arithmetic. And the ball
face had been drawn as two offset circles to suggest a lit sphere; because
`pygame.draw` paints flat, that was not a gradient but a hard-edged step from
238 to 222 at about r=0.45, with the advisory ring falling inside the darker
band. It read as exactly the greyed-out region this revision had argued against
drawing. Unrequested decoration is not free: in a control whose job is to teach
a constraint, any visual distinction will be read as meaning something. The
face is flat now.

**r30.2** puts a second copy of the picker on the Shot tab wherever the window
is tall enough to hold it, so a full-screen game never needs the tab switch at
all. Both copies are built by one function and are views onto the same two
closure variables, so there is no second copy of the state and only the visible
tab receives events. The fit rule is pure and tested: below a 60 px radius the
group is omitted outright rather than shrunk into uselessness, because the Spin
tab always carries the full-size one — omitting the convenience copy costs a
tab click, not a capability.

Validation: 71 assertions, 0 containment escapes over 30 batch strikes, 90
smoke frames, `--snap` byte-identical, `--aigame 12 --seed 4200` unchanged at
SHARK 9–3. Selftests 62 and 63 were both mutation-tested four ways before
shipping.

---

## r29 — power you can name

Aim had fine adjustment from r10. Power did not, and the difference was not
cosmetic: the slider spans 6.5 m/s across about 232 px of panel, which is
0.028 m/s per pixel, while the readout is formatted to two decimals. The
control displayed hundredths it could not physically reach — one pixel of drag
jumps roughly three of them. Setting a specific power was guesswork.

Measured on an empty table, using total cue-ball path length (net displacement
is meaningless once the ball starts rebounding off cushions, which it does):
0.01 m/s is worth 48 mm of travel at power 1.0, 24 mm at 1.5, 13 mm at 2.0. A
ball is 50.8 mm. At break speed it falls to 5 mm, which is why a coarse step
earns its place alongside the fine one.

A row of four buttons now sits under the slider: -0.1, -0.01, +0.01, +0.1. Four
across in a single row rather than the aim group's two stacked rows, because at
the minimum window height the Shot tab had 33 px of headroom and a second row
would have had to be paid for by shrinking the aim dial and the spin pad. The
layout was verified by instrumenting the real panel builder and reading the
widget rectangles: 15 widgets ending at 515 px became 19 ending at 540, against
a 548 px window. Eight pixels clear.

Each press snaps the result to the 0.01 grid, and the order is deliberate. The
delta is applied first and the result snapped second. Snapping first would mean
the opening press off a dragged value merely moved it onto the grid — 1.8472
would become 1.85, displaying "1.85" both before and after, and the button
would look broken. Applying first guarantees the readout always moves by
exactly one step.

Snapping is the part that answers the actual complaint. Without it a nudged
power is precise but never round, so it can be adjusted finely and still never
be repeated. With it, the displayed number is the true number, and since the
human shot path adds no noise — `do_shoot()` passes power straight to
`strike()`, unlike the AI which perturbs it — a power you can write down is a
power you can play again.

Selftest 61 covers the pure core: that a step lands on the grid, that repeated
steps do not drift off it, and that the buttons clamp to the same range the
slider spans. It failed on its first run against a wrong expectation of 1.85.
The code was right and the test was wrong; both the expectation and a docstring
describing the inferior snap-first order were corrected, and the episode is
recorded in the assertion's own comment.

## r28 — a whole frame, driven through the rules engine

The validation chain gained the test it was missing. Every assertion before
this one checks a single function in isolation: given these inputs, does it
return the right answer. A frame is not a function, it is a state machine, and
its bugs live in the ordering — in what the previous shot left behind. Nothing
tested shot N+1 against the state shot N produced, which is precisely why all
five bugs that reached the table got through: turn handover, spin reset, cue
repositioning, sandbox ball-in-hand, and the potted-ball chamber.

Selftest 60 plays a real frame, eight shots long — a dry break, an open-table
pot that assigns the suits, a continuation, a miss that hands the table over, a
wrong-ball foul, the free shot and second visit that foul buys, the last ball
of a suit, and the black — and asserts eleven named invariants after every
shot.

The shots are synthesised rather than played out in physics. That turns out to
be cheap: the rules layer reads exactly four things from the simulation, so a
frame can be driven by setting three fields and removing balls, with no physics
step at all. It stays deterministic, it runs in well under a second, and it
does not inherit the float sensitivity that makes a seeded `--aigame` score a
per-machine check. The cost is stated plainly in the source: it tests the rules
against the events the engine is *believed* to emit, and cannot catch the
physics emitting something else.

Two choices are worth recording. It asserts named invariants rather than
freezing a golden trace — a golden catches more but rewrites a large literal on
every deliberate change and freezes in whatever was wrong when it was captured,
which is the trap selftest 22 fell into at r16. And the full per-shot trace
prints only on failure, so a break diagnoses itself: with the r23 handover bug
reintroduced, the trace names shot 7 and shows the turn flipping to the wrong
player, which is the whole diagnosis in one line.

It was also mutation-tested before shipping. Five historical bugs were
reintroduced one at a time and each was confirmed caught, on the principle that
a test which has never failed has not been shown to work.

No game code changed. `--snap` is byte-identical and the seeded `--aigame`
score is unmoved, both of which are the point.

## r27 — the potted-ball chamber clears when the table does

Emptying the table now empties the chamber. In sandbox, re-racking (`T`),
resetting (`R`) or clearing (`C`) rebuilt the table but left the *previous*
frame's balls sitting in the glass, so the chamber quietly accumulated across
frames until it bore no relation to what was actually missing from the table.

The cause is a promise nothing kept. `potted_all` — the game-scoped pot
history added at r22, which the chamber reads — carries a comment saying it is
"never cleared by `strike()`; only a rebuild/new rack resets it." No code ever
did that second part. It went unseen because the game modes are unaffected:
re-racking there builds an entirely new simulation, so the chamber is new too.
Sandbox is the only path that reuses one, and sandbox is exactly where the
game is mainly played.

A new `reset_potted_history()` empties both pot records, called from
`clear_objects()` (which covers re-rack, sandbox clear, the custom-mode clear
button and layout load in one place) and from `rebuild()` — but only when
there are no ball positions to carry over. That condition is the whole care of
the fix: a rebuild *with* positions is a live-slider rebuild, which is what the
ball-radius, cushion-elasticity and rolling-friction keys do, and the frame in
progress survives those. So must its chamber. An over-broad version of this fix
would wipe the chamber every time you nudged the ball size mid-frame, and the
new assertion pins that case specifically.

Also added, unrelated to the above: an assertion guarding the r26 fix. It holds
STEADY's attempt threshold above `POT_FLOOR` as an *invariant* rather than
checking it equals 0.24, because the number likely to move is the floor — its
own comment invites re-deriving it — and if the floor ever rises past the
threshold, r26's bug returns with nothing to catch it.

Found by playing, not by the validation chain. That makes five.

## r26 — STEADY's attempt threshold moved above the distance floor

STEADY (the cautious AI personality) now actually plays cautiously again at
long range. Follow-on from r25: fixing `pot_estimate()`'s distance floor left
both SHARK's (0.10) and STEADY's (0.18) "confident enough to attempt"
threshold sitting BELOW `POT_FLOOR` (0.19) — so any geometrically valid
long or thin shot read as exactly 0.19 and cleared both thresholds
identically, regardless of how different those numbers were meant to be.

`floor_threshold_audit.py`, a new tool, watched 50 real headless AI-vs-AI
games and measured the actual size of this: 30.6% of ALL shots were pots
sitting exactly on the floor, and 88.7% of those would have been a safety
instead if the floor read its old, collapsed value. Not a rare corner case —
roughly one shot in three. Mechanically, `_search()` takes the best pot that
clears `threshold` outright and only falls to a safety when NOTHING clears
it, so once `POT_FLOOR` sits above a personality's threshold, that threshold
stops being able to reject anything.

SHARK's threshold is left at 0.10 — an aggressive personality attempting a
genuine ~19% shot is in-character. STEADY's moves to 0.24, clear of the
floor, restoring its ability to prefer a safety over a bare-floor pot. Re-
running the audit confirms it: STEADY now shows 0% floored pots (its
threshold correctly rejects them) and its safety rate rose from a blended
~9% to 41.8%. SHARK is essentially unchanged (34.5% floored, same as before).

This is a personality-tuning change, not a physics or geometry fix —
`POT_FLOOR` itself is untouched and still measured correct.

## r25 — AI distance calibration

The AI no longer treats long or thin pots as nearly hopeless. A dead-straight
shot from about two-thirds of a table length was rated at roughly 9% when it
actually drops closer to 19-20% of the time — the AI's shot-selection estimate
was declining a lot of makeable long shots, per Known Issues #2.

`pot_estimate()`'s distance handling had two problems, only one of which
turned out to matter. The r16 lever-arm term, which narrows the pocket's
angular tolerance as cue-throw distance grows, is sound physics but had no
floor, so it kept shrinking the predicted pot chance toward true zero the
longer and thinner a shot got. On top of that sat a second, flat
`exp(-t_cue / 10.0)` knockdown with no stated physical basis — the one Known
Issues named as "derived from first principles and hoped for." Measuring
showed the flat term was a minor contributor (an 8-10% reduction at 1 m); the
lever-arm term's missing floor was the real cause.

The fix is `distance_calibration_sweep.py`, a new headless tool that fires
real, physically simulated shots — the AI's own aim-jitter and power model,
not a hand-picked stand-in — across a grid of cue-to-object distance and cut
angle, and compares the measured pot rate against `pot_estimate()`'s
prediction with a Wilson interval on each cell (300 trials/cell). It found
that from about 0.9 m out, measured pot rate goes flat at ~19% (7 cells,
mean 0.192, s.d. 0.016) regardless of exactly how bad the shot gets within
that range, while the old prediction kept falling toward zero. `POT_FLOOR =
0.19` now clamps the prediction to that measured floor via `max(p_aim,
POT_FLOOR)` — a hard floor rather than a blend, deliberately, so it only
bites once the aim-error term has already collapsed below it and leaves the
model's short/mid-range behaviour untouched. The flat decay term is removed
outright rather than retuned.

This is the fix Known Issues #2 called for and is exactly the discipline it
insisted on: fitted against the Monte Carlo rig, not derived and hoped for —
the same mistake that made the term over-harsh the first time. It also
surfaced two new open threads (Known Issues #2 and #3): the floor sits above
both AI personalities' attempt threshold, so a floored shot always clears it
now, and the floor itself is validated at only one pocket/distance
combination.

## r24 — custom-mode jaws placement

You can now set a ball right on the lip of any pocket in custom mode — a hanger
ready to pot — which the placement rule previously walled off.

The old rule treated the table as a plain rectangle and kept every ball a full
ball-radius inside the rails. That is correct along a cushion, but a pocket
mouth has no cushion, so the rectangle blocked the one spot you most want when
setting a trick shot up. Placement is now tested against the real tangent-true
cushion nose: a ball is legal if its centre sits inside the cushion loop and at
least a ball-radius clear of every cushion edge. That single rule handles the
straight rails and the pocket mouths together, with no special cases — which is
what an earlier "exempt the pocket mouths" attempt got wrong (it leaked along
the side rails and was reverted). Balls still cannot be embedded in a rail, nor
set where the pocket would instantly swallow them.

This is the fix flagged as pending in the r22 notes and Known Issues #1.

## r23 — single-player gameplay fixes

Four bugs, all found by actually playing the game rather than by the test
suite. That's the headline: the validation chain (compile, self-test, batch,
smoke, screenshot) caught none of them, because every one lived in the
gap between a rule and the thing that rule was supposed to control.

- **Potting your last colour no longer hands the table back.** Clearing your
  colours and going on to the black was being scored as a foul. The rules were
  asking "what was this player allowed to hit?" *after* the shot's potted balls
  had already been taken off the table — so potting your final colour made it
  look as though you should have been on the black all along, and your own
  perfectly legal shot was judged a wrong-ball foul.
- **Spin now resets between shots.** Choosing bottom (draw) once applied it to
  every subsequent shot, and the spin pad wouldn't de-select. The shot was
  reading the spin correctly but never clearing it afterwards.
- **The cue ball can be repositioned after a scratch and on the break.** The
  simulation was putting the white straight back on the baulk line the instant
  it dropped — behaviour left over from before the rules layer existed — so you
  were "placing" a ball that had already been placed for you. Potting the white
  now simply removes it and leaves the placement to you. A related fix: ball in
  hand is now granted after *any* foul, not only a scratch, per the rules.
- **Sandbox play gets ball in hand too.** People play solo on pool tables, so
  sandbox mode now lets you place the white at the start of a rack and whenever
  you pot it — it previously had no concept of ball in hand at all.

Also fixed: the baulk highlight (the shaded area showing where placement is
legal) was checking a player's *name* where it should have checked whether that
player was human, so it had never once appeared in a game against the AI.

## r22 — single-player polish

- The game now starts **full-screen** instead of in a small window.
- The **potted-ball chamber** now stacks every ball potted during a game, in
  order, so you can read back the whole frame — previously it only showed the
  most recent shot.
- Trimmed an over-cautious margin around the pockets in custom-mode placement
  (full jaws placement completed later, at r24).

## r19–r21 — AI study tools and calibration

- Added a **per-shot study log** (JSONL) and a calibration report, so the AI's
  shot-quality estimates can be measured against what actually happens.
- Fixed the AI's obstruction check to account for aim variation, and to use the
  true clearance a ball needs.
- Corrected the calibration measurement to exclude "free shots," where the AI
  may legally strike any ball first.
- A long investigation into the AI's shot-quality estimate concluded that the
  estimate itself is sound; remaining differences come from shot selection, not
  from the physics. (One over-harsh distance term is noted for a future pass.)

## r18 — fairer AI matchups

- The two AI personalities (SHARK and STEADY) were re-tuned so they differ only
  in *strategy*, not in raw aiming skill — making an AI-vs-AI result a genuine
  test of tactics rather than of who aims straighter.

## r17 — performance

- Made the AI-vs-AI games roughly four times faster (pocket detection moved into
  the physics engine's own collision handling; games can run in parallel),
  every step verified to leave behaviour unchanged.

## r16 — AI shot-quality fix

- Fixed a significant flaw in how the AI judged the difficulty of a shot, which
  had been making it wildly over-confident and causing it to attempt almost
  everything.

## r15 — study output

- Added seeded, reproducible AI games with a per-shot log and confidence
  intervals — the foundation that made all the later measurement work possible.

## r13–r14 — ball in hand and the aim overlay

- **Ball in hand:** the cue ball can be placed within the baulk area on the
  break and after a foul (the modern UK rule; the "D" is not used).
- **Aim overlay:** a richer aiming display — layered aim lines, a translucent
  ghost ball, a pocket glow when a pot is on, and a predicted cue-ball
  resting position. The aim line's colour shows the pot chance (red → green).

## r9–r12 — rules, HUD, custom mode, chamber

- A full **rules layer**: fouls (wrong ball first, no contact, no cushion,
  scratch), free shots, two visits after a foul, and evaluated safety play.
- **Fine aiming controls** — angle to a hundredth of a degree, a spin pad with
  nudge buttons.
- **Custom mode** — clear the table and place balls freely, with four save/load
  layout slots.
- **Potted-ball chamber** — a glass-fronted readout of what's been potted, in
  order (the cue ball is excluded, since a scratched cue returns to play).

## r7–r8 — graphics and sound

- **Table graphics:** cloth shading with an overhead-light falloff, wood-grain
  rails, and cushions correctly coloured as felt-green cloth.
- **Sound:** ball contact reworked from scratch into a solid polymer "knock" —
  synthesised, like everything else, with no audio files.

## R6 — foundations

- Integrated the tangent-true cushion geometry, finalised the WEPF table spec,
  and settled on the classic (software) renderer and the tabbed control panel.

---

*Older internal detail lives in the project's development notes.*
