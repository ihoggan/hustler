# Contributing to HUSTLER

Thank you for your interest in contributing! This guide covers the contribution
workflow and expectations.

## Before you start

1. **Read** [README.md](README.md) — what the project is and how to run it
2. **Read** [KNOWN_ISSUES.md](KNOWN_ISSUES.md) — open threads, each with its diagnosis
3. **Check** [ROADMAP.md](ROADMAP.md) — what's under discussion and what it depends on
4. **Verify your baseline** before changing anything:

```bash
python3 hustler.py --selftest      # expect: ALL PASS (67 assertions at r27)
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
  unchanged from R6.1 through r27) unless you are deliberately changing the
  rendered scene, in which case say so explicitly in the commit message.
- Seeded `--aigame` results are **platform-sensitive**: the physics is
  float-heavy, so a recorded score is a regression check against *the same
  machine*, not an absolute. Note which machine a number came from when you
  record one, and re-baseline rather than debug if you move machines.

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

## Testing philosophy

The self-test suite is strong on pure functions and physics invariants and
blind to gameplay flow. Every one of the four r23 bugs — turn handover, spin
reset, cue placement, sandbox ball-in-hand — passed the entire validation chain
and was found by sitting down and playing. So did the r27 chamber bug. That is
five, and the tally is the argument for the scripted play-through tests at the
top of the roadmap.

So: add the assertion, run the chain, **and then play the game**. If you're
adding rules or turn logic, consider a scripted play-through test that drives a
whole frame and asserts the state at each step.

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
