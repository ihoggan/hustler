# Roadmap

## Current Status: R6.3 (Graphics Pass 3, Increments 1–2 Complete)

**Validation Snapshot:**
- ✅ Selftest: 27/27 (24 physics/logic + 3 GL, dependency-aware)
- ✅ Drill: 18/18 (tangent-true pot calibration)
- ✅ Containment: 0 escapes over stress testing
- ✅ Classic render: byte-identical to R6.1 baseline
- ✅ GL path (EGL/llvmpipe): SSAA + BALANCED bloom, pixel-exact to classic

---

## Graphics Pass 3 (In Progress)

All increments are signed off with detailed briefs. **Start with 3a.**

### Increment 3a — Resizable/F11 Window + Fit-to-Region (SIGNED OFF, READY)

**Problem:** Current window is fixed size; can't fullscreen or resize. Panel layout needs a fit-to-region algorithm.

**Solution:**
1. Implement resizable window with F11 toggle
2. Fit-to-region: largest uniform scale `S` that keeps exact 2:1 table, reserves right-hand panel
3. GL scene rendered through SSAA/bloom at fitted size
4. Placeholder empty panel composited on top (proves geometry, scaling, compositing)

**Scope:**
- Window management (resizable, F11, event handling)
- Pure function: `fit_to_region(window_w, window_h, panel_w) → S, table_x, table_y`
- GL scene rendered at fitted scale
- Panel composited on top (interactive-only, no blur/bloom)

**Acceptance Criteria:**
- ✅ Resizable window + F11 toggle working
- ✅ `fit_to_region` rounds-trip: `fit_to_region(1456, 728, 300) = (S, x, y)` such that table fits exactly
- ✅ GL SSAA/bloom rendered at fitted scale
- ✅ Panel placeholder composited without affecting bloom
- ✅ Headless modes (`--snap`, `--smoke`) still render scene-only at R6.1 framing (byte-identical)
- ✅ Selftest: `fit_to_region` assertions (several window sizes)

**Headless Guard:**
```bash
python3 hustler.py --snap /tmp/new.png
# Must be byte-identical to R6.1 baseline (no panel, no resize)
```

**Blocked By:** None. Ready to start.

**Status:** 🔴 **Not Started**

---

### Increment 3b — Hand-Rolled Widgets + Tabs + Shoot Button (SIGNED OFF, READY)

**Problem:** Panel placeholder is empty. Need UI controls (sliders, spin pad, tabs, Shoot button) with no new dependencies.

**Solution:**
1. Hand-rolled immediate-mode widgets: slider, 2D spin pad, button, tab strip (NO pygame_gui)
2. Three tabs: **Shot** (power, angle, spin, Shoot), **Table** (friction, elasticity, radius, cue toggle), **Game** (mode, rack up, overlay toggle)
3. **Shoot button** mirrors SPACE (same at-rest/human-turn guard, greyed out when disallowed)
4. Two-way key↔control sync (keyboard still works, changes update panel; panel changes trigger actions)

**Scope:**
- Slider widget (value ↔ parameter round-trip)
- 2D spin pad (drag in circle, vertical = follow/draw, horizontal = side, clamped to unit circle)
- Button widget (click-detection, disabled state)
- Tab strip (click tabs, show/hide panes)
- Shoot button logic (guards, state-driven greying)
- Key binding synchronisation

**Acceptance Criteria:**
- ✅ Slider: `slider_value_to_param(value, min, max) ↔ param_to_slider_value` round-trips
- ✅ Spin pad: `contact_point ↔ (follow, side)` round-trips, clamped to unit circle
- ✅ Shoot button: enabled iff `can_strike()` (at-rest AND human turn)
- ✅ Tabs: switching between Shot/Table/Game works
- ✅ Key bindings: UP/DOWN still adjust power; panel slider also adjusts power; both in sync
- ✅ No new dependencies (pure pygame)
- ✅ Headless modes still render scene-only (panel is interactive-only overlay)
- ✅ Selftest: `slider_value↔param`, `spin_pad_contact↔(follow,side)`, `Shoot_enabled_guard` assertions

**Interactive Testing:**
```bash
python3 hustler.py --gl
# [Interactive] Drag power slider; UP/DOWN key also changes it
# [Interactive] Click tabs (Shot/Table/Game); pane switches
# [Interactive] Drag spin pad; WASD keys also change spin
# [Interactive] Click Shoot button; same as SPACE (guards, greying)
```

**Blocked By:** Increment 3a (fit-to-region)

**Status:** 🔴 **Not Started**

---

### Increment 4 — Effect Passes (DEFERRED TO 3b+)

**Problem:** Table scene lacks visual polish. Break needs animation, slow-mo should feel dramatic, pots need feedback.

**Effects:**
1. **Spectator motion trails** — ghosted ball paths during auto-play (slow-mo only)
2. **Slow-mo on the black** — when black is potted, slow camera + bloom ramp (fade-to-white)
3. **Pot "swallow" animation** — ball descends into recessed cup (visual feedback), cup glow lifts
4. **Colour-grade / vignette** — ambient falloff on cloth (subtle centre-lit feel), subtle vignette
5. **Cloth-light ambient falloff** — brighten centre, darken edges

**Rationale:**
- Trails give visual weight to AI decisions (spectator mode)
- Slow-mo + bloom creates dramatic finish
- Swallow animation makes pots satisfying
- Lighting polish unifies the visual language

**Acceptance Criteria:**
- ✅ All effects optional (toggleable via game state or parameter)
- ✅ Headless modes (`--snap`, `--smoke`) render scene-only (effects are interactive-only polish)
- ✅ GL assertions for each effect (pixel-probe)
- ✅ Performance: 60 FPS maintained on nix5 (Core i7)

**Blocked By:** Increment 3b (panel UI complete)

**Status:** 🔴 **Not Started**

---

### Increment 1B — GL-Native Renderer (DEFERRED POST-3B+4)

**Problem:** Current GL path is a post-process on top of rasterised scene. Real spheres need per-pixel shading.

**Solution:**
1. Render balls as actual spheres (vertex shader projects, fragment shader computes normal, blinnphong shading)
2. MSAA geometry (4×MSAA for cushion edges, rails)
3. Per-ball material variation (surface finish, wear patterns)
4. Cloth nap (normal map on table, affects lighting)

**Scope:**
- Ball rendering: vertex buffers for unit sphere, per-instance position/radius, per-frame rotation
- Phong/PBR material model (specular, normal, roughness)
- Environment: basic lighting model (ambient + directional + specular highlights)
- Cloth material: normal map, roughness map

**Note:** This is a major rebuild (multiple sessions). Not blocking anything else. Targets a significant visual upgrade.

**Blocked By:** Increment 4 complete

**Status:** 🔮 **Deferred — Multi-Session Rebuild**

---

## R6 Gameplay (Queue Behind Graphics Pass 3)

After Graphics Pass 3 is complete, gameplay features can begin. All are signed off in the handoff.

### R6 Gameplay Feature 1: Full WEPF Rules + Foul-Risk Term

**Problem:** Current rules are simplified (pot-to-continue, scratch, black logic). Real blackball has safeties, fouls, penalty scoring.

**WEPF Rules to Add:**
1. **Safety:** Deliberately play a safety (no pot attempt); opponent's turn, no penalty
2. **Foul:** Miss pot legally → no penalty, opponent's turn
3. **Foul (illegal):** Fail to contact your colour first → opponent scores 1 point, re-spots cue
4. **Foul on black:** Hit black illegally (not your colour) → opponent scores 1 point
5. **Penalty scoring:** Accrue points, first to N wins

**AI Feature:** Foul-risk term in utility scoring
- Some positions are risky (high foul probability)
- AI learns to avoid these vs. safe shots
- Adds strategic depth (conservative vs. aggressive play)

**Acceptance Criteria:**
- ✅ WEPF rule engine updated (penalties, fouls, scoring)
- ✅ Selftest: foul detection, penalty calculation
- ✅ AI foul-risk term: `foul_risk ↔ pot_chance` trade-off
- ✅ `--aigame` tournaments with foul-risk show different play styles

**Blocked By:** Graphics Pass 3 Increments 3a, 3b, 4 complete

**Status:** 📋 **Signed Off, Queued**

---

### R6 Gameplay Feature 2: AI Spin Selection + Spin-Aware Leave

**Problem:** AI doesn't use spin strategically. Spin affects leave quality significantly.

**Solution:**
1. AI evaluates spin × (ball, pocket) combinations (follow/draw × side × 7 variants)
2. Spin-aware leave: post-pot position varies with spin; re-score leave for each spin variant
3. Utility now includes spin dimension: `u(ball, pocket, spin) = p × ((1−greed) + greed × leave(spin))`

**Impact:** AI play becomes more sophisticated; can set up tricky positions, use spin defensively.

**Acceptance Criteria:**
- ✅ Spin variants evaluated (say, 5×5 = 25 per shot)
- ✅ Spin-aware leave estimation (geometry function returns position grid)
- ✅ Selftest: spin-aware leave round-trip
- ✅ `--aigame 100` with spin AI vs without shows different strategies

**Blocked By:** Graphics Pass 3 + R6 Gameplay 1 complete

**Status:** 📋 **Signed Off, Queued**

---

### R6 Gameplay Feature 3: Safety Quality Term

**Problem:** AI makes safeties but doesn't score them; can't distinguish good vs. bad safety.

**Solution:**
1. Define safety quality: leaves cue ball in poor position for opponent (near wall, blocked)
2. Utility term: `safety_quality = 1 - opponent_leave_score`
3. AI becomes willing to play safeties if opponent position is sufficiently bad

**Acceptance Criteria:**
- ✅ Safety position scoring (geometry function)
- ✅ Selftest: `safety_quality ↔ opponent_options` validates
- ✅ `--aigame 100` with safety AI shows defensive play style

**Blocked By:** Graphics Pass 3 + R6 Gameplay 1 + 2 complete

**Status:** 📋 **Signed Off, Queued**

---

### R6 Gameplay Feature 4: Spectator Polish

**Problem:** AI-vs-AI spectator mode is functional but lacks personality.

**Ideas:**
1. **Shot commentary** (shot dict now carries `u`, `leave`, `pot_chance` — ready for use)
2. **Score banner** (displays running score, current turn, remaining balls)
3. **Replay system** (save/load game state, step through moves)
4. **Highlight reel** (auto-save dramatic moments: scratches, black pots, comebacks)

**Acceptance Criteria:**
- ✅ Commentary generated from shot dict (human-readable)
- ✅ Score banner rendered (HUD element)
- ✅ Replay system saves/loads game state

**Blocked By:** Graphics Pass 3 + R6 Gameplay 1, 2, 3 (polishing features, lower priority)

**Status:** 📋 **Signed Off, Queued** (polish, not core)

---

## Research & Validation (Post-Release)

### Research Topic 1: Extended Break Rattle Study (§6.4, §6.11)

**Goal:** Validate finding §6.4 over larger N; characterise break variance more thoroughly.

**Method:**
```bash
python3 hustler.py --breaks 500 > breaks_study.txt
# Aggregate stats: pots, scratches, black down, spread, control
# Correlate: does high control → fewer pots?
# Does spin phase affect variance?
```

**Hypothesis:** Tangent-true geometry is stricter (lower average pots), but variance is realistic (similar to real breaks).

**Status:** 📊 **Queued (low priority, long-tail research)**

---

### Research Topic 2: Contingency on Random Swerve (§6.9)

**Goal:** If swerve physics is added, validate via extended AI tournaments.

**Method:**
```bash
python3 hustler.py --aigame 1000 --with-swerve
python3 hustler.py --aigame 1000 --no-swerve
# Compare: win rates, shot strategies, play style
```

**Hypothesis:** Swerve awareness changes AI strategy (more risky shots, different spin usage).

**Status:** 🔮 **Deferred** (swerve not yet implemented)

---

### Research Topic 3: Larger-N Validation (§6.8, §6.9)

**Goal:** Confirm AI learning and pot estimation accuracy over larger samples.

**Method:**
```bash
python3 hustler.py --aigame 10000 --shark
# Track: win distribution, shot success rates, play evolution
# Does SHARK converge to a stable strategy?
# Do leave estimates improve with more games?
```

**Hypothesis:** AI behaviour is stable; utility scoring converges; leave estimates are consistent.

**Status:** 📊 **Queued (post-release, analysis phase)**

---

## Release Milestones

| Version | Status | Target | Contents |
|---------|--------|--------|----------|
| R6.3 | ✅ Released | Jul 2026 | Graphics Pass 3.1–3.2 (SSAA + bloom) |
| R6.4 | 📋 Pending | Oct 2026 | Graphics Pass 3.3a (fullscreen + fit-to-region) |
| R6.5 | 📋 Pending | Nov 2026 | Graphics Pass 3.3b (widgets + tabs) |
| R6.6 | 📋 Pending | Dec 2026 | Graphics Pass 3.4 (effects) |
| R7.0 | 📋 Pending | Jan 2027 | R6 Gameplay 1–3 (WEPF rules, spin, safety) |
| R7.1 | 🔮 Future | Q2 2027 | Graphics 1B (GL-native renderer) + Gameplay 4 (spectator polish) |

---

## How to Use This Roadmap

### For Contributors
1. Pick a **signed-off** item (✅ or 📋 status)
2. Read the full brief in [HANDOFF_HUSTLER.md](docs/HANDOFF_HUSTLER.md)
3. Create an issue using the feature template
4. Follow [DEVELOPMENT.md](docs/DEVELOPMENT.md) workflow
5. Validate against the acceptance criteria

### For Code Review
1. Ensure the change corresponds to a signed-off brief
2. Verify validation chain: `py_compile` → `--selftest` → `--batch 30` → `--smoke`
3. Check assertions (one new assertion per feature)
4. Verify headless modes still work (`--snap`, `--smoke`, `--smoke-gl`)

### For Project Planning
- **Graphics Pass 3:** ~3 months (increments 3a, 3b, 4 in sequence)
- **R6 Gameplay:** ~2 months (features 1–3 in parallel if possible)
- **Research:** ongoing (post-release, lower priority)

---

**Last Updated:** July 2026 (R6.3)

See [HANDOFF_HUSTLER.md](docs/HANDOFF_HUSTLER.md) for full project history and decision logs.
