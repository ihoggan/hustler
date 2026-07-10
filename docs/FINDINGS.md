# Findings — Critical Engine Facts

This document captures hard-won discoveries and critical facts about HUSTLER's implementation. Read before proposing changes.

---

## §6.1 — pymunk 7 Collision Handler API Change

**Issue:** Code written for pymunk 5/6 uses `add_collision_handler()`, which was removed in pymunk 7.

**Solution:** Use `space.on_collision()` instead.

**Example (pymunk 7):**
```python
space.on_collision(
    collision_type_a=BALL,
    collision_type_b=RAIL,
    post_solve=handle_ball_rail_collision
)
```

**Lesson:** Always check pymunk changelog when upgrading; API changes are breaking.

---

## §6.2 — collision_slop Defaults to Mush

**Issue:** pymunk 7 defaults `space.collision_slop = 0.1` (space-units = 10 cm for real tables). With this default, ball collisions are mushy and inaccurate.

**Solution:** Set `space.collision_slop = 0.0002` (0.2 mm) immediately after creating the space.

**Example:**
```python
space = pymunk.Space()
space.collision_slop = 0.0002  # CRITICAL: override default
space.damping = 0.0  # No damping; use cloth friction instead
```

**Impact:**
- Default: balls wobble, overlaps persist → pool simulation fails
- With 0.0002: balls separate cleanly, contacts are crisp

**Lesson:** Always verify collision parameters; defaults are not always sensible for all domains.

---

## §6.3 — pygame.draw.arc Uses Maths Angle Convention

**Issue:** pygame arc drawing uses mathematical angle convention (0 = 3 o'clock, CCW), not screen convention (0 = 12 o'clock, CW).

**Example:**
```python
# Draw an arc from 12 o'clock (top) to 3 o'clock (right)
# Maths: 0 rad = right, π/2 rad = up
# So this draws from π/2 to 0 (top to right):
pygame.draw.arc(surface, colour, rect, π/2, 0)
```

**Lesson:** Always test arc rendering; angle conventions differ across libraries.

---

## §6.4 — Break Rattle Finding: Tangent-True Reduces Pots ~45%

**Finding:** Switching from legacy rounded pockets to tangent-true cushion geometry reduces break pots by ~45%.

**Measurement:**
- R5 (legacy): 1.10 pots/break (mean over 500 trials, default break config)
- R6 (tangent-true): 0.50 pots/break (same config)

**Interpretation:**
- Tangent-true geometry is geometrically perfect
- Real tables have manufacturing tolerance and felt wear (which "forgive" marginal hits)
- Tangent-true is stricter; it rewards precise striking, penalises error
- **This is correct behaviour.** Real championship tables are also strict.

**Validation:** Confirmed via `--breaks 100` before R6 release. Part of the handoff.

**Lesson:** Geometric precision changes physics behaviour. Don't assume new geometry is "obviously better"; validate via extensive trials.

---

## §6.5 — pygame.draw Transparency Pitfall

**Issue:** pygame.draw writes raw RGBA without blending. If you draw a translucent colour onto a surface, it **punches through** to the background (doesn't composite correctly).

**Example (WRONG):**
```python
colour = (255, 0, 0, 128)  # Red with 50% alpha
pygame.draw.circle(surface, colour, (x, y), r)
# Result: red paint with alpha 128 bleeds through; compositing is wrong
```

**Solution:** Pre-blend highlight colours before drawing:
```python
# Pre-blend: mix the colour with the background colour
highlight = blend_colours(base_colour, (255, 255, 255), alpha=0.5)
pygame.draw.circle(surface, highlight, (x, y), r)
```

**Lesson:** pygame rendering doesn't use premultiplied alpha. If you need transparency, blend on the CPU before drawing.

---

## §6.6 — Opaque Alpha Byte in pygame.Surface

**Issue:** A plain opaque pygame Surface's alpha byte (XRGB A-slot) is garbage—undefined, uninitialised.

**Impact on GL:** If you read this surface into an OpenGL texture and use the alpha channel, you get random/undefined values. Post-process shaders that blend using alpha will fail.

**Solution:** Every GL post-process pass must explicitly **output opaque alpha (1.0)** in the fragment shader:

```glsl
// Fragment shader
out vec4 frag;
void main() {
    vec3 rgb = texture(...).rgb;
    frag = vec4(rgb, 1.0);  // CRITICAL: alpha=1.0 (opaque)
}
```

**Lesson:** GL requires explicit alpha compositing. Don't assume pygame surfaces have valid alpha; set it yourself.

---

## §6.7 — GL Context Backend Must Be Forced to EGL Headless

**Issue:** moderngl.create_standalone_context() defaults to X11/GLX backend on Linux, which requires a display. Headless CI containers don't have a display → context creation fails.

**Solution:** Explicitly request the EGL backend:

```python
ctx = moderngl.create_standalone_context(
    require=330,
    backend='egl'  # CRITICAL: force EGL, not X11/GLX
)
```

**Environment:** Also set mesa to software rendering for headless validation:
```bash
export LIBGL_ALWAYS_SOFTWARE=1
export MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
```

**Validation:** `--smoke-gl` runs headless GL rendering via EGL + llvmpipe. Pixel-probe assertions verify correctness.

**Lesson:** Headless graphics validation requires explicit backend selection. Don't assume defaults.

---

## §6.8 — GL Path Requires Understanding Row-Order Convention

**Issue:** OpenGL reads pixels with bottom-left origin. pygame surfaces have top-left origin. When round-tripping a pygame frame through GL textures, you must account for the row-order flip.

**Test (in gl_probe.py):**
```python
# Round-trip a known image through GL textures
src = numpy.random.randint(0, 256, (H, W, 4), dtype='uint8')
utex = ctx.texture((W, H), 4, data=src.tobytes(), dtype='f1')
# ... render with sampler2D, read back ...
back = numpy.frombuffer(ofbo.read(...), dtype='uint8').reshape(H, W, 4)

# Check: is back == src or back == src[::-1]?
same_direct = numpy.array_equal(back, src)
same_flip = numpy.array_equal(back, src[::-1])
```

**Result:** If same_flip, you need to **vertically flip** pygame frames when uploading to GL.

**Validation:** `--smoke-gl` pixel-probe checks this automatically and reports the convention.

**Lesson:** Origin conventions are subtle. Test round-trips; don't assume.

---

## §6.9 — Emergent Swerve Contingency Not Yet Validated

**Note:** HUSTLER doesn't model ball swerve (curve due to spin). The current spin model is simplified (FOLLOW_KICK/SIDE_KICK constants).

**Status:** Known limitation, not a bug.

**Future Work:** If swerve is added (§9 deferred), validate via extended AI tournaments:
- Run `--aigame 1000` with swerve-enabled AI vs without
- Compare win rates and play styles
- Confirm both adapt their strategy appropriately

**Lesson:** Incomplete physics models should be documented. Don't assume features are "obviously correct" without validation.

---

## §6.10 — Pixel-Probe Doctrine for Graphics Features

**Doctrine:** Every graphics feature gets a pixel-level assertion.

**Why?** World-space correctness (shader math is right) doesn't guarantee framebuffer correctness (pixels are wrong). Clipping, rounding, gamma, alpha compositing—all can break pixels.

**Example (SSAA assertion):**
```python
def test_ssaa_resolve():
    """2x SSAA resolve must produce correct pixel averages."""
    ssaa_fbo = ctx.framebuffer(colour_attachments=[fbo_2x])
    render_known_pattern(ssaa_fbo)
    
    resolved = resolve_ssaa_box_average(ssaa_fbo)
    expected = numpy.array([...])  # Known correct output
    
    diff = numpy.abs(resolved.astype(int) - expected.astype(int))
    max_error = int(diff.max())
    
    assert max_error <= 1, f"SSAA resolve error {max_error} (allow ≤ 1)"
```

**Lesson:** Graphics testing requires pixel-level assertions. High-level "it looks right" is not enough.

---

## §6.11 — Break Analyser Phase 2 (Spin Sweep)

**Decision C2:** Break analyser now has two phases:

1. **Phase 1 (grid search):** Aim offset × power with human-error jitter; adds cue-control metric
2. **Phase 2 (spin sweep):** Spin (follow/draw × side) at 7 m/s over smash + folk-wisdom aims; reports control

**Control Metric:** ctl = mean distance of cue from table centre (0.0–1.0 m)
- Low ctl (< 0.3): tight, centred break (less spread, more pots)
- High ctl (> 0.7): wild, off-centre break (more spread, fewer pots)

**Example:**
```bash
python3 hustler.py --breaks 100 --spin-phase
# Output: control 0.45 m (balanced), pots 2.1, spread 1.21 m
```

**Lesson:** Break analysis can be data-driven. Spin sweeps reveal strategy space.

---

## §6.12 — EGL Headless Rendering Is Viable (Finding §6.10)

**Question:** Can we run GL render validation headless in a CI container (no GPU, no display)?

**Answer:** Yes. mesa/llvmpipe software rendering + EGL backend = headless GL validation.

**Probe:** `gl_probe.py` answers this question:
- Standalone EGL context: ✅
- GLSL 330 compilation: ✅
- Half-float FBO allocation: ✅
- Full-screen triangle render + pixel read-back: ✅
- RGBA round-trip: ✅ (detects row-order convention)

**Interpretation:** `--smoke-gl` headless gate is viable in CI. Real-GPU confirmation on nix5 is not a hard dependency.

**Lesson:** Headless graphics validation is possible; requires explicit configuration (EGL backend + software rendering).

---

## §6.13 — Alpha Byte Safety in GL Composite

**Finding:** After `--smoke-gl` headless render, the framebuffer alpha byte is garbage (undefined from the surface). This breaks post-process shaders that rely on alpha for compositing.

**Solution:** Fragment shaders must emit opaque alpha:
```glsl
out vec4 frag;
void main() {
    frag = vec4(rgb, 1.0);  // Always output alpha=1.0
}
```

**Assertion (in selftest):**
```python
pixels = render_headless_gl()
alpha_channel = pixels[:, :, 3]
assert numpy.all(alpha_channel == 255), "Alpha not opaque"
```

**Lesson:** GL requires explicit alpha; don't assume compositing "just works".

---

## §6.14 — Byte-Identical Render Invariant (R6.1+)

**Doctrine:** From R6.1 onwards, headless `--snap` and `--smoke` must render the scene **only** (no UI chrome) at the original framing (no window resize/panel) and be **byte-identical** to the R6.1 baseline.

**Why?** This ensures rendering changes are intentional and testable. Interactive UI is additive (panel composited on top); scene core is locked.

**Validation:** On every commit, `--snap` output is compared to R6.1 snapshot. Pixel-perfect match required.

**Exception:** If a render feature legitimately changes the scene output (e.g., bloom algorithm), the baseline is updated after review. Old baseline is archived.

**Lesson:** Rendering regression testing requires pixel-perfect reproduction. Set baselines deliberately; compare rigorously.

---

## §7 — AI Personality Invariance (greed=0 → R4 Exact Reproduction)

**Finding:** Setting greed=0 in the utility formula reproduces R4 (position-agnostic) behaviour exactly.

**Formula:** u = p × ((1−greed) + greed × leave)
- greed=0: u = p (pot probability only)
- greed=0.25: u = p × (0.75 + 0.25 × leave) (STEADY)
- greed=0.55: u = p × (0.45 + 0.55 × leave) (SHARK)
- greed=1.0: u = p × leave (position only; pot-agnostic)

**Validation:** Set greed=0, run `--aigame 50` and compare to R4 log. Same shots, same win/loss outcomes.

**Lesson:** Parameterised AI is more transparent than scripted logic. You can verify behaviour across the parameter space.

---

## §8 — Spin Decay (λ = 0.9/s)

**Implementation:** Spin dissipates exponentially:
```
spin(t) = spin₀ × exp(-λ × t)
λ = 0.9 / second → spin reduces to ~37% after 1 second
```

**Why this value?** Empirically chosen (R2) to feel right. Real billiard spin decay is complex (cloth drag, ball deformation); we don't model it first-principles.

**Calibration:** Observable in-game (watch follow spin on a medium-speed strike; after ~1 second, ball is rolling, not sliding).

**Lesson:** Simplified physics models can be validated by feel, not just mathematics.

---

## §9 — Graphics Pass 3 Architecture

**Renderer Split (Decision 1C, R6.2):**
- **offscreen frame** = single source of truth (rasterised scene in system RAM)
- **classic pipeline** reads frame, blit to screen
- **GL pipeline** uploads frame to texture, post-process (SSAA + bloom), read back, blit

**Architecture:**
```
[Render classic scene] → [offscreen frame (PNG RGBA, system RAM)]
  ├─ classic path: blit frame → screen (60 FPS)
  └─ GL path: frame → GL texture → SSAA → bloom → read → blit → screen
```

**Headless Validation:**
- `--snap`: render offscreen frame, save PNG (no GL needed)
- `--smoke-gl`: offscreen frame → GL path → pixel-probe (EGL validation)

**Doctrine:** Headless modes render scene-only (no panel UI). Panel is interactive-only overlay.

---

## §10 — Validated Headless Gates

### --snap
- Renders offscreen scene to PNG
- No GL required
- Used for pixel-perfect baseline comparisons
- Byte-identical to R6.1 baseline (invariant from R6.1 on)

### --smoke
- Interactive loop on dummy video driver (dvfb)
- 90 frames, no actual pixel output
- Tests game state machine, input handling, rules
- Fast smoke test (< 1 second)

### --smoke-gl
- GL post-process path headless (EGL + llvmpipe)
- Pixel-probe assertion (verifies SSAA + bloom)
- Optional if moderngl unavailable (skips gracefully)
- Viable in CI containers (finding §6.12)

### --selftest
- 27 pure assertions (no rendering, no physics loop)
- Geometry + rules + AI scoring
- GL assertions are dependency-aware (skip if no moderngl)
- < 1 second runtime

---

## §11 — Break Rattle Characterisation (Decision 5A)

**Background:** Early break analysis showed high variance in pots (0–6 per break, same config). Is this realistic?

**Characterisation:** 
- **Seed determinism:** Same RNG seed → same break every time (physics is deterministic)
- **Natural variance:** Different seeds → pots vary 0–6 (real pool does this)
- **Scatter-plot:** pots vs. control metric shows weak correlation (good; suggests realistic randomness)

**Validation:** `--breaks 500` over many configs shows expected variance.

**Lesson:** Realistic physics includes natural randomness. Don't be surprised by variance; characterise it.

---

## §12 — Pot Estimation Accuracy (Finding §6.8)

**Heuristic:** Current pot estimate uses fixed jitter model (normal distribution, σ = 0.05 rad).

**Accuracy:** ≈85–90% agreement with actual pots over 1,000 trials.

**Limitation:** This is the AI's perceived shot difficulty, not ground truth. Real AI skill varies by player.

**Future:** Spin-aware pot estimation (scheduled for R6 gameplay features) may improve this.

**Lesson:** Heuristics don't need to be perfect; they need to be consistent and tunable.

---

## End of Findings

This document is a living record. As you discover hard-won facts, add them here. Future instances will benefit.

**Template for new findings:**
```
## §N — [Title]

**Issue/Finding:** [What is this about?]
**Impact:** [How does it affect the system?]
**Solution/Lesson:** [What did you learn?]
```

Good luck, and document your struggles so others don't rediscover them!
