# HANDOFF — HUSTLER (UK Pool Physics Sandbox)

**Status:** Banked at R6.3 (Graphics Pass 3 Increments 1–2 — GL post-process renderer: 2× SSAA + bloom). Healthy. Full validation chain green (27/27 selftest, classic render byte-identical to R6.1 baseline). **Increment 3 (fullscreen + hand-rolled tabbed control panel + Shoot button) is signed off and ready to build — start with 3a.**
**Files:** `hustler.py` (~2,570 lines) **+ `cushion_path.py`** (tangent-true cushion-nose geometry module) — single project, two files. Python 3.12, pygame 2.6.1 + pymunk 7.3.0; **moderngl 5.12 optional** (only the GL render path needs it).
**Install:** `pip install pygame pymunk` (add `--break-system-packages` on system Python). For the GL renderer: `pip install moderngl` — optional; the core chain (`--selftest`/`--batch`/`--smoke`) has zero new dependencies and runs without it.
**Platform:** Developed/validated headless on Ubuntu; runs anywhere pygame does. GL path validated headless in-container on Mesa/llvmpipe via EGL (see §6.12); nix5 is the real-GPU confirmation, not a requirement.
**Run note:** `cushion_path.py` must sit alongside `hustler.py` (it is imported as `cushion_geo`). Its own standalone selftest (`python3 cushion_path.py`) validates the reference 6ft/89-100 spec and stays green independently. Table geometry is FINAL as of R6.1 — no construction drawing is forthcoming; the tangent-true loop is the authoritative source of truth.

---

## 1. What this project is

A UK blackball pool physics sandbox grown into a playable game with a utility AI,
built to answer the original question: *how do angles, spin, and the break actually
work?* The long-term destination is AI-vs-AI spectating with emergent behaviour.

## 2. Working agreement (non-negotiable, carried from AISpecOps/HexWars)

- Decisions brief with genuine forks → explicit sign-off → build → validate.
- Validation chain, every release, even graphics-only changes:
  `py_compile` → `--selftest` → `--batch N` → `--smoke` (+ `--snap` for screenshots).
  GL render changes add `--smoke-gl` (headless GL gate) and pixel-probe on `--snap`.
- One selftest assertion per feature. Currently 27 (24 physics/logic + 3 GL render).
  The 3 GL assertions are dependency-aware: they SKIP (not fail) if moderngl/EGL is
  absent, so the core chain stays green on a stripped container.
- UK spelling throughout. Emergent AI behaviour protected — parameters and scores,
  never scripts. Transparent bug ownership: failures are logged in this doc.

## 3. Architecture (decision 1C — hybrid)

- **Simulation:** pymunk in REAL UNITS (metres/kg/seconds). Rendering scales by
  `PX_PER_M` at draw time only.
- **Geometry layer:** pure maths, no pymunk import above its section — ghost ball,
  ray/corridor solves, pot assessment, one-bounce prediction. Directly unit-tested.
- **Rules layer:** `Game` class — rules-lite blackball state machine.
- **AI layer:** `PoolAI` — geometric utility AI (see §7).
- **GUI:** three modes on `M`: SANDBOX / YOU vs AI / AI vs AI spectator.
- **Headless modes:** `--selftest`, `--batch N`, `--breaks N` (break analyser),
  `--aigame N` (AI tournaments), `--smoke`, `--snap FILE`, `--smoke-gl` (GL render
  gate). Interactive renderer chosen by `--gl` (GL: SSAA + bloom) / `--classic`
  (default; overrides `--gl`).

### Critical engine facts (hard-won, do not rediscover)

- **pymunk 7 removed `add_collision_handler`** — use
  `space.on_collision(collision_type_a=, collision_type_b=, post_solve=fn)`.
- **`space.collision_slop` defaults to 0.1 space-units = 10 cm in metre units.**
  Must be set (we use 0.0002) or collisions are mush.
- pygame.draw writes raw RGBA without blending — translucent paint on a sprite
  punches through to the background when blitted. Pre-blend highlight colours.
- pygame.draw.arc uses maths-convention angles (0 = 3 o'clock, anticlockwise,
  0..π = top half on screen).
- **GL context: force `backend='egl'`** on `moderngl.create_standalone_context`
  — glcontext defaults to X11/GLX and dies headless (see §6.12).
- **A plain opaque pygame Surface's alpha byte is garbage** (the XRGB X-slot);
  every GL post-process pass must output opaque alpha `vec4(rgb, 1.0)` (see §6.13).

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
  - **NEXT — Increment 3 (SIGNED OFF, not started): fullscreen + hand-rolled
    tabbed control panel.** Right-hand side panel; table fills the space to its
    left, fitted by the largest uniform `S` that preserves the exact 2:1 table
    (same `S` for x and y, so dimensions can't distort — this is the whole
    reason it's safe). Resizable/maximisable window + F11 toggle, one
    fit-to-region routine. Table+balls drawn through the GL SSAA/bloom path;
    the **panel composited on top afterwards** (crisp UI, no bloom on handles).
    Every control MIRRORS the existing keys and stays in sync — nothing lost.
    Hand-rolled immediate-mode widgets (slider / 2D spin pad / button / tab
    strip), NO new dependency (pygame_gui rejected — keep single-file+module
    discipline). Tabs: **Shot** (power slider, cue-angle slider, 2D spin pad,
    **Shoot** button mirroring SPACE with the same at-rest/human-turn guard and
    greying out when disallowed, reset-spin) · **Table** (cushion elasticity,
    rolling resistance, ball radius, cue-size toggle — mirror E/F/B/K) · **Game**
    (mode selector, rack up, overlay toggle). Spin pad: drag the contact point
    in a cue-ball circle, vertical = follow/draw, horizontal = side, clamped to
    the unit circle, mapped to the existing ±1.0 spin params; mouse still sets
    coarse aim, angle slider fine-tunes. **Staging (signed off): 3a** = resizable
    /F11 window + fit-to-region + GL scene with a placeholder empty panel
    composited on top (proves geometry/scaling/compositing, minimal UI logic);
    **3b** = widget toolkit + tabs + spin pad + Shoot + control wiring.
    **Headless guard (signed off):** `--snap`/`--smoke`/`--smoke-gl` keep
    rendering the BARE SCENE at the original R6.1 framing (no panel, no resize) —
    the panel is an interactive-only overlay — so the byte-identical invariant
    holds unchanged. Validation: dep-free selftest assertions for the pure
    functions (fit-to-region keeps 2:1 + fits + reserves panel across several
    window sizes; slider value↔param round-trips; spin-pad contact↔(follow,side)
    mapping; Shoot-enabled guard mirrors the SPACE condition). Interactive UI
    eyeballed via a saved full-window capture.
  - **Increment 4 — effect passes** (was "candidate Increment 3"): spectator
    motion trails · slow-mo black with bloom ramp (folds in old candidate D) ·
    pot "swallow" animation into the recessed cups (the cup-glow lift lives
    here) · colour-grade / vignette / cloth-light (ambient) falloff.
  - **DEFERRED — 1B GL-native renderer** ("pass 5"): per-pixel shaded ball
    spheres, MSAA geometry, cloth nap. Multi-session rebuild; now targets the
    existing geometry directly (drawing dependency void).
  - Doctrine: every render feature gets a pixel-probe assertion (finding §6.10),
    dependency-aware so the core chain skips GL cleanly. **Byte-identical
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

Paste into a fresh session along with this file and `hustler.py`:

> We are resuming **Hustler**, my UK blackball pool sandbox (pygame + pymunk,
> two files — `hustler.py` + `cushion_path.py` — attached with this handoff).
> Read HANDOFF_HUSTLER.md fully — especially the working agreement (§2), engine
> facts (§3), and findings (§6) — before proposing anything. The validation
> chain is mandatory for every change: py_compile → --selftest → --batch →
> --smoke, plus --smoke-gl and a --snap pixel-probe for any GL render change.
> One new selftest assertion per feature, UK spelling, AI behaviour stays
> emergent (parameters, never scripts). Confirm the chain passes on the attached
> files first (selftest 27/27 — 24 physics/logic + 3 GL, dependency-aware;
> cushion_path.py standalone green; classic --snap must stay byte-identical to
> the R6.1 baseline). moderngl is optional and lazily imported; the GL path is
> validated headless via EGL/llvmpipe in-container (finding §6.12).
> **Graphics Pass 3 is in progress (1C + 2A, signed off).** Increments 1 (R6.2:
> renderer split, --classic/--smoke-gl, passthrough) and 2 (R6.3: GL-only 2×
> SSAA + bloom, interactive --gl) are DONE and banked. The table geometry is
> FINAL — no construction drawing is coming, so 1B builds to the existing
> tangent-true loop. **NEXT, signed off and ready to build: Increment 3 —
> fullscreen + hand-rolled tabbed control panel** (full brief in §9). Build
> **3a first**: a resizable/F11 window + a fit-to-region routine (largest
> uniform S that keeps the exact 2:1 table, reserving a right-hand panel) + the
> GL scene with a placeholder empty panel composited on top — proving geometry,
> scaling and compositing before any widgets. Then **3b**: hand-rolled
> immediate-mode widgets (slider / 2D spin pad / button / tab strip — NO new
> dependency), tabs Shot / Table / Game, a **Shoot** button mirroring SPACE
> (same at-rest/human-turn guard, greys out when disallowed), and two-way
> key↔control sync. **Headless guard (signed off): --snap/--smoke/--smoke-gl
> render the BARE SCENE at the R6.1 framing (no panel, no resize) and must stay
> byte-identical to the R6.1 baseline** — the panel is interactive-only. Add
> dep-free selftest assertions for the pure functions (fit-to-region, slider
> value↔param, spin-pad contact↔(follow,side), Shoot-enabled guard). AFTER
> that, **Increment 4** = the effect passes (spectator trails, slow-mo black,
> pot swallow with cup-glow, colour-grade/vignette/cloth-falloff), then the
> deferred **1B** GL-native rebuild. Bloom is live-tunable via
> BLOOM_SUBTLE/BALANCED/ARCADE at the top of the GL section — I may want to
> dial it by eye. R6 GAMEPLAY candidates queue behind the graphics pass:
> (a) full WEPF rules + foul-risk term; (b) AI spin selection + spin-aware leave;
> (c) safety quality term; (d) any spectator polish not absorbed by the passes;
> (e) larger-N studies to confirm §6.8 and §6.9. I sign off on briefs before you
> build.

**Validation snapshot at handoff:** selftest **27/27** (24 physics/logic + 3 GL:
passthrough err 0, SSAA resolve box-average, bloom sanity) · drill **18/18**
(tangent-true, corners 81.3 mm / middles 100 mm) · containment 0 escapes over
~1,500 max-power stress strikes + batch-30 (PHYS_DT 480 Hz + per-sub-step
capture) · cushion_path.py standalone green · classic render **byte-identical to
R6.1 baseline** · GL path (EGL/llvmpipe): SSAA + BALANCED bloom, GL passthrough
full-frame pixel-exact to classic · break rattle finding preserved (0.50
pots/break at the smash vs legacy 1.10). USE_TANGENT_CUSHIONS retained for
legacy A/B.

*Handoff updated July 2026 (R6.3 banked — Graphics Pass 3 Increments 1–2: GL post-process renderer, 2× SSAA + bloom, dual-renderer with --classic/--gl/--smoke-gl. Table geometry final; no drawing forthcoming. Increment 3 — fullscreen + hand-rolled tabbed control panel + Shoot button — is SIGNED OFF and ready to build (3a first); effects demoted to Increment 4. Good hunting, next instance.)*
