# HANDOFF — HUSTLER (UK Pool Physics Sandbox)

**Status:** r47 — playable, validated, no known blocking bugs.

**Files:** `hustler.py` (~9,220 lines) **+ `cushion_path.py`** (~515 lines,
tangent-true cushion-nose geometry, imported as `cushion_geo`) — one project,
two files. Python 3.12, pygame 2.6.1 + pymunk 7.3.0. **No other dependencies**
— no numpy, no asset files of any kind.

**Install:** `pip install pygame==2.6.1 pymunk==7.3.0` (add
`--break-system-packages` on system Python, or use a venv).

**Run note:** `cushion_path.py` must sit alongside `hustler.py`. Its own
standalone selftest (`python3 cushion_path.py`) validates the reference spec and
stays green independently. **Table geometry is FINAL** as of R6.1 — no
construction drawing is forthcoming; the tangent-true loop is the authoritative
source of truth.

## Validation snapshot at r47

| Check | Result |
|---|---|
| `py_compile` (both files) | OK |
| `--selftest` | ALL PASS — 100 assertions |
| `--batch 30` | 0 containment escapes |
| `--smoke` | 90 frames OK |
| `--snap` | md5 `62c87ddb6d1f0ee36f36a71a5000cd5f`, byte-identical to the R6.1 baseline |
| `--aigame 12 --seed 4200` | SHARK 9–3 STEADY (nix5), all games completed cleanly |
| `cushion_path.py` standalone | SELFTEST OK — 36 primitives |
| GitHub Actions `Validate` | passing (Python 3.12 and 3.13) |

## What r42 changed (as built)

**The four physics constants left the status strip for the Table tab.** They
sit under the sliders that move them, as `SpecBlock`, and each is drawn against
the right kind of reference: a hard tick for the two WEPF Annexe A equipment
values (ball 50.8mm/116g, cue 47.6mm/94g), a band for the two measured
literature ranges (cushion pair restitution 0.6–0.9, roll 0.049–0.147). The
cue-ball toggle (K) makes the casual 2" ball read off spec immediately. Object
and cue ball are drawn side by side at true relative scale with the tip circle
at `TIP_FRAC`, which is now a module-level constant rather than a second
literal inside `SpinPad`.

**The one trap in that block:** the measured 0.6–0.9 cushion range is a
**pair** range, while `CFG["CUSHION_ELASTICITY"]` is the rail component 0.77.
The row plots `BALL_ELASTICITY * CUSHION_ELASTICITY` ≈ 0.75. Assertion 90 pins
it, because plotting the raw 0.77 against a pair band would look entirely
plausible on screen.

**The strip's leading is computed, not chosen** — `strip_leading()` shares out
spare height when there are few lines and tightens to the old 1px floor when a
game fills the strip. The call indicator's clamp now scales.

**Measured before the change** (these are why the constants moved, and they are
worth not rediscovering):

| | before r42 | after r42 |
|---|---|---|
| game + ball in hand, lines wanted vs drawn | 9 vs 7 — two clipped silently | 6 vs 6 — nothing clipped |
| call row vs last line, 1.5x / 1.25x / 1.0x | overlap 4 / 12 / 12 px | gap 4 / **−2** / 1 px |
| call row past the strip rule | spills at every scale | inside the strip at every scale |
| solo run leading at 1.5x | 1px | 9px |

The one residual is in that table: a full game at 1.25x still touches the call
row by 2px, down from 12. It is the over-subscribed case, and assertion 91
deliberately promises a clean row only when the lines leave room for one.

**Headroom after the change** (SpecBlock bottom / window height): 764/1350,
634/1080, 509/768, 509/548. The Shot tab remains the binding constraint at 25px
(1920x1080) and 27px (1144x548), unchanged by this pass.

## What r43 changed (as built)

**Two denominators, because there is no single honest one.** `attempt_population()`
splits the log into `confirmed` (a target pocket resolved), `unresolved_miss`
(potted nothing and the line pointed at no pocket), `unresolved_other` (potted
something but no pocket resolved) and `notrail` (too old). `--stats` prints the
pot rate over `confirmed` and over `confirmed + unresolved_miss`, and the gap
between them is the uncertainty. Measured on 244 rows: 56.2% against 50.9%.

**Every rate carries its 95% Wilson interval** via `rate_ci()` and `band_line()`.
`wilson_interval()` had been unused by the player-facing report since r15.

**The spin table is labelled confounded, not corrected.** It measures which
shots get which spin, not what spin does. Fixing it needs stratification by cut
angle and distance within each spin family; at ~200 rows that leaves cells of
five. r18's lesson was that a confound needs a controlled comparison, not a
caveat — so the caveat is explicitly a placeholder for one.

**A scratch section that says almost nothing on purpose:** 7 in 244 = 2.9%
[1.4-5.8], and no split by power, angle or spin at that count.

**The provenance trap, worth not rediscovering:** `observed` rows are pots by
construction (the drop pocket only exists when the ball dropped) and `inferred`
rows are misses by construction. The counts are a census of how the target was
found, never a comparison. The report now says so in the output itself.

**Still open after r43:** `foul` and `event` are null on all 244 rows including
the newest schema-6 ones, so the writer never populates them on the human path.
Flagged, not fixed — it was deliberately left out of r43's scope.

## What r44 changed (as built)

**`shot_is_foul(cue_potted, first_contact)` is the single foul predicate.**
`solo_apply_shot` (which charges the clock) and `foul_summary` (which counts
afterwards) both route through it. Assertion 94 checks the agreement against
the run state's own accounting rather than a second hand-written expectation,
because a hand-written one would just be the duplication again.

**`foul_summary(rows, penalty_s, mode)`** derives fouls from `potted` and
`first_contact` — fields the log has carried since r15 — so it reports the whole
history. Solo is reported separately because solo is the only mode where a foul
is charged. Measured at r44: 10/244 overall (7 scratch, 3 no contact), 7/140 in
solo, costing 70s.

**r43's `scratch_summary()` was deleted**, not left unused. The fouls block
carries the scratch count as one of its two causes.

**The schema's `foul` field is still not written and that is now documented as
KNOWN_ISSUES #5,** with the ordering diagnosis: the human log write sits above
the game block, so `on_rest` has not run and the foul is undecided at write
time. Also recorded there: in a game mode the `event` field would be *stale*
rather than absent — read from the code, never tested against a real row,
because the log contains no game-mode rows.

## What r45 changed (as built)

**Human rows carry `session` and `t`.** `session` is fixed once at the top of
`run_gui` (one run of the program = one session, NOT one day); `t` is the
shot's UTC clock via `stamp_utc()`. Schema 7. Written in `log_human_shot` and
nowhere else.

**`sessions(rows, limit)`** groups them oldest-first with a single `None` bucket
for everything predating r45; **`session_span_s(rows)`** returns the sitting's
duration, or None below two stamped rows. `--stats` gains a BY SESSION block
(last ten), which stays hidden while every row is in the unknown bucket.

**Assertion 96 is the important one.** The study log must stay byte-identical
for a fixed seed — that md5 diff is how r17 proved three optimisations safe. It
checks `make_shot_record` carries neither field and that exactly one site in
the file assigns them. Verified empirically as well: two fixed-seed runs give
identical bytes, and the only field differing from the pre-r45 baseline is
`schema` (6 → 7).

**Not done, deliberately:** no backfill of the 377 existing rows from commit
boundaries, and no trend line. Both are written up in the changelog with the
reasoning.

**Assertion 39 relaxed** from `STUDY_SCHEMA == 6` to `>= 6`. `break_shot()` was
always keyed on field presence, so only the assertion pinned the number, and
assertion 47 already used `>=`.

## What r46 changed (as built)

**`grannie(potted_colours, winner_colour, loser_colour, clean_black)`** — pure,
no new state. Judged on the COLOUR that never went down, not on who potted it,
which is why no per-player attribution exists anywhere. The winner accidentally
potting a loser's ball kills it; a win handed over by a foul on the black is
not a clearance and cannot be one. Assertion 98.

**`draw_grannie()`** lives inside `run_gui` (pygame is not imported at module
scope) and is called from the existing black-pot finale, inside its `not smoke`
gate — the `--snap` baseline stays `62c87ddb…`. Drawn from primitives per the
no-asset rule. Deliberately rough for now; the Maker's brief was that she just
has to be there.

**Shift+G previews the Grannie** by building the same `finale` dict the real
path builds (`cup` None, `grannie` True), so preview and reality cannot drift.
The Shift arm must stay ABOVE the plain `K_g` arm or the aim-overlay toggle
swallows it.

**`clear_objects()` now prunes `self.colours`.** It never did, so the map grew
by a rack each time the table was cleared (4 → 19 → 34 against 16 live balls).
Harmless only because ids are never reused and `remaining()` walks `balls`.
Assertion 99 pins the invariant, because league mode racks at volume.

**Not in r46:** the permanent record of a Grannie. That needs profiles, which
are r47.

## What r47 changed (as built)

**The status readout moved to the band above the table**, and `STATUS_STRIP_H`
collapses to 0 when it does. Pure cores: `band_capacity(band_h, font_h, lead,
pad)` and `status_goes_in_band(...)`. The band is computed in `refit()` from
the FITTED height (`(win_h - fit_H1) // 2`) because it only exists as the
leftover of the table fit; `STATUS_STRIP_H` is then decided once the panel font
is known, and `build_panel_widgets()` — already re-run on resize — lays every
tab out from the new origin.

**Decided by geometry, never by the live text.** A content-driven choice would
relayout the panel whenever an event line appeared. Assertion 100.

**Measured:** worst-case status packs 6 panel lines into 2 band lines at
2160x1350, 1 at 1920x1080, 2 at 1024x768, and the band is 0px at 1144x548 where
the panel strip carries on unchanged. Shot-tab headroom at 1920x1080 goes
25px -> 166px.

**Side effect, by design:** at 1024x768 the reclaimed space lets r30.2's
`spin_group_radius()` fit a second strike-point picker on the Shot tab, which
did not fit at r46. Five extra widgets, and the reason the tab now ends 8px
from the window foot.

**Fixed on the way:** `call_led()` is computed once above the branch so both
homes draw it; and r46's grannie block had reused the name `_lc` for the
loser's colour, clashing with the call indicator's colour — renamed `_loc`.

**Scope note:** "readouts" here means the status strip. Slider value suffixes
and the r42 constants block stay with their controls — a slider without its
value is unusable, and the constants block was deliberately placed beside the
sliders that change it (r42 Fork 1B).

**The chain also runs in CI** on every push to `main`, at
`.github/workflows/validate.yml`, across a 3.12/3.13 matrix. Since r27 it
enforces the `--snap` md5 as well: the hash lives in one place, as a
workflow-level `env: SNAP_MD5`, and the step fails if the render moves. If you
are *deliberately* re-capturing the baseline, change that hash in the same
commit and say so — being forced to do it visibly is the point. Worth knowing
that the baseline has now been confirmed identical on three independent
platforms, so a mismatch means a real render change, not a machine difference.
The `lint` job (isort, pyflakes) is **blocking**. As of r31.1 nothing in this
workflow is advisory — no step anywhere carries `continue-on-error`. That
matters more than it sounds: isort had been genuinely failing for months
behind `continue-on-error` and nobody noticed, precisely because the job was
known to be ignorable. A check that cannot fail trains you to stop reading it,
and then it hides the one that could. black was removed rather than fixed —
its diff here runs to roughly a third of `hustler.py`, including 251 aligned
inline comments, so enforcing it would bury every future change under a
reformat. pyflakes replaced it and earns the slot: it is what found the r31
`finale` bug, by reporting a local assigned and never used, which is the
signature of a missing `nonlocal`.

Three notes on reading those. `--batch` uses an **unseeded** RNG, so pot and
scratch counts vary run to run — the invariant is `containment escapes: 0`, not
the counts. Seeded AI games are extremely sensitive to behavioural change,
which makes `--aigame N --seed S` an excellent regression check: if a refactor
was meant to preserve behaviour, the result should be identical. But that
sensitivity cuts both ways — the physics is float-heavy and the result is
**platform-sensitive**, so a recorded score is a check against *the same
machine*, not an absolute. The r25 and r26 figures recorded in the roadmap
(SHARK 4–8 and 5–7) did not reproduce elsewhere on identical code. Note the
machine when you record one; re-baseline rather than debug if you move.

## What changed since this document was last fully rewritten

**This handoff was written at R6.10 and its narrative sections (§5 release
history, §6 findings, §7 the AI, §8 rules coverage) stop there.** Everything in
them remains accurate as history and the engine facts in §3 are still current
and still worth reading — but roughly sixteen revisions of work happened
afterwards. That later work is documented in:

- [CHANGELOG.md](CHANGELOG.md) — plain-language history through r34
- [KNOWN_ISSUES.md](KNOWN_ISSUES.md) — the three open threads, each with its diagnosis
- [ROADMAP.md](ROADMAP.md) — what's under discussion and what it depends on
- [CONTRIBUTING.md](CONTRIBUTING.md) — workflow, standards, and the traps that have cost real time

**The short version of r15–r29:** a JSONL per-shot study log and seeded
reproducible games; a major fix to the AI's shot-quality estimate (it had been
wildly over-confident); a ~3.8× performance pass, every step proved
behaviour-preserving by diffing study output; the two AI personalities re-tuned
so they differ only in strategy, not aiming skill; a long calibration
investigation that concluded the estimator is sound and the gap is a
shot-selection artefact; full-screen startup and a game-scoped potted-ball
chamber; four single-player gameplay fixes at r23; and custom-mode jaws
placement at r24 (containment now tests the real cushion-nose polyline instead
of a rectangle, so a ball can be set on a pocket lip).

**r25–r27** are all one thread plus a tail. r25 fixed the AI's distance
calibration: `pot_estimate()`'s distance term had no floor and decayed toward
zero, rating a real ~19%-to-drop long shot at under 2%, so the AI declined
makeable long pots. `POT_FLOOR = 0.19` clamps it to a rate *measured* by firing
300 real simulated shots per cell across a distance/cut grid — fitted against
the rig, not derived and hoped for, which is the mistake that made the term
over-harsh in the first place. r26 cleaned up after it: the new floor sat
*above* both AI personalities' attempt thresholds, so every floored shot
cleared both identically and `threshold` lost its power to reject anything — a
measured 30.6% of all AI shots, of which 88.7% would otherwise have been
safeties. STEADY's threshold moved to 0.24, clear of the floor; SHARK's stayed
at 0.10, since attempting a genuine 19% shot is in character for it. r27 fixed
a sandbox bug (the potted-ball chamber never cleared when the table was
emptied) and added the assertion r26 should have shipped with, guarding the
threshold-above-floor invariant.

**r28–r29** turn outward. r28 closed the tooling gap the r23 lesson below has
been pointing at since it was written: selftest 60 drives a whole frame through
the rules engine rather than testing one function at a time. r29 is the first
change in a while aimed squarely at the single-player game — fine adjustment
for shot power, which had none, on a slider whose pixel resolution was three
times coarser than its own two-decimal readout. Both are described in the
CHANGELOG; the second blind spot r29 exposed, that the HUD panel cannot be
rendered headlessly at all, is written up after the r23 lesson.

**r30** finishes what r29 started. Aim had fine adjustment from r10 and power
from r29; spin was the last shot parameter still set by eye, with the same
pixel-versus-readout mismatch and no snapping at all. It now snaps to the same
0.01 grid, and the contact point is set on a cue-ball picker with its own tab —
drawn at true tip scale, with the rim meaning maximum usable spin rather than
pretending to a miscue limit the engine does not model. Two follow-ups, r30.1
and r30.2, came straight out of playing it: a button overlap the layout probe
could not see, a piece of shading that accidentally signalled a distinction
that does not exist, and a second copy of the picker on the Shot tab wherever
the window is tall enough to hold it.

**The most important lesson of the whole period** is from r23: all four of those
gameplay bugs — turn handover, spin reset, cue placement, sandbox ball-in-hand —
passed the *entire* validation chain and were found by sitting down and playing.
So did r27's chamber bug. That is five.
The suite is strong on pure functions and physics invariants and blind to
whether a turn passes to the right player. **r28 answers that tally**: selftest
60 drives a whole eight-shot frame through the rules engine and asserts eleven
named invariants covering turn, visit, spin and placement state after every
shot. It is the first test in the suite that checks shot N+1 against the state
shot N left behind, which is where all five of those bugs lived. Add the
assertion, run the chain, **and then play the game** — r28 narrows the gap, it
does not close it.

There is a second blind spot the chain cannot cover, and r29 ran straight into
it. `--snap` and `--smoke` render the bare scene; `build_panel_widgets()` is
only called in the non-smoke branch, so **the HUD panel is never built or drawn
headlessly** and no automated capture can show it. Panel layout can still be
checked without eyes, but numerically rather than visually: copy the tree
aside, inject a `print` and a `raise SystemExit(0)` immediately after
`panel_widgets["Shot"] = shot`, run `run_gui(smoke=False)` under
`SDL_VIDEODRIVER=dummy`, and read the widget rectangles against `win_h`. That
is how r29's four-button row was confirmed to fit — 19 widgets ending at 540 px
against a 548 px minimum window.

**r30 showed that is not enough on its own.** A probe reading only the topmost
and bottommost widget reports the *extent* of a tab, and an overlap does not
change a maximum. The Shoot button was moved up by a wrong constant and sat
10 px inside the aim row, and the probe reported a perfectly sensible bottom
edge the whole time. Compare every pair of widget rectangles for intersection
as well; it is four lines and it catches the class. Run it at more than one
window size, too — layout is in absolute pixels and does not scale with window
height, so a tab that fits a desktop-sized borderless window may not fit the
1144×548 the F11 toggle restores.

Anything about how the panel *looks*, as opposed to where it sits, still needs
a human at the keyboard — and r30 proved that twice over, since both of its
follow-up fixes were found by playing rather than by measuring.

---

## 1. What this project is

A UK blackball pool physics sandbox grown into a playable game with a utility AI,
built to answer the original question: *how do angles, spin, and the break actually
work?* The long-term destination is AI-vs-AI spectating with emergent behaviour.

## 2. Working agreement (non-negotiable, carried from AISpecOps/HexWars)

- Decisions brief with genuine forks → explicit sign-off → build → validate.
- Validation chain, every release, even graphics-only changes:
  `py_compile` → `--selftest` → `--batch N` → `--smoke` (+ `--snap` for screenshots).
- One selftest assertion per feature, testing the PURE CORE (values in, values
  out) rather than the pygame wrapper around it. Currently 100 assertions, all
  physics/logic/UI and entirely dependency-free.
- Report the ACTUAL NUMBERS from the chain, not "passed" — the numbers are what
  let the next person spot a drift nobody noticed.
- UK spelling throughout. Emergent AI behaviour protected — parameters and scores,
  never scripts. Transparent bug ownership: failures are logged in this doc.

## 3. Architecture (decision 1C — hybrid)

- **Simulation:** pymunk in REAL UNITS (metres/kg/seconds). Rendering scales by
  `PX_PER_M` at draw time only.
- **Geometry layer:** pure maths, no pymunk import above its section — ghost ball,
  ray/corridor solves, pot assessment, one-bounce prediction. Directly unit-tested.
- **Rules layer:** `Game` class — rules-lite blackball state machine.
- **AI layer:** `PoolAI` — geometric utility AI (see §7).
- **GUI:** three modes on `M`: SANDBOX / YOU vs AI / AI vs AI spectator. Single
  renderer (classic pygame) — GL was tried (R6.2-R6.9) and removed (R6.10).
- **Headless modes:** `--selftest`, `--batch N`, `--breaks N` (break analyser),
  `--aigame N` (AI tournaments, `--jsonl`/`--seed` for study output), `--smoke`,
  `--snap FILE`, `--sound-probe [DIR]`.
- **Rules/physics separation is load-bearing.** `Sim` knows nothing about
  `Game`. Where the rules need to change physics behaviour (e.g. whether a
  potted cue ball is auto-respotted), it is done with an explicit flag set by
  whoever CONSTRUCTS the sim — never by the physics layer reading the rules.

### Critical engine facts (hard-won, do not rediscover)

- **THE PANEL SCALES; EVERY DIMENSION GOES THROUGH `U()`.** `panel_scale(win_h)`
  gives 1.0 / 1.25 / 1.5 by window height. Any new panel dimension MUST be
  written as `U(n)` with `n` at the 1.0 size, or it will be right on one screen
  and wrong on another. Four button heights were missed on the first pass
  because their rects begin with an expression rather than a bare `px`.
- **PANEL PIXELS COME OUT OF THE TABLE.** The scene is width-limited on this
  layout: PANEL_W 260 -> 520 costs 14% of the playing area at 2160 wide. The
  1.5 cap is a deliberate trade signed off by the Maker, not a technical limit.
- **THE PROBE NOW CHECKS LABEL-FITS-BUTTON.** Overlap and extent checks cannot
  see text spilling out of a widget. Run the probe after ANY font or layout
  change, at 2160x1350 as well as the smaller sizes — the six overflows r41
  found appeared only at 1.5.

- **SIX TABS NOW: `["Shot", "Aim", "Spin", "Table", "Game", "Cust"]`.** Adding
  "Aim" at index 1 moved every label after it. Resolve tabs BY NAME, always;
  `panel_widgets` keys must match `TAB_LABELS` exactly or a click KErrors.
- **ALL THREE SHOT CONTROLS SNAP TO 0.01 AND SHARE ONE IDIOM**
  (`round(round(v/step)*step, 6)`): power r29, spin r30, aim r40. Aim is
  SNAP-THEN-WRAP for the same reason spin is snap-then-clamp — snapping 359.999
  yields 360.00, which is not a legal angle.
- **WHEN SIZING A PANEL GROUP, COUNT WHAT SITS BELOW IT TOO.** r40's first
  attempt reserved only the group's own height and ran the Shot tab 19px off a
  548-tall window, having forgotten the separation gap and the Shoot button.
  The `extra` term in `spin_group_radius()` must cover everything that is not
  the diameter, with headroom left spare.

- **A LOG READER THAT CANNOT KNOW MUST RETURN None, NOT A DEFAULT.**
  `break_shot()` is the pattern: rows predating the flag report None so they are
  EXCLUDED from a break sample, never counted as non-breaks. The same discipline
  as r36's `departure_pocket()` refusing rather than picking a best-aligned
  pocket. Defaulting an unknowable to False is how a table becomes partly
  invented while looking authoritative. Key such readers on the PRESENCE OF THE
  FIELD, not on the schema number — the schema is stamped by the writer, so a
  record that has not been written carries no version.

- **THE SHOT LOG IS TRACKED, AND LIVES IN THE REPO (r38).** `hustler_shots.jsonl`
  sits beside `hustler.py`, resolved by `shot_log_path()` from the script's own
  directory so a second clone logs to itself. `.gitignore` keeps `*.jsonl` and
  carries one negation for this file. **A working copy will show it modified
  after play — that is real data and is meant to be committed**, and it is the
  one exception to "anything modified is suspicious". A FRESH CLONE is still
  clean. Set `$HUSTLER_SHOT_LOG` to keep an experiment out of the tracked file.

- **THE STATUS STRIP CLIPS SILENTLY.** `STATUS_STRIP_H` is 113px and the draw
  loop breaks the moment a line will not fit, so an overrun reads as a line
  that was never written rather than as a bug. At a 15px line height that is
  SEVEN lines total, four of which the physics fields already take. The
  widget-overlap probe does NOT cover this — it checks the tabs, and the strip
  is outside the tab system. Anything added here must earn its line by taking
  one away; `solo_status_lines()` caps itself at two and self-test 85 pins it.
  The font is `SysFont("consolas,menlo,monospace", 14)` with fallbacks, so line
  height is not identical on every machine: leave headroom, do not just fit.

- **NEVER test a mode by its index.** `MODES` is `["SANDBOX", "YOU vs AI",
  "AI vs AI", "SOLO"]` and `mode_intents(mode_name, run_started)` answers the
  three questions a mode index used to stand in for: is the human shooting,
  may the table be edited, and what does the shot log call this. Before r37,
  eighteen sites tested `mode == 0` and that literal was answering all three —
  which worked only while SANDBOX was the sole Game-less mode. Self-test 84
  pins the full table, so a fifth mode fails the build until it is classified.
  Same defect as `custom_active()` testing `panel_tab == 3`, nine times over.
- **SOLO locks the table on the first STRIKE, not at rest.** `table_is_editable()`
  keys off the clock's start stamp, which is set in `do_shoot()`. Run state is
  advanced when the balls stop, so gating on `solo_run["started"]` would leave
  the table editable for the whole flight of the opening shot.

- **A missing target must be refused, not guessed.** `pot_assessment()` returns
  the best-aligned pocket and ALWAYS returns one, so using it to fill in what a
  player was aiming at converts every safety, cannon and roll-up into a failed
  pot. r36's `departure_pocket()` declines instead: the object ball's onward
  line must pass within `POCKET_AIM_TOL` (50mm, measured against 29 shots whose
  pocket was known) and a pocket behind the ball is rejected outright. Any
  future inference over player intent should copy this shape.
- **Observation outranks inference, always.** Where r35 recorded which pocket
  swallowed a ball, that is the answer and the line is not consulted. The two
  agreed on all 29 shots where both existed — which is a reason to trust the
  inference, not a reason to prefer it.

- **post_solve fires once per SUBSTEP, not once per contact.** pymunk calls
  the handler for as long as two bodies remain touching, and `step()` runs
  eight substeps a frame. One ordinary shot, measured: fifteen cue-cushion
  callbacks for what a player would call four rebounds, one contact firing
  eleven times by itself — a ball sitting in the jaws is touching several
  cushion primitives at once, each with its own arbiter. **Anything that
  counts, records or accumulates from a collision handler must de-duplicate,
  or it will be wrong by a large factor while looking entirely plausible.**
  `trail_append()` is the worked example (r35).
- **The drop pocket is read off the sensor, not the position.** Each pocket
  sensor shape carries its index in `Sim._pocket_of_shape`, and
  `_pending_pot_ids` is a map from ball id to pocket index. A nearest-capture-
  point lookup would be unambiguous (pockets are 924mm apart against a 35mm
  capture radius) but it is an inference standing next to an exact answer, and
  `pocket_axis` is the standing reminder of what that costs.
- **`potted_log` still means exactly what it always meant** — shot-scoped, read
  by the rules engine, wiped by `strike()`. r22 split `potted_all` off it for
  the game-scoped chamber; r35 added `drop_log` for destinations. Three
  narrow records rather than one wide one, because two features wanting one
  variable to mean two things is how the chamber bug happened.

- **pymunk 7 removed `add_collision_handler`** — use
  `space.on_collision(collision_type_a=, collision_type_b=, post_solve=fn)`.
- **`space.collision_slop` defaults to 0.1 space-units = 10 cm in metre units.**
  Must be set (we use 0.0002) or collisions are mush.
- pygame.draw writes raw RGBA without blending — translucent paint on a sprite
  punches through to the background when blitted. Pre-blend highlight colours.
- pygame.draw.arc uses maths-convention angles (0 = 3 o'clock, anticlockwise,
  0..π = top half on screen).
- **Spin is an IMPULSE AT CONTACT, never a force during travel.** `FOLLOW_KICK`
  (0.60) is applied once at cue→object-ball contact and `_live_follow` is then
  zeroed; `SIDE_KICK` (0.35) is applied at cue→cushion contact and `_live_side`
  is then decayed ×0.35 (it also decays per step while rolling). Between
  contacts the cue ball travels in a **straight line** — there is no swerve, no
  squirt, no masse anywhere in the engine. Consequence for any predicted-path
  or coaching overlay: it must not draw a curve, because the balls will not
  follow one. Side spin *does* change the cushion rebound, so a pure
  law-of-reflection prediction is wrong whenever side is loaded — but the
  formula is deterministic and three lines long, so a prediction can reproduce
  it exactly rather than approximate it.
- **`estimate_leave()` predicts against a RECTANGLE, not the real cushion.** It
  uses `ray_rect_exit()` / `reflect_off_rect()`, stops after ONE bounce, and
  rebounds at `LEAVE_CUSHION_E` (0.73). Adequate mid-table; increasingly wrong
  near the pockets, where the tangent-true nose diverges from the rectangle.
  It feeds the AI's utility, so changing it shifts shot selection — prove any
  change with a seeded `--aigame` diff rather than assuming.
- **There are TWO pot-difficulty models and they have drifted apart.**
  `pot_assessment(gb)` is human-facing (the aim overlay); `pot_estimate(cp, t,
  pc, cap_r, r_cue, r_obj, jitter)` is the AI's. Different signatures, different
  distance decay, different thinness term — and only the AI's takes `jitter`,
  which is correct, since a human aims via the HUD and is not randomly
  perturbed. Note that `pot_estimate`'s docstring calls itself the "single
  source of truth": that is scoped to the AI's own two uses, but reads broader
  than it is. Don't point one at the other without an explicit decision — this
  is why r16's over-harshness went unnoticed for so long, since no human path
  ever touches `pot_estimate`.
- **Sandbox has no shot-completed event.** `pending` is only ever set when a
  `Game` exists, so mode 0 — which is where the practice frames actually
  happen — never resolves a shot at all. r33's logging carries its own
  `shot_pending` flag for exactly this reason. Anything that needs to react to
  a human shot finishing must not assume `pending` will fire.
- **NO CHOICE OF SPIN CAN RESCUE A MISSED DIRECT POT.** Worth stating
  separately from the no-swerve fact above, because it is the load-bearing
  consequence for any "why did that miss / what would have worked" analysis.
  There is no contact throw, no squirt and no swerve: `FOLLOW_KICK` acts on the
  CUE ball after contact and `SIDE_KICK` acts on the CUE ball's rebound off a
  cushion. Side spin cannot move the object ball's line at all. So if a player
  reports that a particular spin "makes a pot work", the mechanism is either
  the cue ball's own path (a cushion-first line, or a scratch avoided), or it
  is a selection effect — and the shot log can tell those apart. Do not offer
  spin as a remedy for a missed pot.
- **The shot log records the table BEFORE the shot only.** There is no
  post-shot state: nothing records where the cue came to rest, what it
  contacted, or which pocket took a potted ball. "Why did the white go down"
  is therefore unanswerable from the current log, and logging the leave is the
  first item on the next session's list.
- **The shot log stores RAW POSITIONS, and angles are derived on read.**
  Every row carries the cue ball, the object ball and the whole table layout
  in metres at the moment of striking. `pocket_geometry()` turns those into
  distance, bearing and — the one that matters here — the angle the ball sat
  off the pocket's own mouth axis. Distance alone cannot tell a ball tight on
  the cushion from one in open baize at the same range, and on this table
  those are not the same shot: over four logged AI frames the pot rate ran
  59% within 10 degrees of the mouth and 5% beyond 30. Add derived scalars if
  they are convenient, but never at the cost of the positions.
- **Shot-log rows carry provenance, and it is not decoration.** Every record
  written from r32 says `source` (human or ai), `mode` (practice or
  tournament), `intent` (called or none) and `p_model` (which difficulty
  function produced `p_pred`). Rows that disagree on any of these MUST NOT be
  pooled. A human aims by HUD number with no applied jitter and the AI does
  not; in practice the player sets the balls up themselves, so a practice pot
  rate measures what they chose to rehearse; an un-nominated shot has no
  declared goal and is not a missed pot; and `pot_estimate` and
  `pot_assessment` are different scales that have drifted apart. Each of those
  is a population, and r19-r21 was one long lesson in what happens when you
  measure the wrong one.
- **The shot log is the source of truth; profiles store identity and results
  only.** Every statistic is derived on read. This is deliberate: when a
  statistic later turns out to have been computed wrongly — and r16 found
  exactly that, a 5x over-confident estimator — a function gets rewritten and
  re-run. Stored aggregates would have to be migrated or thrown away.
- **A reset inside a nested function needs `nonlocal`, or it resets nothing.**
  `run_gui` is one long closure and its handlers are nested functions, so
  `finale = None` inside `do_rack()` silently created a local and left the
  real `finale` untouched. This has now happened twice — r23's spin values
  were re-sent every shot for the same reason. Nothing in the validation
  chain can see it: the code is legal, runs without error, and does nothing.
  Selftest 72 (`closure_state_leaks`) guards the class by reading the
  compiled code objects — a leaked name sits in the nested function's
  `co_varnames` when it belongs in `co_freevars`. If you add a new piece of
  `run_gui` state that handlers reset, add its name to `RUN_GUI_STATE`.
- **The spin unit circle IS the miscue limit, and nothing else is.** No tip,
  miscue threshold, squirt or swerve is modelled anywhere — those words appear
  zero times in the source. `spin_pad_map()` divides a pixel offset by the
  picker's radius and clamps the magnitude to 1, and `follow`/`side` are
  abstract coefficients in [-1, 1] applied as impulses at contact. So the unit
  circle already means *maximum usable spin*, which is why r30's picker draws
  its rim as the circle and greys nothing: an outer band would assert a miscue
  radius this project has not measured. The dashed ring at 0.75 R is drawn as a
  real-cue note and no code reads it. Any future overlay must not assert one
  either.
- **Spin snaps to a 0.01 grid, and the order is snap-then-clamp** (r30,
  `snap_spin()`). Snapping a value already on the rim pushes it back out — a
  45° maximum is (0.7071, 0.7071), which snaps to (0.71, 0.71) with magnitude
  1.0041, i.e. more spin than the budget allows — so the clamp must come
  second. The deliberate consequence is that rim values sit exactly on the
  circle rather than on the grid.
- **`cushion_path.flatten(path, max_seg_deg=5.0)`** returns the tangent-true
  cushion as a vertex list. That's the starting point for anything needing real
  cushion geometry instead of the rectangle — it is what the custom-mode jaws
  placement fix was built on at r24, and what a cushion-accurate aim or coach
  overlay would need.
- **Line endings: fixed at r30.3, and a dirty clone now means something.**
  `.gitattributes` pins the repo to LF (`* text=auto eol=lf`), but
  `cushion_path.py` had been committed CRLF long before that attribute existed.
  Git normalises to LF when staging, so it compared the file against a blob
  that disagreed and reported it modified forever — a 514-line phantom diff
  with zero content change, in every clone, for many revisions. That is what
  `git add --renormalize cushion_path.py` fixed, in one commit.

  The file's md5 moved from `23198648db217016cdea85823e38e324` to
  **`8568f6658a90ce33e05e04af73eb03f4`**. Nothing else moved: still 514 lines,
  still 36 primitives from the standalone selftest, `--snap` still
  byte-identical, `hustler.py` untouched. **If you are working from an older
  re-entry prompt that quotes the old hash, that is the one thing to update.**

  A fresh clone should now be completely clean. If `git status` shows
  `cushion_path.py` as modified, that is a real change and not the old phantom
  — treat it as one. Naming files explicitly on `git add` remains the practice
  regardless; the phantom was one reason for it, not the only one.

## 4. Physics calibration (real spec, sourced)

| Quantity | Value in CFG | Source/basis |
|---|---|---|
| Playing surface | 1.82 × 0.91 m | 7 ft table, manufacturer spec (WEPF-legal) |
| Object ball | 50.8 mm / 116 g | WEPF Annexe A |
| Cue ball (default) | 47.6 mm / 94 g | WEPF Annexe A — light cue is championship spec |
| Pocket mouth | 1.6 × ball dia = 81.3 mm, all six | WEPF blackball spec |
| Baulk line | 1/5 table length; black spotted centre of top half | WEPF |
| Ball–ball restitution | pair 0.96 (shape e 0.98) | measured range 0.92–0.98 |
| Ball–rail restitution | pair ≈ 0.75 (cushion e 0.77) | measured effective range 0.6–0.9 |
| Cushion friction | 0.14 | Mathavan et al. (Loughborough 2010) |
| Rolling resistance | constant decel 0.147 m/s² (μᵣ 0.015) | measured 0.005–0.015; napped cloth = slow end |
| Spin model | FOLLOW_KICK 0.60, SIDE_KICK 0.35, decay 0.9/s | game-feel simplification, R2 |

Note the Loughborough 0.98 is NORMAL restitution pre-friction; our pair value
targets observed effective rebound. Measured in selftest at 0.733 — in range.

> **The release history and findings log below run from R1 to R6.10 only.**
> They are preserved because the reasoning in them is genuinely useful — several
> entries record mistakes that would otherwise be repeated. For r15 onward see
> [CHANGELOG.md](CHANGELOG.md). Where a section below describes something as
> "in progress" or "next", read it as a snapshot of what was true at R6.10, not
> as current work.
## 5. Release history

- **R1** — pymunk table, cushions, pockets, strike, ghost-ball overlay, chain.
- **R2** — spin (follow/draw on contact, side on cushions), pocket jaws,
  blackball cue toggle, shot assessment (pot % heuristic + degrees-off).
- **R3** — real-spec rewrite (metres/kg, WEPF numbers, constant-decel cloth),
  full blackball rack, parameterised break, break analyser (`--breaks`),
  one-bounce prediction, pot-drill calibration gate (18/18).
- **R4** — rules-lite blackball, geometric utility AI, three GUI modes,
  `--aigame` tournaments.
- **R5** — AI positional play (decision A3): analytic leave estimate in the
  geometry layer (tangent/carry model, one cushion bounce at reduced energy),
  leave scored via a shared `pot_estimate` (single source of truth with shot
  choice), utility u = p × ((1−greed) + greed × leave); `greed` is a
  personality parameter (SHARK 0.55, STEADY 0.25; greed=0 reproduces R4
  exactly — verified). Break analyser rebuilt two-phase (decision C2):
  phase 1 the R3-comparable grid plus a cue-control column, phase 2 a spin
  sweep (follow/draw × side at 7 m/s, smash and folk-wisdom aims) with
  ctl = mean cue distance from table centre (scratch counted as 1.0 m).
- **Graphics pass** (iterative, art-directed by Maker from reference images):
  wood rails + bolts on navy, cushions drawn FROM the physics segments,
  pockets recessed into the edging with open-mouth rim arcs, trumpet-mouth
  rounded cushion tips at middle pockets (from a technical construction
  drawing), straight 45° corner facings, shaded ball sprites (gradient +
  specular + cloth shadow, cached per colour/radius).
- **Graphics pass 2** (Maker-directed, decisions 1A/2A/3A, from US-spec
  pocket construction drawings — visual language adopted, WEPF dimensions
  kept): pocket cups recessed BEHIND the nose line. Construction: each
  cup's chord on the nose line equals the mouth, so the cup passes exactly
  through both cushion tips (the cushion-to-cup blend) and the centre sits
  behind the nose by h = √(cup_r² − half_mouth²); only a small cap
  (~0.44 × half-mouth) protrudes through the mouth. Geometry lived in
  `pocket_cup_centres(scale=1.35)` (retired at R6.1 when the module's
  draw_table took over pocket rendering); the drawn circle was re-derived in
  SCREEN space from the rendered tip positions (see finding §6.10). Physics
  untouched (3A) — capture points already sat inside the throat, so the
  recess made art and physics agree. **Superseded at R6.1** — the live render
  is now cushion_path.py's layered draw_table (§5 R6.1, finding §6.11).
- **R6** (tangent-true table geometry — decision Fork C/C1): adopted
  `cushion_path.py`'s tangent-true cushion-nose loop (six rails + per-pocket
  22 mm knuckle arcs, C1 straight jaws, flat pocket backs — 36 primitives)
  as the PHYSICAL cushions, replacing the legacy straight-45°-facings +
  deadened-horns builder. The module is driven at this table's 7 ft
  dimensions and mm→m rescaled at the build boundary; collision type remapped
  to `COLL_CUSHION`; rail restitution kept at the calibrated 0.77, pocket
  knuckles/jaws deadened (0.25) and pocket backs dead (0.10) so the throat
  swallows true shots rather than banking them. Corner mouths stay WEPF 1.6×
  (81.3 mm); middle mouths widened to 100 mm (C1 — see finding §6.11). The
  legacy builder is retained as `_build_cushions_legacy` behind
  `USE_TANGENT_CUSHIONS` for A/B comparison. `cushion_path.py` gained a
  `configure()` entry so a host can drive its geometry without touching the
  module defaults.
- **R6.1** (render adoption + containment hardening): adopted
  cushion_path.py's own layered render (`draw_table`) as hustler's table —
  art and physics now share one geometry, gap closed (see §6.11). Fixed a
  rare high-speed tunnel through the thin tangent-true segments via
  per-sub-step capture + PHYS_DT 1/240 -> 1/480 (see §6.11). Chain green,
  containment verified over ~1,500 stress strikes.
- **R6.2** (Graphics Pass 3, Increment 1 — renderer split + GL plumbing;
  decision 1C + 2A): the scene now draws to an offscreen frame surface (the
  single source both backends consume) while the window is a separate
  `display`; the entire draw loop is unchanged, so classic output is
  byte-identical to R6.1. Added a lazy-imported `GLPostProcessor` (moderngl,
  EGL standalone context) running a passthrough shader, plus `--classic` and
  `--smoke-gl` gates. moderngl is imported only when the GL backend is built,
  so the core chain gains zero dependencies. Feasibility settled by a headless
  EGL probe first (see §6.12). Selftest 24→25 (GL passthrough, dependency-aware).
- **R6.3** (Graphics Pass 3, Increment 2 — SSAA + bloom + interactive `--gl`):
  GL-only 2× supersampling (render scale `RS`; the pipeline resolves 2×→1× with
  a linear box filter) + a bloom pass (luminance bright-pass with soft knee →
  separable Gaussian at half-res → additive composite). Presets
  `BLOOM_SUBTLE/BALANCED/ARCADE` at the top of the GL section; default BALANCED
  (threshold 0.78, knee 0.12, intensity 0.60). `--gl` runs the interactive
  window through the pipeline. `RS=1` for classic collapses every scaled literal,
  so classic stays byte-identical to R6.1 (verified). Selftest 25→27 (SSAA
  resolve box-average, bloom sanity). Measured effect on a frame: ~5% of pixels
  changed, ~13k brightened — selective, not a wash (see §6.14).
- **R6.4** (Graphics Pass 3, Increment 3a — fullscreen + fit-to-region,
  Maker-signed-off): resizable window + F11 fullscreen toggle. A new pure,
  dependency-free `fit_to_region()` finds the largest uniform scale `FS` that
  fits the reference (1x) frame into the window minus a reserved right-hand
  panel (`PANEL_W_PX`, currently a placeholder), clamped to
  `FIT_MIN_SCALE`/`FIT_MAX_SCALE` — the same `FS` multiplies both axes, so the
  table's exact 2:1-derived aspect never distorts. `rebuild_render_targets()`
  reruns the fit and rebuilds every size-dependent object (offscreen frame,
  GL pipeline, HUD font) on every resize/fullscreen toggle; the fitted scene
  is centred in the region left of the panel, with the panel itself drawn as
  a flat placeholder rect (3b wires real widgets into that same area).
  **Headless guard held exactly:** smoke/snap always fit at FS=1 with no
  panel — verified byte-identical to the R6.1 baseline by raw pixel
  comparison, not just the pixel-probe assertion. Selftest 27→28
  (fit-to-region: aspect preserved, fits the region, reserves the panel,
  floor-clamps gracefully — dependency-free, no moderngl/EGL needed). Two
  real bugs caught by eyeballing saved captures rather than by the selftest
  (see finding §6.15) — the doctrine earning its keep again.
- **R6.5** (Graphics Pass 3, Increment 3b — hand-rolled tabbed control
  panel, Maker-signed-off): the placeholder
  panel rect is now real widgets — `Slider`, `Button`, `SpinPad`, `TabStrip`,
  hand-rolled immediate-mode classes nested inside `run_gui` (no new
  dependency; `pygame_gui` stays rejected). Every widget binds DIRECTLY to
  the same live variable its mirrored key already mutates (`power`,
  `spin_side`/`spin_follow`, `CFG["CUSHION_ELASTICITY"]`,
  `CFG["ROLL_DECEL"]`, `CFG["BALL_R_M"]`, `mode`, `show_overlay`) — no
  shadow state, so keyboard and widget can't drift apart. SPACE/M/T
  actions were pulled into shared `do_shoot()`/`do_cycle_mode()`/`do_rack()`
  functions so the key and its mirrored button call the identical code path.
  Tabs: **Shot** (power slider, a NEW cue-angle fine-tune slider ±15°
  additive on top of the mouse's coarse aim, a 2D spin pad clamped to the
  unit circle via `spin_pad_map()`, Reset-spin, **Shoot** mirroring SPACE's
  exact guard via the pure `shoot_enabled()`) · **Table** (cushion
  elasticity / roll decel / ball radius sliders, ball radius greyed outside
  SANDBOX same as the B key, cue-size toggle button) · **Game** (mode-cycle,
  rack-up, overlay-toggle buttons, all with live-state labels). Panel stays
  260px (Maker's call — the placeholder width was already comfortable).
  **HUD-crowding fix (Maker's call — icon keeps its own independent size
  floor):** `hud_icon_x()` anchors the aim icon at its usual right-anchored
  spot when there's room, but pushes it further right (never left, never
  smaller) to clear hud2's ACTUAL rendered pixel width once the font's fixed
  floor makes the text encroach, clamped inside the frame at absurd sizes —
  same floor-clamp doctrine as `fit_to_region`. A separate `panel_font`
  (fixed 14px) was added because the panel is drawn straight onto the
  window, not through the scene's SSAA-scaled surface — reusing the scaled
  HUD font would have rendered the panel at double size under `--gl`
  (RS=2), a bug caught before it shipped by reasoning through the pipeline,
  not by eyeballing (worth flagging in case a future pass hits the same
  trap the other way round). **Headless guard — a real near-miss, owned:**
  the first cut of the icon fix ran UNCONDITIONALLY, so a long AI-vs-AI
  status string in `--smoke` (mode 2's `hud2`) pushed the icon a few pixels
  off its R6.1 position and broke the byte-identical invariant (caught by a
  raw byte diff against the pre-3b baseline, not by the selftest, which
  only exercises the pure function in isolation — same lesson as finding
  §6.15, glue can defeat a correct unit in isolation). Fixed by branching
  on `smoke`: the headless path reproduces the ORIGINAL icon formula
  verbatim (including the exact `12 * RSF` spin-dot offset, not the new
  `icon_r * 0.67`), so smoke/snap are provably untouched; the crowding fix
  only applies to the interactive window. Re-verified byte-identical by raw
  byte comparison post-fix. Selftest 28→33 (slider round-trip, spin-pad
  unit-circle clamp, Shoot-guard mirror, HUD-icon-anchor, `rotate_vector`
  round-trip — all dependency-free). Validated: py_compile, selftest 33/33,
  batch 30 (0 escapes), smoke, smoke-gl, classic `--snap` byte-identical to
  R6.1 (raw byte comparison) — plus a scripted interactive session (tab
  switching, slider drag, spin-pad drag, Shoot click) captured to PNG and
  eyeballed, since the render-feature doctrine (finding §6.10/§6.15) says a
  correct-looking value doesn't guarantee the surrounding glue is right.
- **R6.6** (bug-report follow-up, Maker-signed-off): Maker reported that moving the mouse still changed the shot
  angle and the cue-angle slider didn't override it. Root cause: `aim_pos`
  was recomputed from the LIVE mouse position every frame, with the
  offset added on top each frame -- it never actually locked anything down,
  it just rotated whatever the mouse was doing that instant. Maker's call:
  power, aim angle and spin are now HUD-only -- the table's mouse has no
  bearing on aim at all. The old ±15° "cue-angle fine-tune" slider (additive
  on a mouse baseline) is replaced by a new `Dial` widget: drag anywhere
  around it to set an ABSOLUTE angle [0, 360) via `dial_angle()` (true
  inverse of `rotate_vector(1, 0, angle)`), plus ±1° nudge buttons for
  precision. `do_shoot()` no longer reads the mouse at all --
  `rotate_vector(1.0, 0.0, aim_angle)` is the sole source of the strike
  direction, and the interactive aim-overlay preview uses the same value
  (both `strike()` and `ghost_ball()` only care about direction, confirmed
  by reading `vnorm()` -- magnitude was always irrelevant, which is why this
  was a clean swap rather than a wider rewrite). Per Maker's second call,
  keyboard shortcuts for shot PARAMETERS are gone too -- ↑/↓ (power),
  W/S/A/D (spin), X (reset spin) all removed; SPACE (the shoot ACTION, not
  a parameter) stays, since it wasn't part of what Maker asked to remove.
  Table-tab keys (E/F/B/K) and sandbox tools (N/C/R) are unaffected --
  Maker's ask was scoped to aim/power/spin specifically. `--help`'s Controls
  block corrected to match. Selftest 33→34 (`dial_angle` round-trips with
  `rotate_vector` at several angles including the 0/360 wrap, and defaults
  sanely to 0° at the dial's dead centre rather than raising on atan2(0,0)).
  Validated: full chain green, classic `--snap` re-verified byte-identical
  to R6.1 (the smoke path's aim_pos was never touched -- it's still the
  apex-targeting logic, independent of the interactive HUD state) --
  plus a scripted session confirming (a) mouse motion across the whole
  table window has zero effect on aim, (b) dragging the dial to point
  straight down sets exactly 91.1°/90.1° and the on-table aim line rotates
  to match, (c) a `Sim.strike` spy confirms the fired direction vector is
  the exact rotation of the dial's angle (270° dial -> (0, -1) strike, to
  floating-point noise).
- **R6.7** (Increment 4a — spectator motion trails, BUILT, pending Maker's
  own eyeball sign-off): the first of four effect passes (trails -> pot
  swallow/cup-glow -> slow-mo black/bloom ramp -> colour-grade/vignette/
  cloth falloff, Maker's chosen order). Maker's calls: ALL balls get a
  trail while moving (not cue-only), an explicit position-history trail
  (fading dots/ribbon) rather than an accumulation/ghosting blend, always
  on in every mode, and — unlike bloom — this one works in BOTH classic and
  GL, not GL-only (Maker: "some effects should work in classic too, I'll
  flag which"). Implementation: `trail_history` (bid -> list of recent
  world positions, capped at `CFG["TRAIL_LEN"]`, a new live-tunable
  constant next to the bloom presets) is updated once per rendered frame,
  keyed off the same `CFG["STOP_SPEED"]` threshold the physics engine
  already uses for "at rest" -- so a trail can never disagree with the
  Shoot-button guard about whether a ball is "moving." A ball's history is
  dropped the instant its speed falls under that threshold (trail
  disappears with the ball, doesn't linger), and is pruned/cleared outright
  on rack, mode-cycle, and the R sandbox-rebuild key (stale bid reuse would
  otherwise draw a false streak from an old layout to a new one). Drawn as
  a tapering ribbon (`trail_dot_style()`, new dependency-free pure
  function: newest sample full-size/unfaded, oldest at a size floor and
  fully cloth-coloured, monotonic in between) using the ball's own light
  shade faded toward `COL["baize"]` via the existing nested `lerp3()` --
  no new colour-blend primitive needed. Drawn onto `screen` (the scene
  surface itself, not the panel) BEFORE the ball sprites, so each ball
  sits on top of its own trail; this makes it scene content, which matters
  for the next point. **Headless guard: got it right this time on the
  first pass** -- unlike the R6.5 near-miss, the whole trail-update-and-draw
  block was written already gated behind `if not smoke:` from the start
  (trails are real per-frame visual state, exactly the class of thing that
  bit the HUD icon before), and the byte-identical `--snap` comparison
  passed clean without a second attempt. Selftest 34->35
  (`trail_dot_style`: newest sample is `(1.0, 0.0)`, oldest is
  `(0.25, 1.0)`, strictly monotonic between, and a single-sample trail
  doesn't fade). Validated: full chain green, byte-identical `--snap`
  confirmed by raw comparison, plus scripted sessions on BOTH backends
  firing a real shot via the Shoot button and confirming visually: the
  ribbon fades and tapers correctly behind the moving cue ball on classic
  AND GL, the trail shrinks and vanishes smoothly as the ball's speed
  decays toward `STOP_SPEED` (same frame the Shoot button re-enables), and
  a mid-power shot leaves a clean, correctly-ordered fading tail.
- **R6.8** (candidate fix, **UNCONFIRMED** — this is the first bug in the
  project's history I have not been able to reproduce or verify myself;
  everything below is a diagnosis from evidence Iain pasted back, not
  something I watched fail or watched get fixed): Iain reported `--gl`
  showing a black window on his real machine (nix5, real GPU) despite
  `--smoke-gl` passing clean (llvmpipe, all three pixel-probes PASS) on the
  SAME machine. Root cause, from his console output: `libEGL warning: Not
  allowed to force software rendering when API explicitly selects a
  hardware device.` `GLPostProcessor.__init__` unconditionally ran
  `os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")` — harmless in a
  container with no real GPU (nothing to conflict with, which is the only
  environment this was ever validated in — see the "moderngl optional /
  validated headless via EGL/llvmpipe" line at the top of this doc), but on
  a host with a real display connection and a real GPU, EGL sees a
  legitimate hardware device too, forcing software then conflicts with it,
  and the resulting context is broken (black output) rather than raising
  cleanly. `--smoke-gl` passing on the same machine is consistent with this
  theory, not evidence against it — no display server is attached to that
  headless run, so there's no hardware device for the forcing to conflict
  with there. Fix: `GLPostProcessor.__init__` takes a new `force_software`
  parameter (default `True`, preserving every existing headless call site
  unchanged — the three pixel-probe functions `gl_passthrough_check` /
  `gl_ssaa_check` / `gl_bloom_check` never pass it, so `--selftest`'s GL
  assertions and the probes inside `smoke_gl()` still force software
  exactly as before). The one shared call site in
  `rebuild_render_targets()` — used by BOTH `smoke_gl()`'s
  `run_gui(smoke=True, backend="gl")` and genuinely interactive
  `run_gui(smoke=False, backend="gl")` — now passes
  `force_software=smoke`, so the interactive path (smoke=False) is the only
  one that stops forcing it, letting EGL pick Iain's real GPU naturally.
  Also fixed in passing: the window caption and `--help` description both
  still said "(R3)"/"(R5)" from early development, never bumped as the
  internal release number moved on — corrected to "(R6)" (cosmetic only,
  unrelated to the black-screen bug, just noticed it while in this code).
  **Validated (in-container only):** full chain green, byte-identical,
  `--smoke-gl` still reports llvmpipe and PASSES exactly as before
  (confirms the headless call sites are genuinely untouched by this
  change). **NOT validated:** the actual fix, because this container has
  no real GPU and no display server — there is no way to reproduce Iain's
  black screen here to confirm the fix resolves it. This needs Iain to
  re-run `--gl` on nix5 and report back (ideally a screenshot) before this
  entry can be marked resolved rather than candidate.
- **R6.9** (candidate fix, **UNCONFIRMED**, supersedes R6.8's theory):
  Iain re-tested R6.8's fix (`--gl`, no env var needed) and got the SAME
  black screen. That's the finding that matters here: before R6.8, the
  interactive path ALSO forced software (identical config to the working
  `--smoke-gl`), and it was STILL black — so EGL device selection was
  probably never the actual root cause, R6.8's fix just happened to be a
  real (harmless, worth keeping) improvement to a theory that turned out
  wrong. Iain also confirmed classic (no `--gl`) works fine on the same
  machine, and `lspci`/`glxinfo` showed a single Intel UHD Graphics
  (CometLake-U) GPU — no hybrid-graphics device conflict to chase either.
  Redirected the diagnosis to what's structurally different between
  `smoke_gl()`'s frame loop (works, all pixel-probes pass with pixel-exact
  data) and genuinely interactive `--gl` (black) -- since both run the
  IDENTICAL `GLPostProcessor.process()` code, the actual GL computation
  was already proven correct by the selftest's pixel-exact assertion, so
  the bug had to be downstream of that, in how the processed frame reaches
  the window. Found it: `process()` returns a surface via
  `pygame.image.fromstring(out, (w, h), "RGBA", False)`, which carries
  per-pixel alpha and its own internal pixel format -- this was blitted
  onto `display` directly, with no format-matching. That's a known pygame
  gotcha: SDL blits like this can render fine on a permissive path and
  wrong (including solid black) on a real windowing backend depending on
  the native display format. The reason nothing caught this in months of
  my own validation: **every interactive test I've ever run — the R6.5/
  R6.6/R6.7 scripted sessions included — used `SDL_VIDEODRIVER=dummy`**,
  which is how headless testing works at all in this container, but it
  also means none of that testing ever exercised a real window's blit
  behaviour. This is a real gap in what "validated" has meant for anything
  GL-and-interactive in this project so far -- worth remembering next time
  something passes every check in-container but a person reports it broken
  on their own machine. Fix: an explicit `shown.convert(display)` right
  before the blit (a new `blit_surf` local, NOT a reassignment of `shown`
  itself, so `last_shown` -- what `--snap` saves -- is untouched and the
  byte-identical invariant holds). Applied to both the smoke and
  interactive branches for consistency, though only the interactive one
  can actually be affected by a real display's format. **Validated
  in-container:** full chain green, byte-identical `--snap` confirmed by
  raw comparison (unaffected, as expected, since it doesn't touch
  `last_shown`). **NOT validated:** whether this is actually what was
  wrong on Iain's machine -- same limitation as R6.8, this container can't
  reproduce a real windowing backend to test against. Needs Iain to re-run
  `--gl` on nix5.

  **Outcome: PARKED, not solved.** Iain re-tested on nix5 and the R6.9 fix
  didn't resolve it either -- still a black screen. Maker's call: stop
  spending cycles on this for now, classic is the working baseline, move
  on. Both R6.8's and R6.9's changes stay in the code (neither is confirmed
  wrong, and both are reasonable regardless of whether either was ever the
  actual cause), but the interactive `--gl` window should be treated as
  **unconfirmed-broken on the only real hardware it's ever been tested on**,
  not "fixed." A few things worth knowing if a future session picks this up
  again: (1) `--selftest`/`--smoke-gl` passing proves nothing about the
  interactive window -- they're headless, pixel-probe-only, and now
  demonstrably don't catch whatever this is; a real fix needs Iain to test
  on nix5 directly, there's no way to close the loop from a container
  session alone. (2) Two theories were tried and neither confirmed
  (EGL software-forcing, surface format-conversion) -- worth asking Iain
  for a completely fresh, detailed console dump (and maybe `SDL_DEBUG=1`
  or similar verbose SDL/EGL logging) before trying a third theory blind,
  rather than continuing to guess-and-patch. (3) Every effect built after
  this point that's GL-only in the interactive sense (bloom-dependent ones
  especially -- Increment 4c's "bloom ramp" folds in bloom, which only
  exists in the GL pipeline) should be flagged to Maker as build-but-can't-
  be-eyeballed-interactively-by-you until this is resolved, since headless
  pixel-probes are the only validation available for GL-only features
  right now. Classic-capable effects (like 4a's trails) aren't affected by
  any of this.
- **R6.10** (GL removed entirely, Maker's call): after R6.8's EGL-forcing
  scope fix and R6.9's surface-format-conversion fix both failed to resolve
  the black screen on Iain's real hardware (nix5), Maker decided classic is
  the whole game going forward -- not "keep debugging," not "park it and
  maybe revisit," but remove it. Deleted: `GLPostProcessor` (the whole
  offscreen post-process pipeline -- passthrough/resolve/bright-pass/blur/
  composite shaders), `GLUnavailable`, `gl_passthrough_check()` /
  `gl_ssaa_check()` / `gl_bloom_check()` (the three headless pixel-probes),
  `smoke_gl()`, the `BLOOM_SUBTLE`/`BALANCED`/`ARCADE`/`RESOLVE_ONLY`
  presets, and the `--gl`/`--smoke-gl`/`--classic` CLI flags. `moderngl` is
  no longer a dependency at all, optional or otherwise -- the project's only
  dependencies are pygame and pymunk. `run_gui()` lost its `backend`
  parameter entirely; `RS` (render scale) is now hardcoded to `1` rather
  than computed from a backend choice, and every `*RS`/`*RSF` multiplication
  throughout the draw code was left in place rather than stripped out --
  they're no-ops now, but touching ~15 call sites for a cosmetic
  simplification carried real risk for zero behavioural benefit, so the
  safer, lower-diff choice was made deliberately. `present()` is now a
  straight passthrough. The R6.9 surface-format-conversion workaround
  (`shown.convert(display)`) was removed too, since it existed solely to
  fix the GL surface's format mismatch -- classic never needed it (Iain
  confirmed classic worked fine before that fix ever existed) and it cost a
  small per-frame copy for no remaining benefit. Also fixed in passing: the
  top-of-file docstring title still said "(R5)" (a third stale version
  string beyond the two already caught in R6.8 -- window caption and
  `--help` description -- evidently these labels just never got bumped
  consistently across releases; all three now read "(R6)"). File shrank
  from ~3,300 to ~2,750 lines. Selftest **35 -> 32** -- exactly the three GL
  pixel-probe assertions removed, nothing else touched, and the remaining
  32 needed zero changes (none of them ever depended on GL). **Validated:**
  full chain green (`py_compile`, `--selftest` 32/32, `--batch 30` with 0
  escapes, `--smoke`, `cushion_path.py` standalone) -- and, given how much
  of `run_gui`'s render-target setup this touched, the byte-identical
  `--snap` comparison against the ORIGINAL R6.1 baseline (not a
  post-GL-era baseline -- the actual first one, still on disk from the very
  start of this project) got re-run explicitly rather than assumed, and
  passed clean. A scripted interactive session (power slider drag, Shoot
  click, dial visible, trail rendering) was also re-captured post-removal
  and confirmed everything still renders and behaves identically -- the
  panel/dial/trail code never touched GL machinery directly, but this
  refactor came close enough to their shared plumbing (`present()`,
  `rebuild_render_targets()`, the RS/RSF scale variables) that re-checking
  by eye rather than assuming was the right call. **Not validated, and
  no longer relevant:** whether R6.8 or R6.9's theories were ever actually
  correct -- moot now, the code they were fixing doesn't exist anymore.
  If GL is ever wanted again, it's a fresh build, not a revert -- the git
  history has the old implementation if it's ever worth mining for
  reference, but nothing in the current codebase assumes it'll come back.

## 6. Findings log (the interesting bits)

1. **Corner throats were geometrically unenterable in R2** — diagonal opening
   24.7 px vs 26 px effective ball. Widened to √2×pr, which R3 made spec-exact.
2. **Two test-window bugs, zero physics bugs, in R2**: follow/draw was correct
   but measured after a second collision; the jaws "regression" was a grazing
   ball travelling on into a *newly functional* corner and legitimately dropping.
   Lesson: measure at the right moment.
3. **The drill redesign (R3):** approaching corners from table centre is a
   shallow rail-line shot that blackball corners are DESIGNED to reject. Fair
   calibration = throat-axis approach, ±1° line deviation (pocket acceptance),
   not contact-offset (which tests cut-error amplification ~1/fullness).
4. **Break finding (small N, 36 breaks):** full-ball on the apex at 7 m/s gave
   2.00 pots/break vs 0.25–0.75 for all offset/power configs, 0 scratches.
   Folk wisdom (cut the second ball) may be about cue-ball control, which needs
   spin in the sweep — deferred (decision 4B). Verify with `--breaks 20`.
5. **AI-vs-AI, first 4 games:** STEADY (jitter 0.014, threshold 0.18) leads
   SHARK (0.008, 0.10) 2–1 despite worse aim — caution appears to pay. One game
   ended on an illegal black under jitter. Games ran 22–82 shots, all concluded
   legitimately. Needs a proper `--aigame 20+` sample.
6. **94 g cue physics validated:** rebounds at −0.151 m/s off a 116 g ball
   head-on where an equal-mass cue carries through at +0.026. Spec masses
   produce textbook collision behaviour unprompted.
7. **R5 leave-model calibration quirk:** with `aim_jitter=0` the pot-chance
   estimate degenerates to distance decay only (the acceptance-angle term
   goes to 1), so every leave looks good. Leave quality is only meaningful
   at realistic jitter — selftest 22 uses 0.02 rad. The frozen test position
   (cue 0.91,0.455; balls 0.45,0.25 and 0.33,0.72) flips deterministically:
   greed 0 takes the surer pot (p 0.914 vs 0.905), greed 0.9 takes the
   better leave (utility margin 0.195).
8. **Break spin finding (C2, N=12/config, seed 1234):** the §6.4 smash
   still tops phase-1 pots (best pots: 0 mm offset, 7 m/s) but leaves the
   cue worst-placed (ctl 0.78 m, 25% scratch in phase 2). Draw transforms
   it: smash + draw −0.7 + side 0.5 gave 1.83 pots/break, 8% scratch and
   the best control (0.429 m). The folk-wisdom cut (25.4 mm) was worse on
   BOTH pots and control even with spin — in this model the control benefit
   folk wisdom promises comes from draw, not from cutting the second ball.
   Draw alone (selftest 23, deterministic): cue rest moves 633 mm, ctl
   0.809 → 0.218 m. Worth a larger-N confirmation (`--breaks 30`).
9. **First greedy AI sample (N=10):** SHARK (greed 0.55) beat STEADY
   (greed 0.25) 6–4, all games legitimate, 20–73 shots. Three wins came
   from the opponent potting the black illegally — position pressure may
   be inducing errors. Needs `--aigame 20+` before drawing conclusions,
   and re-baselining against greed-0 personalities would isolate what the
   leave term is actually worth.
10. **Rasterisation broke the blend (graphics pass 2 bug, owned):** the
   world-space cup geometry was exact (selftest fit error 1e-16 m) but the
   first render truncated cup centre and radius independently, leaving a
   ~3.5 px wood sliver between each cushion tip and the cup — precisely
   the detail the pass existed to fix. Caught by pixel-probing the
   snapshot, not by the selftest (which pins world geometry only). Fix:
   derive the drawn circle in screen space from the rendered tip
   positions. Residual tip gap ≤ 1 px (the nose-line endpoint pixel).
   Lesson for future art passes: verify at the pixel level; world-space
   correctness does not survive int() twice.

11. **Tangent-true adoption (R6, Fork C/C1) — the middle-throat jam, owned:**
    a straight swap to the tangent-true loop at a UNIFORM WEPF 1.6x mouth
    (81.3 mm) dropped the drill to 12/18 — corners potted 12/12, all six
    MIDDLE shots missed (0/6). Root cause is geometric, not physics: with
    true 22 mm knuckle arcs the middle jaw-to-jaw gap = mouth - 2R = 81.3 -
    44 = 37.3 mm, NARROWER than the 50.8 mm ball, so a middle pot enters the
    mouth then wedges on the knuckles before the drop. This is §6.1's
    "unenterable throat" resurfacing at the middles — and exactly why
    cushion_path.py defaults middles to 100 mm. Minimum middle mouth that
    admits the ball at R=22 is 94.8 mm (= dia + 2R). Corners unaffected
    (diagonal e1-e2 span 68.4 mm > ball). Resolution (C1, Maker-signed):
    non-uniform mouths — corners stay 81.3 mm, middles widen to 100 mm
    (56 mm throat), which is real-world accurate (UK centre pockets ARE cut
    wider than corners; "1.6x all six" was a simplification). Implemented via
    POCKET_MIDDLE_MOUTH_M, a pocket_middle_half_mouth() helper and
    middle-specific capture points; the AI assessor picked up the easier
    middles for free because pot_estimate keys off the capture radius, not
    the mouth. Drill back to 18/18. **Break-pot delta (deterministic, seed
    1234, 10/config):** at the smash (0 mm / 7 m/s) tangent-true pots 0.60
    balls/break vs legacy 1.10 — ~45% fewer — while spread (0.495 vs 0.471 m)
    and cue control (0.671 vs 0.651 m) barely move. The rounded knuckles
    reject fast rattly break balls the deadened straight horns funnelled in;
    straight pots untouched. Preserved as emergent behaviour, not tuned away.
    **Render adopted (R6.1) — art-physics gap CLOSED:** cushion_path.py's own
    layered render (draw_table: wooden rail + cushion slope, baize, nose
    highlight, throat wraps, depth-shaded pockets) IS now hustler's table
    render, driven at the same 7ft / corner-81.3 / middle-100 config so art
    and physics share one geometry. The legacy furniture block (navy fill,
    straight-facing cushions, recessed cups, bolts) was removed from run_gui
    and replaced by a single cushion_geo.draw_table call (mm->screen via w2s);
    the baulk line + pyramid spot are drawn on top, then balls/overlays/HUD.
    (Correction: R6 as first banked kept the legacy render and I wrongly filed
    the mismatch as "defer to pass 3" — that was wrong; the module's render
    was always the intended one. Now done. pocket_cup_centres()/check 24 remain
    but guard now-unused legacy cup geometry — retire when convenient.)
    **Containment hardening (R6.1) — a rare tunnel, owned and fixed:** the
    tangent-true loop is 264 short 5mm-radius segments (vs the legacy 6 long
    ones), which are far more tunnelable. A ball kicked past POWER_MAX by a
    pack collision travelled ~29mm per sub-step at the old 240Hz PHYS_DT
    against a 30.4mm ball+nose collision band, so it occasionally passed
    straight through a cushion and fled (batch found ~0.17%, not caught by the
    10-strike selftest). Two fixes: (a) _capture_pockets() now runs every
    physics sub-step, not once per frame, so a fast ball crossing a capture
    zone is taken before it can reach a back segment; (b) PHYS_DT 1/240 ->
    1/480, halving per-sub-step travel to ~14.6mm << 30.4mm band with headroom
    for transient overshoot. Restitution (shape property) and the rolling
    model (per-frame decel unchanged) are untouched; cushion e still 0.733,
    drill 18/18. Verified 0 escapes across ~1,500 max-power stress strikes +
    3x batch-20. Break-pot rattle finding survived (0.50 pots/break at the
    smash vs legacy 1.10 — the finer step slightly strengthened it).

12. **Headless GL is viable in-container (Graphics Pass 3 feasibility probe):**
    a standalone EGL context on Mesa/llvmpipe gives OpenGL 4.5 Core / GLSL 4.50,
    half-float (rgba16f) FBOs, and a pixel-exact RGBA round-trip. No GPU, no X
    display, no sudo needed. **The trap:** glcontext defaults to X11/GLX and
    raises `XOpenDisplay: cannot open display` headless — `backend='egl'` must be
    forced on `create_standalone_context`. This is what makes the `--smoke-gl` CI
    gate possible in-container; nix5's real GPU is a confirmation, not a hard
    dependency. Row order: pygame is top-row-first and GL texel row 0 is bottom,
    but `tostring → texture.write → fbo.read → fromstring` cancels the flip, so
    passthrough is upright with NO explicit flip. Probe kept as `gl_probe.py`.
13. **The XRGB alpha-slot garbage (Increment 1, owned):** the classic-vs-GL
    passthrough snapshot differed on EVERY pixel, yet RGB was bit-identical
    (ratio exactly 1.0). The whole difference was the ALPHA channel: a plain
    opaque `pygame.Surface` has no per-pixel alpha, so its 32-bit pixels' unused
    X-byte (XRGB) is arbitrary (values 8–254), and `tostring(...,"RGBA")` leaks
    it into the texture. Invisible on-screen (blit to an opaque window drops
    alpha) but it would poison any alpha-aware effect. Fix: every post-process
    pass outputs `vec4(rgb, 1.0)`. After that, GL passthrough is a full-frame
    pixel-exact match to classic. Same §6.10 lesson from the other side —
    verify the WHOLE pixel (incl. alpha), and don't trust an md5 diff to tell
    you *what* changed.
14. **SSAA + bloom, GL-only by construction (Increment 2):** the 2× render
    scale is a single `RS` (2 for GL, 1 for classic) threaded through `S`, `M`,
    the frame size, the font and the HUD/icon pixel literals; with `RS=1` every
    `*RS` is a no-op, so the classic frame stays byte-identical to R6.1 — the
    regression invariant is protected by construction, not by discipline. The
    resolve is a plain linear downsample: for an exact 2:1 (`W=W1*2`, `H=H1*2`)
    bilinear sampling at each output texel centre averages the 2×2 block = a box
    filter (pixel-probed: a block whose 4 subpixels are T±64 resolves to T,
    which a broken/nearest resolve would miss). Bloom = luminance bright-pass
    (Rec.709, soft knee) → separable 9-tap Gaussian at half-res → additive
    composite; a black frame stays black (no light from nothing) and a bright
    core glows outward (both asserted). Balanced preset changed ~5% of pixels
    (~13k brightened), mean abs diff 1.87 but local max 217 — subtle overall,
    punchy on the cue ball/highlights, which is the intended signature.
15. **Two fullscreen/resize bugs, owned (Increment 3a) — caught by eyeballing
    saved captures, not by the selftest:** (a) the `VIDEORESIZE` handler
    recomputed the fit maths (`FS`, fitted size) but never re-called
    `pygame.display.set_mode()`, so the window itself silently stayed at its
    old size — a captured screenshot at the "new" size showed the old
    dimensions verbatim. Fix: re-issue `set_mode((win_w, win_h), RESIZABLE)`
    inside the resize handler. (b) F11 queried `pygame.display.Info()` for the
    desktop resolution AFTER the window already existed; on this backend that
    returns the current WINDOW's size rather than the desktop's, so
    "fullscreen" silently became a same-size no-op. Fix: cache
    `DESKTOP_W/DESKTOP_H` once, immediately after `pygame.init()` and strictly
    before the first `set_mode()` call. A related SDL quirk surfaced alongside
    it: the FIRST `set_mode()` back OUT of `FULLSCREEN` can be a no-op too
    (surface stays at the fullscreen size) — calling it twice is the standard,
    harmless workaround, now baked into the F11-exit path. Lesson for future
    UI passes, same family as §6.10/§6.13: a value computed correctly in
    isolation (`fit_to_region()`'s own selftest was green throughout both bugs)
    doesn't guarantee the surrounding glue actually applies it — verify by
    looking at a real rendered frame, not just the maths.

## 7. The AI (protect the emergence)

`PoolAI(name, aim_jitter, threshold, greed)` — for every legal (ball, pocket)
pair: ghost-ball aim, corridor clearance (cue path AND object path), success
estimate = exp(−½(jitter/allowed)²) where allowed = pocket acceptance angle ×
fullness (thin cuts amplify error), × distance decay. All of that now lives in
`pot_estimate` (geometry layer), shared with the leave assessment. Candidates
above threshold are ranked by u = p × ((1−greed) + greed × leave), where leave
is the best next-shot chance from `estimate_leave`'s analytic rest position
(tangent deflection × LEAVE_TANGENT_KEEP, carry f²×LEAVE_CUE_CARRY — negative,
the light cue rebounds — one cushion bounce at LEAVE_CUSHION_E, all in CFG).
Best utility is taken with jitter applied at execution; otherwise soft safety
on the nearest legal ball. Personalities are ONLY parameters:
SHARK (0.008/0.10/greed 0.55) vs STEADY (0.014/0.18/greed 0.25).
Known gaps: the leave model ignores spin and second cushions; the AI never
chooses spin deliberately; no safety-quality term (safeties still just roll
at the nearest ball).

## 8. Rules-lite coverage (Game class)

Covered: colour assignment on first pot (open table), pot-your-colour-to-continue,
scratch = foul + respot behind baulk (nudged clear) + turn passes, black legal only
if own colour cleared BEFORE the shot, early/scratched black = loss, clean = win.
Deferred to full rules: free shots / two visits, wrong-ball-first fouls, re-racks,
ball-in-hand placement choice.

## 9. Known gaps & deferred items

This section previously tracked the Graphics Pass 3 / GL increments. All of that
is resolved: the tabbed panel and full-screen window shipped, and the GL
renderer was removed entirely at R6.10 after an unresolved black-screen bug on
real hardware. Classic software pygame is the only renderer. Reintroducing GL
would be a fresh build, not a revert, and shouldn't happen without an explicit
ask — the git history has the old implementation if it's ever worth mining.

Current open work now lives in two places, kept up to date:

- **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)** — three open threads, each written up
  with its diagnosis so the next person starts from the answer rather than the
  symptom: full-screen software-render performance; the pot-chance floor being
  a reasonable average rather than an exact fit; and ball-to-ball throw, which
  the estimator does not model and which only bites at extreme cut angles.
  Custom-mode jaws placement and the AI's over-harsh distance term were both
  open here once and are now fixed (r24 and r25/r26) — their diagnoses are kept
  under "Recently fixed".
- **[ROADMAP.md](ROADMAP.md)** — candidates under discussion, with dependencies:
  league mode, the "Grannie" whitewash rule, a possible snooker project, and
  **the shot-log / profiles / tournament arc**, which is the live direction as
  of r32-r34. **Coach mode as a live table overlay is SHELVED, and so is AI
  learning** — do not propose either. Coach mode survives only in the form the
  Maker approved: post-hoc analysis of shots already played ("Human Learning"),
  not a prediction drawn on the baize. Its old entry is still worth reading for
  what was settled about spin dependence, but not as a work item
  (reflect off the real cushion-nose polyline rather than a rectangle; never
  draw a curve, because spin is an impulse at contact only; use
  `pot_assessment()` and not the AI's `pot_estimate()`; cap the prediction at
  the cue plus the first object ball plus cushions, because a break's secondary
  scatter is chaotic and drawing it would be fiction) as well as what is
  genuinely still open. r30 adds one more settled constraint: the engine models
  no miscue limit, so an overlay must not assert one either. Scripted
  play-through tests were on this list and shipped at r28; the cue-ball strike
  point was on it and shipped at r30.

Two constraints worth restating here, because both have been nearly broken by
accident:

- **No asset files.** Everything drawn or played is synthesised in code. Any
  feature that wants a photo, an icon or a sound file needs an explicit decision
  first — including the cartoon granny for the whitewash screen.
- **Table geometry is final.** Read `cushion_path.py`; don't re-derive it.

## 10. Re-entry / continuation prompt

The repository at `github.com/ihoggan/hustler` is the source of truth and is
current — cloning it is the cleanest start. Otherwise paste the prompt below
into a fresh session along with this file, `hustler.py` and `cushion_path.py`:

> We are resuming **HUSTLER**, my UK blackball pool sandbox (pygame + pymunk,
> two files — `hustler.py` + `cushion_path.py` — attached). Read
> HANDOFF_HUSTLER.md first, especially the working agreement (§2) and the engine
> facts (§3); then CHANGELOG.md and KNOWN_ISSUES.md for anything after R6.10,
> since this handoff's narrative sections stop there.
>
> **Working agreement.** Decision brief with genuine forks → my explicit
> sign-off → build → validate. The validation chain is mandatory for every
> change: `py_compile` → `--selftest` → `--batch 30` → `--smoke` (+ `--snap`,
> verified by md5, for anything visual). Report the actual numbers, not
> "passed". One new selftest assertion per feature, testing the pure core rather
> than the pygame wrapper. UK spelling. AI behaviour stays emergent —
> parameters and utility weights, never scripted shots.
>
> **Confirm the chain before proposing anything, and report the actual
> numbers rather than "passed":**
>
> > `hustler.py` md5 `8d002427a4f9d8b65c2d66cbf60606aa`, 9218 lines
> > `cushion_path.py` md5 `8568f6658a90ce33e05e04af73eb03f4`, 514 lines
> > `py_compile` → `--selftest` ALL PASS, **100 assertions** → `--batch 30`
> > with 0 containment escapes → `--smoke` 90 frames → `--snap` md5
> > `62c87ddb6d1f0ee36f36a71a5000cd5f` byte-identical → `cushion_path.py`
> > standalone, 36 primitives. `setup.py` says 0.47.0.
>
> Quote the md5s and the assertion COUNT, not just "ALL PASS" — a stale file
> passes the whole chain, and one nearly got built on for exactly that reason.
> A fresh clone should also be COMPLETELY CLEAN; if `git status` shows
> anything modified, say so before editing. (The old CRLF phantom on
> `cushion_path.py` was fixed at r30.3, so a dirty tree now means a real
> change.) If a marker is missing or a number is off, say so before editing
> anything. Check what is in front of you rather than what the docs claim is
> there — a session once found the repo documenting two measurement scripts
> that had never been committed.
>
> **Two blind spots the chain cannot cover.** The HUD panel is never built or
> drawn headlessly (`build_panel_widgets()` runs only in the non-smoke branch),
> so no capture can show it — instrument the real builder instead, and check
> widget rectangles for overlap rather than only reading the topmost and
> bottommost, at more than one window size. And a seeded `--aigame` score is a
> per-build, per-machine regression check, not an absolute.
>
> **Two measurement tools** sit alongside the game and are not part of the
> chain: `distance_calibration_sweep.py` (fires real simulated shots on a grid
> and compares measured pot rate against the AI's prediction) and
> `floor_threshold_audit.py` (watches real AI games to ask whether a tuning
> constant actually changes a decision). Reach for them when a number in the AI
> is in question — twice now, guessing cost several sessions and measuring
> solved it in one.
>
> **Things not to do without asking:** don't reintroduce the GL renderer
> (removed at R6.10); don't add a dependency (pygame and pymunk only, no numpy);
> don't add asset files; don't re-derive the table geometry; don't reintroduce
> the skill/strategy confound in the AI personalities (`aim_jitter` is
> deliberately matched between them).
>
> **What I actually use it for:** single player — setting the balls up and
> potting them myself. AI-vs-AI was a way to test the physics and is a secondary
> interest. Ask before assuming study or AI work is the priority.
>
> **Don't trust a seeded `--aigame` score across machines.** It is a
> behaviour-preservation check against one machine, not an absolute; two
> previously recorded figures did not reproduce elsewhere on identical code.
>
> **Where I work.** I develop on nix5 but also edit through the GitHub web
> interface, so `git pull` before starting is not optional. Keep any git
> instructions to a single paste-able block — no heredocs unless I ask.
>
> Finally: the last five bugs all passed the whole validation chain and were
> found by playing. If we change rules or turn logic, propose a scripted
> play-through test alongside the unit assertion.

---

*(Written at r23, refreshed at r30. The file is safe to play. Good hunting,
next instance.)*
