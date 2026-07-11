# HANDOFF — HUSTLER (UK Pool Physics Sandbox)

**Status:** R6.10 — **GL removed entirely (Maker's call).** After R6.8/R6.9's
candidate fixes failed to resolve the interactive black-screen bug on nix5,
Maker decided classic is the whole game going forward: `GLPostProcessor`,
`GLUnavailable`, the three GL pixel-probe functions, `smoke_gl()`, bloom, the
SSAA render-scale plumbing, and the `--gl`/`--smoke-gl`/`--classic` CLI flags
are all gone. `moderngl` is no longer a dependency at all, optional or
otherwise. Selftest dropped from 35 to 32 (the three GL pixel-probes
removed; nothing else changed). Full chain re-validated green after the
removal, including the byte-identical `--snap` guarantee against the
original R6.1 baseline — confirmed by raw byte comparison, not just
assertion, same as every other change in this project. R6.7 (spectator
motion trails) is unaffected (it was already classic-capable) and still
awaits Maker's eyeball. See the R6.10 finding for the full removal record.
**Files:** `hustler.py` (~2,750 lines) **+ `cushion_path.py`** (unchanged,
tangent-true cushion-nose geometry module) — single project, two files.
Python 3.12, pygame 2.6.1 + pymunk 7.3.0. No other dependencies.
**Install:** `pip install pygame pymunk` (add `--break-system-packages` on
system Python, or use a venv). That's everything — the whole core+GUI chain
now has just these two dependencies.
**Platform:** Runs anywhere pygame does. No GPU, no EGL, no display-driver
quirks to worry about — the entire class of bug from R6.8/R6.9 is gone with
the code that caused it.
**Run note:** `cushion_path.py` must sit alongside `hustler.py` (it is
imported as `cushion_geo`). Its own standalone selftest (`python3
cushion_path.py`) validates the reference 6ft/89-100 spec and stays green
independently. Table geometry is FINAL as of R6.1 — no construction drawing
is forthcoming; the tangent-true loop is the authoritative source of truth.

---

## 1. What this project is

A UK blackball pool physics sandbox grown into a playable game with a utility AI,
built to answer the original question: *how do angles, spin, and the break actually
work?* The long-term destination is AI-vs-AI spectating with emergent behaviour.

## 2. Working agreement (non-negotiable, carried from AISpecOps/HexWars)

- Decisions brief with genuine forks → explicit sign-off → build → validate.
- Validation chain, every release, even graphics-only changes:
  `py_compile` → `--selftest` → `--batch N` → `--smoke` (+ `--snap` for screenshots).
- One selftest assertion per feature. Currently 32 (all physics/logic/UI, dependency-
  free — GL removed entirely at R6.10, no dependency-aware SKIP path needed anymore).
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
  `--aigame N` (AI tournaments), `--smoke`, `--snap FILE`.

### Critical engine facts (hard-won, do not rediscover)

- **pymunk 7 removed `add_collision_handler`** — use
  `space.on_collision(collision_type_a=, collision_type_b=, post_solve=fn)`.
- **`space.collision_slop` defaults to 0.1 space-units = 10 cm in metre units.**
  Must be set (we use 0.0002) or collisions are mush.
- pygame.draw writes raw RGBA without blending — translucent paint on a sprite
  punches through to the background when blitted. Pre-blend highlight colours.
- pygame.draw.arc uses maths-convention angles (0 = 3 o'clock, anticlockwise,
  0..π = top half on screen).

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

- Full WEPF rules (§8 list) — first candidate for R6, as B1 (whole set in one
  release); pairs naturally with a foul-risk term in the AI utility.
- AI spin selection and a spin-aware leave model (the leave estimate assumes
  a plain rolling strike).
- Safety quality: safeties are still "roll at the nearest ball" — no
  assessment of what the safety leaves the opponent.
- Larger-N confirmations: `--breaks 30` for finding §6.8, `--aigame 20+`
  (including a greed-0 baseline) for §6.9.
- Spin-inclusive break in actual AI games (the AIs still break plain).
- **Graphics Pass 3 — IN PROGRESS (decision 1C + 2A, signed off).** Direction
  ModernGL (Maker wants a show-off build; spectacle outranks minimal-dependency
  fidelity). Builds on the tangent-true geometry + cushion_path's layered
  `draw_table` as its baseline. **No construction drawing is coming** — the R6.1
  geometry is final and authoritative, so the deferred 1B stage builds to the
  existing tangent-true loop, not to a spec sheet.
  - **DONE — Increment 1 (R6.2):** renderer split (offscreen frame as the single
    source), lazy-moderngl `GLPostProcessor`, `--classic` + `--smoke-gl` gates,
    passthrough. Preceded by the headless EGL feasibility probe (§6.12).
  - **DONE — Increment 2 (R6.3):** GL-only 2× SSAA + bloom (threshold/knee →
    separable Gaussian → additive composite), interactive `--gl`. Presets
    SUBTLE/BALANCED/ARCADE; default BALANCED.
  - **REMOVED at R6.10** (Maker's call, after R6.8/R6.9's fixes didn't resolve
    the interactive black-screen bug on real hardware): everything Increments
    1 and 2 built -- `GLPostProcessor`, the GL pixel-probes, `smoke_gl()`,
    bloom, SSAA render-scale, `--gl`/`--smoke-gl`/`--classic` -- is gone.
    `moderngl` is no longer a dependency. See the R6.10 finding for the full
    removal record. The entries above stay as history of what was built and
    why; nothing below this point in Increment 1/2's description is still
    true of the current codebase.
  - **Increment 3 — fullscreen + hand-rolled tabbed control panel** (decision
    signed off). Right-hand side panel; table fills the space to its left,
    fitted by the largest uniform `S` that preserves the exact 2:1 table
    (same `S` for x and y, so dimensions can't distort — this is the whole
    reason it's safe).
    **DONE — 3a (R6.4, Maker-signed-off):** resizable/maximisable window +
    F11 fullscreen toggle, `fit_to_region()` (pure, dependency-free), GL scene
    with a placeholder empty right-hand panel composited on top — geometry,
    scaling and compositing all proven before any widgets. Two real bugs
    found and fixed along the way (see finding §6.15): `VIDEORESIZE` wasn't
    actually resizing the window surface, and F11 was reading the desktop
    resolution too late to get a real value. Headless guard verified not just
    by the pixel-probe selftest but by a raw byte comparison of `--snap`
    output against the R6.1 baseline (identical). **Known follow-up for 3b:**
    the HUD text (bottom-left readout, aim icon) scales with the fit but its
    font has a legibility floor (`max(8, int(14·RS·FS))`); at small window
    sizes the floor wins before the table has shrunk as far, and the text
    crowds the aim icon (seen in a signed-off-anyway capture at 700×500).
    Not a defect in 3a's own scope, but 3b should either move the HUD into
    the panel (likely right, since the panel is the natural home for status
    text) or give it its own independent scale floor.
    **DONE — 3b (R6.5, Maker-signed-off):**
    hand-rolled immediate-mode widgets (`Slider`/`Button`/`SpinPad`/
    `TabStrip`, no new dependency) wired into the real panel rect from 3a.
    Every control binds DIRECTLY to the same live variable its mirrored key
    already mutates — no shadow state. Tabs: **Shot** (power slider,
    cue-angle fine-tune slider ±15° additive on mouse aim, 2D spin pad
    clamped to the unit circle, Reset-spin, **Shoot** mirroring SPACE's
    exact guard via `shoot_enabled()`) · **Table** (cushion elasticity /
    roll decel / ball radius sliders — ball radius greyed outside SANDBOX,
    matching the B key — cue-size toggle) · **Game** (mode-cycle, rack-up,
    overlay-toggle, live-labelled). Panel stayed at 260px per Maker's call.
    HUD-crowding fix: the icon gets its own independent size floor
    (`hud_icon_x()`), per Maker's call, rather than moving the HUD into the
    panel. **Headless guard — a real near-miss, caught and fixed (see
    finding, new R6.5 entry):** the icon fix initially ran unconditionally
    and broke smoke's byte-identical invariant on a long AI-vs-AI status
    string; fixed by branching the icon formula on `smoke` so the headless
    path is provably untouched. Selftest 28→33. Validated: full chain green
    plus a scripted interactive session (tab switch, slider drag, spin-pad
    drag, Shoot click) captured and eyeballed.
  - **Increment 4 — effect passes**, staged one at a time (Maker's call),
    in this order:
    **DONE — 4a (R6.7, BUILT, pending Maker's own eyeball sign-off):**
    spectator motion trails. All balls while moving, explicit
    position-history fading ribbon (not an accumulation blend), always on
    in every mode. Built classic-only now (was classic+GL; GL removed at
    R6.10 -- see the R6.7 finding for the original build record, unaffected
    by the removal since trails never depended on GL).
    **NEXT — 4b (not started):** pot "swallow" animation into the recessed
    cups, cup-glow lift.
    **THEN — 4c:** slow-mo black with a glow ramp (folds in old candidate D)
    -- needs its own decision brief (trigger condition, what "black" means
    -- fade/vignette/letterbox -- weren't specified in the original
    candidate list). **Rethink needed, not just flag:** the original brief
    said "bloom ramp", but bloom no longer exists anywhere in the codebase
    (R6.10 removed it along with the rest of GL) -- this isn't a GL-only
    feature waiting on a parked bug anymore, it needs an actual classic-
    renderer equivalent decided at brief time (a plain pygame glow/blend
    effect achieves a similar look without a GL pipeline; scope it fresh
    rather than assuming the old GL design carries over).
    **THEN — 4d:** colour-grade / vignette / cloth-light (ambient) falloff.
  - **DEAD — 1B GL-native renderer** ("pass 5"): was deferred, now moot.
    GL was removed entirely at R6.10 (Maker's call, after two candidate
    fixes failed to resolve a real black-screen bug on real hardware) --
    per-pixel shaded ball spheres, MSAA geometry, and cloth nap would all
    need a GL pipeline that no longer exists in this codebase. Not
    "deferred until dependencies clear" anymore; would need its own fresh
    decision brief and a reason to reintroduce GL at all before this is
    worth resurrecting.
  - Doctrine: every render feature gets a pixel-probe assertion (finding §6.10
    -- written when GL still existed; the principle still applies to any
    future render feature, GL or not). **Byte-identical
    invariant (from Increment 3 on): headless `--snap`/`--smoke` render the
    scene-only at the R6.1 framing and must stay byte-identical to the R6.1
    baseline; the interactive window may add UI chrome.** Graphics constants of
    interest live in cushion_path.py (COL_BAIZE/COL_WOOD/COL_BG, RAIL_WIDTH,
    FRAME_OFFSET, KNUCKLE_R, nose highlight + throat-wrap params) plus hustler's
    sprite highlight blends `0.7/0.95`, shadow alpha `70`, and the bloom presets
    at the top of the GL section.
- Spectator polish ideas: pot/score banner, shot-by-shot commentary line
  (the shot dict now carries `u` and `leave` — ready-made commentary
  material), slow-mo on the black.
- American table preset (specs on file from the calibration research) — one
  CFG dict away if ever wanted.

## 10. Re-entry / continuation prompt

Paste into a fresh session along with this file, `hustler.py` and `cushion_path.py`:

> We are resuming **Hustler**, my UK blackball pool sandbox (pygame + pymunk,
> two files — `hustler.py` + `cushion_path.py` — attached with this handoff).
> Read HANDOFF_HUSTLER.md fully — especially the working agreement (§2), engine
> facts (§3), and findings (§6) — before proposing anything. The validation
> chain is mandatory for every change: py_compile → --selftest → --batch →
> --smoke (+ --snap for screenshots). One new selftest assertion per feature,
> UK spelling, AI behaviour stays emergent (parameters, never scripts).
> Confirm the chain passes on the attached files first (selftest 32/32, all
> dependency-free; cushion_path.py standalone green; classic --snap must stay
> byte-identical to the R6.1 baseline). **GL was tried (R6.2-R6.9: renderer
> split, SSAA, bloom, fullscreen panel) and REMOVED ENTIRELY at R6.10** after
> two candidate fixes failed to resolve a black screen on my real hardware
> (nix5) — classic is the only renderer now, `moderngl` is not a dependency,
> don't reintroduce GL without me asking for it explicitly. The hand-rolled
> tabbed control panel (R6.5: Slider/Button/SpinPad/TabStrip/Dial,
> Maker-signed-off), the HUD-only aim fix (R6.6: mouse-aim removed, rotating
> angle dial, Maker-signed-off), and spectator motion trails (R6.7: all balls
> while moving, fading ribbon, classic-only now — Maker-signed-off) are all
> live and working. **Increment 4b (pot "swallow" animation + cup-glow) is
> next, not yet started** — needs its own decision brief before building.
> After that: **4c** (slow-mo black with a glow effect — the original brief
> said "bloom ramp" but bloom is gone, so this needs a genuine classic-
> renderer redesign, not just a port) and **4d** (colour-grade/vignette/
> cloth falloff). The table geometry is FINAL — no construction drawing is
> coming. R6 GAMEPLAY candidates queue behind the effect passes: (a) full
> WEPF rules + foul-risk term; (b) AI spin selection + spin-aware leave;
> (c) safety quality term; (d) any spectator polish not absorbed by the
> passes; (e) larger-N studies to confirm §6.8 and §6.9. I sign off on
> briefs before you build.

**Validation snapshot at handoff:** selftest **32/32**, all dependency-free
(25 physics/logic/fit-to-region + 7 Increment-3b/3.6/4a widget-and-effect
primitives: slider round-trip, spin-pad unit-circle clamp, Shoot-guard
mirror, HUD-icon-anchor, rotate_vector round-trip, dial_angle inverse,
trail_dot_style tapering) · drill **18/18** (tangent-true, corners 81.3 mm /
middles 100 mm) · containment 0 escapes over batch-30 (PHYS_DT 480 Hz +
per-sub-step capture) · cushion_path.py standalone green · classic render
**byte-identical to the R6.1 baseline** (verified by raw byte comparison,
re-confirmed after the R6.10 GL removal specifically, since that was the
largest structural change to `run_gui` since the baseline was set) · panel/
dial/trails exercised via scripted interactive sessions captured to PNG and
eyeballed by this instance — live two-way sync confirmed throughout (slider
drag moves the same figure the key changes; dial drag sets the exact angle
`Sim.strike` fires with; trail tapers and vanishes in step with the
`STOP_SPEED` threshold the Shoot-button guard also uses) · break rattle
finding preserved (0.50 pots/break at the smash vs legacy 1.10).
USE_TANGENT_CUSHIONS retained for legacy A/B.

*Handoff updated July 2026 (R6.10 — GL removed entirely, Maker's call, after
R6.8's EGL-forcing-scope fix and R6.9's surface-format-conversion fix both
failed to resolve a real black-screen bug on Iain's own hardware (nix5).
`GLPostProcessor`, `GLUnavailable`, the three GL pixel-probes, `smoke_gl()`,
bloom, SSAA render-scale, and the `--gl`/`--smoke-gl`/`--classic` flags are
gone; `moderngl` is no longer a dependency, optional or otherwise. Selftest
35→32 (the three GL pixel-probes removed, nothing else touched). Full chain
re-validated green including a fresh byte-identical `--snap` comparison
against the original R6.1 baseline. R6.7 (spectator motion trails) is
unaffected — it was already classic-capable — and still awaits Maker's
eyeball. R6.10's finding entry has the full removal record and a rethink
note for Increment 4c, whose original "bloom ramp" brief no longer has
bloom to ramp. Good hunting, next instance.)*
