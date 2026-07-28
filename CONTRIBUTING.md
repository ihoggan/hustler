# Contributing to HUSTLER

Thank you for your interest in contributing! This guide covers the contribution
workflow and expectations.

## Before you start

1. **Read** [README.md](README.md) — what the project is and how to run it
2. **Read** [KNOWN_ISSUES.md](KNOWN_ISSUES.md) — open threads, each with its diagnosis
3. **Check** [ROADMAP.md](ROADMAP.md) — what's under discussion and what it depends on
4. **Verify your baseline** before changing anything:

```bash
python3 hustler.py --selftest      # expect: ALL PASS (71 assertions at r30)
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
python3 hustler.py --selftest | grep -c "\[PASS\]"     # expect 71, not "passes"
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
