# HUSTLER — UK Pool Physics Sandbox

[![Tests](https://github.com/ihoggan/hustler/actions/workflows/validate.yml/badge.svg)](https://github.com/ihoggan/hustler/actions)

A Python/pygame pool physics sandbox built to answer how angles, spin, and the break actually work. It features WEPF-compliant real-world physics, a geometric utility AI with emergent behaviour, and comprehensive headless validation. Playable interactive game with AI-vs-AI spectator mode.

**Current Status:** R6.3 (Graphics Pass 3, Increments 1–2 complete). Validation: 27/27 selftest ✓, 18/18 drill ✓, 0 escapes over stress testing. **Increment 3 (fullscreen + hand-rolled tabbed control panel) is signed off and ready to build.**

## Quick Start

### Requirements
- Python 3.12+
- `pip install pygame pymunk`
- Optional (GL renderer): `pip install moderngl`

### Run

```bash
# Interactive sandbox (classic renderer)
python3 hustler.py

# Interactive with GL post-processing (2× SSAA + bloom)
python3 hustler.py --gl

# Validation suite
python3 hustler.py --selftest

# Headless batch test (N random strikes)
python3 hustler.py --batch 30

# AI vs AI tournament (N games)
python3 hustler.py --aigame 10

# Break analyser (N trials per config)
python3 hustler.py --breaks 100

# Headless smoke test (90 frames, dummy video driver)
python3 hustler.py --smoke

# Save headless screenshot
python3 hustler.py --snap output.png
```

### Controls (Interactive)

| Key | Action |
|-----|--------|
| **Mouse** | Aim (cue → pointer) |
| **SPACE** | Strike (only when at rest & human turn) |
| **UP/DOWN** | Power ±0.25 m/s (0.5–7.0) |
| **W/S** | Follow/draw (top/backspin) |
| **A/D** | Side spin (left/right english) |
| **X** | Reset spin to centre |
| **M** | Cycle mode: SANDBOX → YOU vs AI → AI vs AI |
| **T** | Rack up (new frame) |
| **K** | Toggle cue ball: WEPF 1-7/8″ ↔ casual 2″ |
| **E/Shift+E** | Cushion elasticity ±0.05 |
| **F/Shift+F** | Rolling resistance ±0.02 |
| **G** | Toggle prediction overlay |
| **ESC/Q** | Quit |

*Sandbox mode only (B/Shift+B: ball radius; N: new ball; C: clear; R: reset)*

## Architecture

### Design Principles
- **Real units:** pymunk simulation in metres/kg/seconds; rendering scales by `PX_PER_M` only.
- **Pure geometry layer:** ghost ball, ray corridor, one-bounce prediction, pot assessment — no pymunk import, directly testable.
- **Emergent AI:** behaviour arises from parameters (greed, jitter) and utility scoring, never scripts.
- **Headless-first validation:** every feature validated via selftest assertions before interactive use.

### Core Files

| File | Purpose |
|------|---------|
| `hustler.py` (~2,570 lines) | Simulation loop, rules engine, UI, AI, rendering pipelines |
| `cushion_path.py` (~514 lines) | Tangent-true cushion-nose geometry, layered render module |

### Key Layers

- **Simulation:** pymunk physics (collision_slop 0.0002, ball restitution 0.96, rail 0.75)
- **Geometry:** pure-Python pot estimates, ghost-ball overlay, carry prediction
- **Rules:** rules-lite blackball state machine (colour assignment, pot-to-continue, scratch, black logic)
- **AI:** utility-based shot selection with positional leave estimation (greed parameter controls balance)
- **Graphics:** classic rasterised (pygame) + GL post-process (2× SSAA + bloom, headless-viable via EGL/llvmpipe)

## Physics Specification

All specs sourced from real-world championship data (WEPF, manufacturer, peer-reviewed research):

| Quantity | Value | Source |
|----------|-------|--------|
| Playing surface | 1.82 × 0.91 m | 7 ft table, WEPF-legal |
| Object ball | 50.8 mm / 116 g | WEPF Annexe A |
| Cue ball | 47.6 mm / 94 g (WEPF spec); 50.8 mm / 120 g (casual) | Championship vs casual |
| Pocket mouth | 81.3 mm (1.6× ball dia) | WEPF blackball spec |
| Ball restitution | 0.96 (pair) | Measured range 0.92–0.98 |
| Rail restitution | 0.75 (effective pair) | Measured range 0.6–0.9 |
| Cushion friction | 0.14 | Mathavan et al. (Loughborough 2010) |
| Rolling resistance | 0.147 m/s² (μᵣ 0.015) | Measured 0.005–0.015 for napped cloth |
| Spin model | FOLLOW_KICK 0.60, SIDE_KICK 0.35, decay 0.9/s | Game-feel calibration (R2) |

See [PHYSICS.md](docs/PHYSICS.md) for calibration methodology and findings.

## Validation & Testing

**The validation chain is mandatory for every change:**

```
py_compile → --selftest → --batch N → --smoke
+ --smoke-gl (GL changes) + --snap (pixel-probe for render)
```

### Current Snapshot

- ✅ Selftest: **27/27** (24 physics/logic + 3 GL, dependency-aware)
- ✅ Drill: **18/18** (tangent-true pot gate across all six pockets)
- ✅ Containment: **0 escapes** over ~1,500 max-power stress strikes + batch-30
- ✅ Classic render: **byte-identical to R6.1 baseline**
- ✅ GL path (EGL/llvmpipe): **SSAA + BALANCED bloom, pixel-exact to classic**
- ✅ cushion_path.py standalone: **green** (6ft/89–100 mm spec validated)

### One Assertion Per Feature

Every new feature adds one selftest assertion. GL assertions are dependency-aware (skip if moderngl/EGL unavailable, so core chain stays green on stripped containers).

## Development

### Getting Started

1. Clone the repo: `git clone https://github.com/ihoggan/hustler.git`
2. Install: `pip install -r requirements.txt`
3. Run: `python3 hustler.py`
4. Validate: `python3 hustler.py --selftest` (should show 27/27)

### Working Agreement

- **Decision → sign-off → build → validate.** All code changes must pass the full validation chain.
- **One selftest assertion per feature.** New gameplay, physics, or graphics code adds a corresponding selftest check.
- **Emergent AI only.** Behaviour comes from utility scoring and parameters (greed, jitter). No decision scripts.
- **UK spelling** throughout (colour, favour, centre, etc.).
- **Real WEPF units** — no game-feel fudging of the table spec or ball physics.

### Code Style

- Python 3.12+ idioms
- Inline docstrings for geometry and AI functions
- Physics code comments cite the source (WEPF, Mathavan, etc.)
- No dependencies outside pygame/pymunk (moderngl is optional, lazily imported)

See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for the full contribution guide.

## Roadmap

### Graphics Pass 3 (In Progress)
- ✅ **Increment 1 (R6.2):** Renderer split, `--classic` + `--smoke-gl` gates
- ✅ **Increment 2 (R6.3):** GL-only 2× SSAA + bloom (live-tunable presets: SUBTLE/BALANCED/ARCADE)
- 📋 **Increment 3a (SIGNED OFF, ready):** Resizable/F11 window, fit-to-region, placeholder panel
- 📋 **Increment 3b (SIGNED OFF, ready):** Hand-rolled widgets, tabs, Shoot button, key↔control sync
- 📋 **Increment 4 (deferred):** Effect passes (trails, slow-mo, pot swallow, colour-grade, vignette)
- 🔮 **Increment 1B (deferred):** GL-native renderer (per-pixel shaded spheres, MSAA, cloth nap)

### R6 Gameplay (Queue Behind Graphics Pass 3)
- Full WEPF rules + foul-risk term
- AI spin selection + spin-aware leave estimation
- Safety quality term
- Spectator polish (shot commentary, score banner)

### Deferred Research
- Confirm §6.8 (break rattle finding) and §6.9 (contingency on random swerve) over larger N studies
- American table preset (specs on file)

## Architecture & Design

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — detailed design overview (decisions 1A–1C, 2A–3A)
- [PHYSICS.md](docs/PHYSICS.md) — real-world spec sourcing, calibration, findings
- [FINDINGS.md](docs/FINDINGS.md) — critical engine facts, known issues, hard-won discoveries

## Contributing

Pull requests welcome, but **all code must:**
1. Pass `py_compile`
2. Pass `--selftest` (27/27 assertions, including at least one new assertion per feature)
3. Pass `--batch 30` (containment check)
4. Pass `--smoke` (interactive loop smoke test)
5. Maintain byte-identical classic render (checked via `--snap`)

See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for the full workflow.

## License

[Specify your license here — e.g., MIT, GPL-3.0, etc.]

## References & Calibration

- **WEPF Equipment Specification:** Pocket mouths (1.6× ball diameter), ball specs, table dimensions
- **Mathavan et al. (Loughborough 2010):** Measured cushion friction (0.14) and restitution (0.98 normal, pre-friction)
- **Manufacturer Data:** Ball restitution range, rolling resistance over napped cloth
- **Game Physics Engine:** pymunk 7.3.0 (collision handling, constraint resolution)

## Contact & Changelog

- **Author:** Iain Hoggan  
- **Repository:** https://github.com/ihoggan/hustler  
- **Status Page:** See [HANDOFF_HUSTLER.md](docs/HANDOFF_HUSTLER.md) for detailed project history and current work-in-progress notes.

---

**Last Updated:** July 2026 (R6.3) — Graphics Pass 3 Increments 1–2 banked; Increment 3 signed off and ready to build.
