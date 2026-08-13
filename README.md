# HUSTLER

A UK blackball pool physics sandbox, written in Python. Real table geometry,
real units, honest cushions — and a set of brutal, tangent-true pocket jaws
that reward a properly lined-up shot and punish a lazy one.

![HUSTLER in Sandbox mode: a full rack of reds and yellows around the black, the cue ball in hand on the baulk line with a red aim line and ghost ball projected into the pack. A banner above the table names the mode, with the ball count and ball-in-hand prompt on the line beneath. The tabbed control panel sits down the right-hand side. Every pixel is drawn from code](Screenshot.png)

Everything you see and hear in the game is generated from code — no image
files, no sound files, no third-party assets loaded at runtime. The table, the
balls, the shading, the knock of a contact are all synthesised.

![status](https://img.shields.io/badge/status-playable-brightgreen)
![python](https://img.shields.io/badge/python-3.12-blue)
![deps](https://img.shields.io/badge/dependencies-pygame%20%2B%20pymunk-lightgrey)

---

## What it is

HUSTLER simulates a 7-foot UK pool table to WEPF specification — 81.3 mm corner
pockets, 100 mm middles, correct ball sizes and masses, real rolling friction.
The cushion noses are built from true tangent geometry rather than a rough
outline, which is why the pockets *play* the way a real table does: line the
shot up and it drops; catch a knuckle and it rattles.

You can:

- **Play single-player** — set up the balls, aim from the control panel, and
  pot them yourself. This is what the project is mainly for.
- **Race a timed clearance** — SOLO mode clocks you from the first strike to the
  black. Every run is recorded against your profile, with a personal best you
  have to beat.
- **Play a career** — a menu shell holds your profile, an eight-player league
  played one fixture at a time, play-offs seeded by the final table, and
  trophies that stay on your record.
- **Use custom mode** — clear the table and place balls exactly where you want
  for trick shots and practice, with four save/load layout slots.
- **Watch or study the AI** — eight emergent AI personalities, matched so they
  differ in temperament rather than in how straight they aim.

## The career menu

The game boots into a menu rather than straight onto the table. It holds your
profile name and nickname, a **Solo** row showing your best clearance time, the
league table with each player's strength beside it, the play-off bracket, and
**Resume** for a frame you left half-played.

A league fixture is an ordinary frame that happens to be the one the season is
waiting on — there is no separate mode to remember being in, and no way to play
your fixture and have it not count. Press `Esc` at any point to come back here.

Ranking is by Bradley-Terry strength, which weighs *who* you beat rather than
how many: seeing off the runaway leader counts for more than seeing off the
bottom seed. The win rate is shown beside it with its Wilson interval, because
over seven games a percentage on its own says more than it knows.

## Requirements

- **Python 3.12**
- **pygame 2.6.1**
- **pymunk 7.3.0**

No other dependencies. Nothing to compile.

```bash
pip install pygame==2.6.1 pymunk==7.3.0
```

> **Windows note:** if you install a library and the game still can't find it,
> you almost certainly have more than one Python installed and the install
> landed in a different one than the game runs under. The reliable fix is to
> route both through the same launcher:
>
> ```bash
> py -m pip install pygame==2.6.1 pymunk==7.3.0
> py hustler.py
> ```
>
> Running from the terminal (rather than IDLE or a double-click) also avoids a
> separate class of window/event-loop weirdness with pygame.

## Running it

```bash
python hustler.py
```

The game starts full-screen. Aiming is done entirely from the on-screen control
panel — this is deliberate, so a shot is set precisely rather than flicked with
the mouse. Angle, power and spin each have a coarse control and fine adjustment
buttons, and all three snap to a grid fine enough that the number you read is
the number you get: a shot you can write down is a shot you can play again.

The **Shot** tab is laid out in the order a shot is played: power, aim angle,
spin, then Shoot. Spin is set by clicking or dragging on a cue-ball picker on
that same tab, when the window is tall enough to hold it. The rim of the drawn ball is the most spin the engine can
apply — nothing is greyed out, because everything inside it is reachable. The
dashed ring at three-quarters is an advisory note about where a real cue starts
to miscue; the simulation does not model a tip, so nothing enforces it. The
cursor is drawn at true tip scale, which is why placing fine spin feels
fiddly — it is fiddly in reality, for the same reason.

### Keyboard controls

| Key | Action |
|-----|--------|
| `Space` | Take the shot |
| `M` | Cycle mode (sandbox / you vs AI / AI vs AI / solo) |
| `Esc` | Back to the career menu (and back out to the table) |
| `Q` | Quit |
| `T` | Re-rack |
| `R` | Reset table (sandbox) |
| `N` | Add a random ball (sandbox) |
| `C` | Clear object balls (sandbox) |
| `B` / `Shift+B` | Nudge ball radius up / down (sandbox) |
| `K` | Toggle cue-ball size |
| `E` / `Shift+E` | Cushion elasticity up / down |
| `F` / `Shift+F` | Rolling friction up / down |
| `G` | Toggle the aim overlay |
| `F11` | Toggle full-screen / windowed |
| `Esc` / `Q` | Quit |

### Placing the cue ball

When you have ball in hand — at the start of a rack, after any foul, or whenever
you pot the white — the baulk area is shaded to show where placement is legal,
and you **drag the cue ball there with the mouse**. There's no key for it.

This works in sandbox as well as in a game against the AI, because people play
solo on pool tables and being able to set the white where you want it is half
the point.

Ball placement in custom mode is also done with the mouse: click to place, drag
to move, right-click to remove. You can set a ball right on a pocket lip — a
hanger ready to pot — because placement is bounded by the real cushion-nose
geometry, not a rectangle; only spots that would embed a ball in a rail or drop
it straight into a pocket are refused.

## Command-line tools

HUSTLER doubles as its own test bench. These run headless (no window needed):

| Command | What it does |
|---------|--------------|
| `python hustler.py --selftest` | Runs the full assertion suite (dependency-free core logic) |
| `python hustler.py --batch N` | Fires N random strikes, reports containment and timing |
| `python hustler.py --smoke` | Renders 90 frames on a dummy video driver |
| `python hustler.py --snap FILE` | Saves a single reference screenshot |
| `python hustler.py --breaks N` | Break analyser, N trials per configuration |
| `python hustler.py --aigame N` | Plays N headless AI-vs-AI games and reports the result |
| `python hustler.py --aigame N --jsonl FILE --seed S` | As above, writing a per-shot study log for analysis |
| `python hustler.py --sound-probe [DIR]` | Dumps every synthesised sound to WAV for auditioning |

## Project layout

```
hustler.py        the game — physics, rules, AI, rendering, sound, HUD
cushion_path.py   tangent-true cushion-nose geometry (imported as cushion_geo)
```

**The game is two files, by design** — small, readable, and free of binary
assets. Two further scripts sit alongside it as measurement tools. They are not
part of the game and the game never imports them:

```
distance_calibration_sweep.py   fires real simulated shots on a grid and
                                compares the measured pot rate against the
                                AI's own prediction, with confidence intervals
floor_threshold_audit.py        watches real AI-vs-AI games to ask whether a
                                given tuning constant actually changes play
```

Both are slow, both only measure, and neither is part of the validation chain.
They exist because two separate AI bugs were solved by measuring rather than
reasoning, and the rigs were worth keeping.

## Design principles

These have held throughout the project and are worth knowing before contributing:

- **No dependencies beyond pygame + pymunk.** No numpy, no asset files.
  Everything is drawn or synthesised in code.
- **Real units in the physics layer.** Metres, kilograms, metres per second —
  WEPF spec, not screen pixels.
- **The AI is emergent.** Its behaviour comes from a handful of utility
  parameters, never from scripted shots or hardcoded sequences.
- **Every change is validated.** Compile, self-test, batch, smoke — and a
  byte-identical screenshot check for anything visual.
- **UK spelling** throughout (colour, behaviour).

## Known issues

See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the current list of bugs and rough
edges, each with its diagnosis. Nothing there stops the game being playable —
they're the honest state of the last few open threads.

## History

See [CHANGELOG.md](CHANGELOG.md) for how it got here — the graphics, sound,
rules, HUD, custom mode, and the long tail of physics and AI work.

## Credits

**David Hoggan** — Software Tester #1, and the man who taught me the game.

## Licence

See [LICENSE](LICENSE).
