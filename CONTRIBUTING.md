# Contributing to HUSTLER

Thank you for your interest in contributing! This guide covers the contribution
workflow and expectations.

## Before you start

1. **Read** [README.md](README.md) — what the project is and how to run it
2. **Read** [KNOWN_ISSUES.md](KNOWN_ISSUES.md) — open threads, each with its diagnosis
3. **Check** [ROADMAP.md](ROADMAP.md) — what's under discussion and what it depends on
4. **Verify your baseline** before changing anything:

```bash
python3 hustler.py --selftest      # expect: ALL PASS (126 assertions at r65)
```

If that doesn't pass on a clean checkout, stop and work out why before writing
any code. A failing baseline makes every later result meaningless.

## Workflow

### 1. Pick a task

- Check [ROADMAP.md](ROADMAP.md), or open an issue to discuss something new
- **Anything with a genuine fork gets a decision brief first** — laid-out
  options, a recommended default, and an explicit sign-off before any code.
  Small, fully-specified changes can go straight to build.

### 2. Create a feature branch

```bash
git checkout -b feature/short-description
```

### 3. Decision → build → validate

**A. Decision brief** (in the commit message, or an issue for larger work)

```
Feature: [short title]
Problem: [what are we solving?]
Approach: [how? what alternatives were considered?]
Scope:   [what's in, what's explicitly out?]
```

**B. Implement.** Commit often, in small steps.

**C. Add exactly one self-test assertion.** Test the *pure core* of the feature
— the part that takes values and returns values — not the pygame wrapper around
it. If a feature has no testable pure core, that's usually a sign it should.

**D. Run the full validation chain.** Every time, even for graphics-only work:

```bash
python3 -m py_compile hustler.py cushion_path.py
python3 hustler.py --selftest         # must pass
python3 hustler.py --batch 30         # must show 0 containment escapes
python3 hustler.py --smoke            # must render 90 frames
python3 hustler.py --snap /tmp/new.png && md5sum /tmp/new.png
python3 cushion_path.py               # geometry module's own selftest
```

**Report the actual numbers, not "passed."** The numbers are what let the next
person spot a drift you didn't notice.

Two notes on reading the results:

- `--batch` uses an **unseeded** random number generator, so pot and scratch
  counts vary run to run. The invariant being tested is `containment escapes: 0`.
  If a count looks different, run it a few times on both versions before
  concluding anything.
- `--snap` must stay **byte-identical** (md5 `62c87ddb6d1f0ee36f36a71a5000cd5f`,
  unchanged from R6.1 through r30) unless you are deliberately changing the
  rendered scene, in which case say so explicitly in the commit message.
- A seeded `--aigame` result is a regression check against **one build on one
  machine**, not an absolute. Note which machine a number came from when you
  record one. It has now reproduced identically across nix5 and an x86-64
  Linux container on the same bytes, so a change in the score means behaviour
  moved — but both boxes share an architecture and a libc, genuine
  cross-platform determinism is untested, and CI does not run `--aigame`. If
  you move to different hardware and the number shifts, re-baseline and say so
  rather than assuming a regression.

### Check the file before you commit it, not just the chain

The chain proves a file is internally consistent. It cannot prove it is the
**right** file.

r29 was pushed twice. The first push carried a hustler.py from around r7 —
3065 lines instead of 6358, 3374 deletions, everything from r8 onward gone. It
was copied by mistake from a stale download that had been sitting in the same
folder for a fortnight, shadowing every newer one the browser saved beside it
under a suffixed name.

Every step of the chain passed on that file. `py_compile` was fine. The
selftest read `ALL PASS` — with 35 assertions instead of 69, which the command
as written never checked. `--batch`, `--smoke` and `cushion_path.py` were all
clean. The commit block was chained with `&&` and sailed straight through to
the push.

**Only the `--snap` md5 caught it**, rendering `d571882a…` against the
`62c87ddb…` baseline, and CI went red on exactly that step. That is the whole
argument for enforcing the snap hash in CI rather than letting it warn: it is
the one check that is sensitive to what the file *is* rather than to whether it
hangs together.

So: verify identity up front. Put the hash in front of the copy, not the
validation after it, and the wrong file stops the block dead —

```bash
md5sum ~/Downloads/hustler.py | grep -q <expected> && cp ~/Downloads/hustler.py hustler.py && ...
```

and assert the assertion **count**, not just that it says ALL PASS:

```bash
python3 hustler.py --selftest | grep -c "\[PASS\]"     # expect 126, not "passes"
```

Nothing was lost — the previous revision was a commit away in history — but it
cost a session, and it was the second time a stale copy in a downloads folder
has done that to this project.

Two measurement tools live alongside the game and are **not** part of the gate
— they are slow, they only measure, and they change nothing:

```bash
python3 distance_calibration_sweep.py --trials 300   # pot_estimate vs measured
python3 floor_threshold_audit.py -n 50               # does POT_FLOOR change play?
```

Reach for them when a number in the AI is in question. Both write `--jsonl`.

If your change touches rules or the AI, also run a seeded game batch:

```bash
python3 hustler.py --aigame 12 --seed 4200
```

Seeded games are extremely sensitive to behavioural change, which makes them a
good regression check — and a good way to prove a refactor changed nothing.

### 4. Commit with context

```bash
git commit -m "Feature: [title]

[The decision brief: problem, approach, scope]

Validation:
- py_compile OK
- selftest ALL PASS (N assertions)
- batch 30: 0 containment escapes
- smoke: 90 frames OK
- snap md5 <hash> (byte-identical / deliberately re-captured)
"
```

### 5. Push and open a PR

```bash
git push origin feature/short-description
```

## Code standards

### Style

- **Python 3.12+**
- **Docstrings** on geometry, AI and rules functions — and say *why*, not just
  what. The docstrings in this project carry a lot of hard-won reasoning.
- **Inline comments** for physics, citing sources (WEPF, Mathavan, measured data)
- **UK spelling** throughout: colour, centre, behaviour, metres

### Dependencies

**pygame and pymunk only.** No numpy, no asset files, no images, no sound files.
Everything is drawn or synthesised in code. This has held since the start and is
a deliberate constraint, not an accident — adding a dependency needs an explicit
decision, not an assumption.

### Physics

- Simulation in **real units** (metres, kilograms, seconds); rendering scales by
  `PX_PER_M` at draw time only
- **No game-feel distortion** of the table spec or ball physics
- **Table geometry is final.** The tangent-true cushion loop in `cushion_path.py`
  is the authoritative source. Read it; don't second-guess it.

### AI

- Behaviour **emergent from utility scoring**, never scripted shots or
  hardcoded sequences
- Personality via **parameters** (threshold, greed, caution) — and note that
  `aim_jitter` is a *skill* parameter, deliberately held equal between the study
  personalities so results measure strategy rather than who aims straighter.
  Don't reintroduce that confound.
- Test by running `--aigame` and observing the play style

### Rendering

- **Headless modes render the bare scene** (table and balls, no panel).
  Cosmetic overlays are gated behind `if not smoke:` specifically to protect the
  byte-identical `--snap` baseline.
- **Translucency needs a separate `SRCALPHA` surface, then `blit()`.**
  `pygame.draw` with an RGBA colour writes flat, non-composited pixels onto an
  opaque surface — it does *not* alpha-blend. Every fade, glow and tint depends
  on getting this right.

## Things that will trip you up

Collected from real time lost. Each of these cost somebody a session.

- **The panel's widget lists are keyed by the tab label strings.** Rename a tab
  and you must rename its key too, or it raises `KeyError` on click.
- **`pygame.init()` already initialises the mixer.** A later `mixer.init(...)`
  is a silent no-op. Call `mixer.quit()` first, then init, then *verify* with
  `mixer.get_init()`. A mono buffer fed to a stereo mixer plays at double pitch,
  and no amount of parameter tuning will fix it.
- **`potted_log` is shot-scoped and wiped by `strike()`;** `potted_all` is
  game-scoped. They mean different things — don't make one do both jobs.
- **When a fix doesn't work, stop and measure.** This project has twice burned
  several attempts on consecutive guesses. Both were solved the moment somebody
  looked at actual numbers.
- **Check *who* a bug affects before asking why.** Half of one long investigation
  turned out to be legal play that was never a bug at all.
- **Resolve a tab by name, never by a literal index.** `custom_active()` tested
  `panel_tab == 3` for years. Adding the Spin tab at r30 moved Custom to 4, and
  mouse-table ball placement would have started firing on the wrong tab with
  every automated check still green. It now reads `TAB_LABELS.index("Cust")`.
- **Before adding a field to a shared record, ask what depends on that record
  being reproducible.** The study JSONL is byte-identical for a fixed seed, and
  that property is load-bearing: r17 proved three optimisations
  behaviour-preserving by md5-diffing it. A wall-clock stamp in
  `make_shot_record` would have retired the technique without failing a single
  test. If a field cannot be reproduced, it belongs on the path that needs it,
  not in the shared builder — and write the assertion that fails if it moves.
- **A guess in a data file outlives the person who made it.** The 377 rows
  predating sessions could have been chopped into plausible chunks using commit
  boundaries. Nobody reading the file a year later could tell that from real
  session data. One honest unknown bucket beats four confident fictions.
- **An assertion that inspects source can match its own text.** Assertion 96
  counts assignment sites by reading the module source, and failed first run
  with 3 instead of 1 because the assertion's own literals were in the count.
  Strip the selftest's source before counting.

- **One rule, one definition — especially when a report counts what a rule
  charges.** At r44 the solo clock's foul test and the `--stats` foul count
  would have been two copies of the same condition. Add a third foul case later
  and the report goes on counting two, with nothing failing anywhere. Share the
  predicate and assert both callers route through it.
- **Check WHERE in the frame loop a value is available before blaming the
  caller.** `foul` looked like a missing argument at the human log site. It is
  an ordering problem: the write happens above the game block, before `on_rest`
  has decided anything. A one-line "fix" there would have logged the previous
  shot's state and looked entirely correct.

- **Run the tool before declaring the data can't answer the question.** At r43
  the raw log showed `cut_deg`, `t_cue` and `d_tp` null on all 244 rows, and a
  whole brief was written around rebuilding the geometry — when `--stats` had
  been recovering it at read time since r36 and already printed the answer. One
  command would have settled it. Inspecting the artefact is not the same as
  running the reader.
- **An exclusion rule triggered by failure will flatter your numbers.** The pot
  rate dropped shots whose line pointed nowhere near a pocket, which is the
  right call for safeties and the wrong one for shots missed so badly they
  stopped looking like attempts. Whenever a row is filtered out, ask what makes
  a row get filtered — if the answer correlates with the outcome, report both
  denominators rather than choosing one.
- **A provenance label can BE the outcome.** `observed` targets come from the
  drop pocket, which only exists when the ball dropped; `inferred` targets come
  from the line, which is only consulted when it did not. Splitting a rate by
  those labels yields 100% and 0% and means nothing. Check whether a category
  is caused by the thing you are measuring before you group by it.

- **A fixed pixel inside a scaled layout is a bug waiting for a bigger screen.**
  This has now been found three times: r41's button rects, and at r42 both the
  status strip's `+ 1` leading and the call indicator's `STATUS_STRIP_H - 14`
  clamp. Each looked correct at exactly one window size. When you add a literal
  to anything inside the panel, put it through `U()` or explain in a comment why
  it must not scale.
- **Overlap checks cannot see text spilling out of a widget.** Rects can pass
  every containment and collision test while the label rendered into them runs
  off the panel — r41 found six such overflows, and r42's first constants layout
  reproduced it immediately, overflowing the 232px panel by up to 104px at 1.0x.
  Measure rendered string widths with `font.size()` against the space you have,
  at every scale, before believing a layout fits.
- **A silent clip is worse than a visible one.** The status strip breaks its
  draw loop rather than spilling onto the tabs, so an over-subscribed strip does
  not look like a bug — it looks like the line was never written. r42 found a
  full game quietly losing two lines this way. Anything added to the strip has
  to take a line away, and `strip_leading()` is what pays for the spacing.

- **Write git command blocks with no globs.** The maintainer's shell is zsh,
  where an unmatched glob raises `no matches found` and abandons the *entire*
  command line — so a defensive `for f in files*/thing.py` silently prevents
  everything after it from running, including the guard that was supposed to
  protect you. Name paths explicitly, or use `find`.

## Testing philosophy

The self-test suite is strong on pure functions and physics invariants and
blind to gameplay flow. Every one of the four r23 bugs — turn handover, spin
reset, cue placement, sandbox ball-in-hand — passed the entire validation chain
and was found by sitting down and playing. So did the r27 chamber bug. That is
five, and that tally is what the scripted play-through test at r28 exists to
answer.

Selftest 60 drives a whole frame — eight shots — through the rules engine and
asserts eleven named invariants covering turn, visit, spin and placement state
after every one. Two things about it are worth copying if you extend it. It
asserts *named invariants* rather than freezing a golden trace, because a
golden rewrites a large literal on every deliberate change and preserves
whatever was wrong when it was captured. And it was **mutation-tested before it
shipped**: five historical bugs were reintroduced one at a time and each was
confirmed caught, because a test that has never failed has not been shown to
work. Do that for anything you add here.

So: add the assertion, run the chain, **and then play the game**. If you're
adding rules or turn logic, consider a scripted play-through test that drives a
whole frame and asserts the state at each step.

### When an assertion fails, find out which end is wrong

Twice now — r29's power nudge and r30's picker fit rule — a new assertion has
failed on its first run with the *code* correct and the *expectation* wrong.
Both times the instinct was to reach for the implementation. Read the failure
detail first and work out which end you actually trust: a test written from an
idea of how something should behave is exactly as likely to be wrong as the
code written from the same idea, and it is cheaper to be wrong in the test.
When it turns out the test was at fault, leave a note in the assertion saying
so. Both of those episodes are recorded in the source beside the assertion.

### Measuring that it fits is not measuring that it is laid out

The panel layout probe below reports the extent of a tab — its topmost and
bottommost widget. At r30 the Shoot button was moved up by a wrong constant and
overlapped the aim row by 10 px, and the probe reported a perfectly sensible
bottom edge throughout, because an overlap does not change a maximum. Any probe
of this kind should also compare every pair of widget rectangles for
intersection. It costs four lines and it catches the whole class.

### A collision handler fires per substep, so anything it accumulates must fold

pymunk calls `post_solve` for as long as two bodies stay in contact, and
`Sim.step()` runs eight substeps a frame. At r35, before any code was written,
one ordinary shot was measured producing **fifteen** cue-cushion callbacks for
what a player would call **four** rebounds — and one of those contacts fired
eleven times on its own, because a ball sitting in the jaws touches several
cushion primitives simultaneously and each gets its own arbiter.

The trap is that raw accumulation produces something that looks *more*
detailed, not obviously broken. A trail of fifteen entries reads like a rich
record until you ask it how many cushions the white found and it answers four
times too many. If you add anything that counts, appends or accumulates from a
collision handler, fold repeats at the point of recording and assert the
folding — `trail_append()` and self-test 82 are the worked example. And note
that the existing rules facts sidestep this by being *latches*
(`first_contact`, `cushion_after_contact` are set once and never counted),
which is why the problem had not come up before.

### A mutant that CRASHES the test has not been caught by it

Mutation testing asks whether an assertion can fail. An assertion that raises
instead — a `KeyError` because the mutated code returned `None` where the test
subscripted a dict — makes the build red, so it looks like a catch. It is not
one. The check never ran, so nothing was measured, and the same assertion would
sail past a mutant that returned a *wrong* value rather than a missing one.

Found at r36: five of six mutants failed self-test 83 cleanly and the sixth
blew up in the detail string, which is evaluated eagerly as an argument to
`check()`. The fix is to make every lookup in an assertion non-raising
(`.get()` over `[...]`, `x or {}` after anything that can return `None`) so a
mutant produces a readable failure with the actual values in it. Same family as
the r30 mutants that silently passed because they could not import
`cushion_path` — a harness that cannot report has not proved anything.

### One literal answering several questions is the bug, not the literal

`custom_active()` tested `panel_tab == 3` for years and adding a fifth tab moved
`Cust` to 4. The obvious lesson — resolve by name, not by index — is right and
insufficient. At r37 eighteen sites tested `mode == 0`, and renaming the constant
would have fixed none of them, because that one test was answering three separate
questions that agreed only by accident of there being a single Game-less mode.

When a new case makes an old constant ambiguous, the fix is not a better constant.
It is to name each question and answer them independently — `mode_intents()` is the
worked example — and then to assert the whole table, so the next case added fails
the build until somebody classifies it on purpose.

### The panel probe does not cover the status strip

The overlap probe walks `panel_widgets` and compares every pair of rectangles.
The persistent status strip is not in `panel_widgets` — it is drawn directly,
above the tabstrip, into a fixed `STATUS_STRIP_H` budget, and its loop `break`s
rather than overflowing. So a strip that overruns passes the probe, passes the
chain, and quietly drops its last line.

If you add anything to the strip, count the lines against the budget as well as
running the probe, and leave a line spare: the panel font comes from `SysFont`
with fallbacks, so the line height on your machine is not necessarily the line
height on someone else's. `solo_status_lines()` caps itself and self-test 85
pins the cap.

### Testing a helper is not testing that anything calls it

At r38 the shot log moved into the repo, and one resolver was introduced so the
writer and `--stats` could not drift onto different paths. Self-test 86 asserted
the resolver thoroughly — and then two mutants that pointed the writer and the
reader back at the old location both PASSED it, because the assertion only ever
exercised the helper in isolation.

Where a function exists specifically to be the single source of a value, assert
that its CALLERS still use it. `main.__code__.co_names` covers the CLI;
`run_gui` needs a recursive walk over `co_consts`, since the writer is a nested
function and a flat name check misses it entirely. Self-test 72 introduced the
technique for closure state; it applies to any "these two must agree" helper.

## Getting help

Search the issues and PRs first — the reasoning behind most decisions is written
down somewhere. If you're stuck, open an issue describing what you tried and
what you measured.

## Code of conduct

- Be respectful and constructive
- Assume good intent
- Give credit where due
- Focus on the code, not the person

---

Thank you for contributing!
