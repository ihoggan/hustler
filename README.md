# HUSTLER

A UK blackball pool physics sandbox, written in Python. Real table geometry,
real units, honest cushions — and a set of brutal, tangent-true pocket jaws
that reward a properly lined-up shot and punish a lazy one.

Everything you see and hear is generated from code. There are no image files,
no sound files, and no third-party assets of any kind. The table, the balls,
the shading, the knock of a contact — all synthesised at runtime.

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
  pot them yourself.
- **Use custom mode** — clear the table and place balls exactly where you want
  for trick shots and practice, with four save/load layout slots.
- **Watch or study the AI** — two emergent AI personalities can play each other,
  either for fun or as a way to stress-test the physics.

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
panel (fine angle buttons, a spin pad, power) — this is deliberate, so a shot
is set precisely rather than flicked with the mouse.

### Keyboard controls

| Key | Action |
|-----|--------|
| `Space` | Take the shot |
| `M` | Cycle mode (game / sandbox / custom) |
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

Ball placement in custom mode is done with the mouse: click to place, drag to
move, right-click to remove.

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

Two files, by design. The whole thing is meant to stay small, readable, and
free of binary assets.

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

## Licence

See [LICENSE](LICENSE).
