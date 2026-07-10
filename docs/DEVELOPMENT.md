# Development Guide

## Working Agreement (Non-Negotiable)

All code changes must follow this workflow:

### 1. Decision → Sign-Off → Build → Validate

- **Decision:** Brief describing the change, forks (if any), and how it solves the problem
- **Sign-off:** Explicit approval before code is written
- **Build:** Implement the feature or fix
- **Validate:** Pass the full validation chain (see below)

This discipline ensures changes are intentional, documented, and safe.

### 2. Validation Chain (Every Release)

```
py_compile → --selftest → --batch N → --smoke
+ --smoke-gl (GL changes) + --snap (pixel-probe)
```

**Do not skip any step.** Each stage catches different failure modes:

1. **py_compile** — Syntax errors (immediate feedback)
2. **--selftest** — 27/27 assertions (one per feature; dependency-aware GL assertions skip gracefully)
3. **--batch N** — Containment check (N random strikes, ensure balls don't escape; N=30 minimum)
4. **--smoke** — Interactive loop validation (headless, dummy video driver, 90 frames)
5. **--smoke-gl** — GL-only validation (headless via EGL/llvmpipe, SSAA + bloom rendered correctly)
6. **--snap FILE** — Screenshot to verify pixel-level correctness

### 3. One Selftest Assertion Per Feature

Every new gameplay, physics, or graphics feature must add exactly one new selftest assertion. This keeps the assertion count as a progress metric and forces features to be unit-testable in isolation.

GL assertions are **dependency-aware**: they skip (not fail) if moderngl/EGL is unavailable, so the core chain stays green on stripped containers.

### 4. Emergent AI Only

AI behaviour must arise from:
- Utility scoring (greedy selection of best move)
- Personality parameters (greed, jitter, risk tolerance)
- Geometric estimates (pot chance, leave quality)

**Never:** decision scripts, hard-coded shot types, or conditional logic that says "if X then do Y".

Test emergent behaviour by varying parameters and observing how play changes.

### 5. Real WEPF Units

- Simulation: metres, kilograms, seconds
- Physics: specs from WEPF Annexe A, measured data, peer-reviewed research
- No "game-feel" fudging of table dimensions, ball mass, or restitution
- Rendering scales to pixels at draw time via `PX_PER_M`

### 6. UK Spelling

Throughout the codebase: colour, centre, favour, calibre, metres, etc.

---

## Setup for Contributors

### 1. Clone & Install

```bash
git clone https://github.com/ihoggan/hustler.git
cd hustler
pip install -r requirements.txt
pip install -r requirements-gl.txt  # Optional, for GL renderer
```

### 2. Verify Baseline

Before making changes, confirm the current state is green:

```bash
python3 hustler.py --selftest    # Should show 27/27 ✓
python3 hustler.py --batch 30    # Should complete, 0 escapes
python3 hustler.py --smoke       # Should complete
python3 cushion_path.py          # Should show standalone green
```

### 3. Write Your Feature / Fix

Follow the code style:
- Function docstrings for geometry, AI, rules logic
- Inline comments for physics calculations (cite sources)
- Type hints where it aids clarity (not mandatory)
- Keep functions small and testable

**Geometry functions** (pure Python, no pymunk) live in the geometry section and must be directly testable. **AI functions** must emit their score/utility so behaviour is auditable.

### 4. Add a Selftest Assertion

Add exactly one assertion to the `--selftest` suite that validates your feature in isolation (headless, no GUI). Examples:

```python
# Physics: test a new collision property
result = test_ball_restitution_on_rail()
assert result > 0.70 and result < 0.80, f"Restitution {result} out of range"

# Geometry: test a new prediction function
ghost_ball = predict_ghost_ball(cue_pos, target_pos, spin)
assert ghost_ball.distance_to(target) < 0.01, "Ghost ball misaligned"

# AI: test utility scoring
shot = evaluate_shot(cue_ball, target_ball, pocket)
assert 0 <= shot.utility <= 1, f"Utility {shot.utility} out of [0,1]"

# Render: test a new shader or post-process output
pixels = render_headless_snapshot()
assert pixels.shape == (HEIGHT, WIDTH, 4), "Screenshot dimensions wrong"
```

GL assertions must handle missing moderngl gracefully:

```python
try:
    import moderngl
    result = test_bloom_shader()
    assert result.passed, "Bloom shader failed pixel-exact test"
except ImportError:
    print("  [SKIP] bloom shader (moderngl unavailable)")
```

### 5. Run the Validation Chain

```bash
# Quick compile check
python -m py_compile hustler.py cushion_path.py

# Full validation
python3 hustler.py --selftest
python3 hustler.py --batch 30
python3 hustler.py --smoke
python3 hustler.py --smoke-gl    # Optional if GL available
python3 hustler.py --snap /tmp/baseline.png  # Optional, verify render
```

If any step fails, **do not proceed to push**. Fix the issue and re-run the chain.

### 6. Commit & Push

```bash
git add hustler.py cushion_path.py  # And any new docs
git commit -m "Feature: [short description]

[Optional longer explanation of the design and why it was done this way.]

Validation:
- Selftest 28/28 (added pot_estimate_accuracy assertion)
- Batch 30 containment: 0 escapes
- Smoke: OK
- Classic render: byte-identical
"
git push origin feature-branch
```

Create a PR with a clear description of the decision and findings.

---

## Common Tasks

### Adding a New Physics Feature

1. **Understand the current model** — read PHYSICS.md and the relevant section in hustler.py
2. **Source real-world spec** — cite WEPF, Mathavan, manufacturer data, or measured results
3. **Implement in simulation** (pymunk layer)
4. **Add geometry prediction** (pure Python layer) if the feature affects aiming
5. **Add one selftest assertion** — test the feature in isolation
6. **Validate against real behaviour** — compare your simulation to actual pool physics if possible
7. **Update docstring & PHYSICS.md** with the source and calibration result

### Adding an AI Feature

1. **Design the utility term** — how does this feature contribute to shot quality?
2. **Source geometric estimate** if needed (e.g., leave quality, risky shots)
3. **Add one selftest assertion** — test the utility calculation
4. **Add a parameter** (e.g., risk_aversion) if this is a personality trait
5. **Test with `--aigame`** — run a tournament with both personalities; does one adapt?
6. **Document the decision** in the code and HANDOFF document

### Adding a Graphics Feature

1. **Implement render function** (or shader for GL path)
2. **Add **two** assertions** if the feature is GL-specific:
   - One for the classic (rasterised) path
   - One for the GL (post-process) path with pixel-exact validation
3. **Ensure headless modes are **not** affected** — `--snap` and `--smoke` must keep rendering the scene-only at the R6.1 framing (no UI chrome)
4. **Test with `--gl` and `--classic`** — ensure both render paths work
5. **Test with `--smoke-gl`** headless — verify EGL/llvmpipe rendering works

### Changing the Table Geometry

**This is rare.** The table geometry is FINAL as of R6.1 (tangent-true cushions, 6ft WEPF spec). If you believe a change is needed:

1. **Discuss with the project owner first** — geometry changes affect physics, drill validation, pot estimates, all of it
2. **Source the spec** — real table data, construction drawings, or measured results
3. **Update cushion_path.py** and re-run its standalone selftest
4. **Re-run the full drill gate** — all 18 pots must succeed at >= 90%
5. **Validate byte-identical render** — if geometry changes affect drawing, new snapshots are required

---

## Code Organisation

### Main File (hustler.py)

- **Top:** imports, config (ball specs, table dims, colours, physics constants)
- **Geometry layer:** pure-Python functions (ghost ball, pot assessment, one-bounce prediction)
- **Physics layer:** pymunk setup, collision handlers, ball/rail/pocket simulation
- **Rules layer:** `Game` class state machine (colour, pot-to-continue, scratch, black logic)
- **AI layer:** `PoolAI` class, utility scoring, shot selection
- **Rendering:** classic rasterised pipeline + GL post-process orchestration
- **GUI:** interaction loop, mode cycling (SANDBOX / YOU vs AI / AI vs AI)
- **Headless modes:** selftest, batch, breaks analyser, smoke, snapshot, AI tournament

### Geometry Module (cushion_path.py)

- **Tangent-true cushion loop** — 36 primitives defining the exact nose line
- **Render stack** — layered drawing (rails, cushions, pockets, highlights)
- **Helper functions** — point-in-table, distance-to-pocket, etc.
- **Standalone selftest** — validates 6ft/89–100 mm spec, run independently

---

## Performance & Profiling

The simulation runs at 480 Hz (PHYS_DT = 1/480) by default. If performance is an issue:

1. **Profile before optimising** — identify bottlenecks with cProfile:
   ```bash
   python3 -m cProfile -s cumulative hustler.py --batch 10
   ```

2. **Common issues:**
   - Too many sub-steps (try reducing PHYS_SUBSTEPS)
   - Collision solver struggling (check collision_slop, restitution tuning)
   - Rendering every frame (headless modes skip rendering; use `--batch` for speed)

3. **Do not sacrifice accuracy** — the physics must match the spec, even if it's slow

---

## Troubleshooting

### "Selftest 26/27 (GL assertion skipped)"
This is normal if moderngl/EGL is unavailable. Core chain (physics + classic render) is still green.

### "Batch test: 5 escapes"
Balls are leaving the table. Check:
- collision_slop value (should be 0.0002)
- Pocket capture points (inside the throat, not on the nose)
- Rail contact normals (should point inward)

### "Smoke test hangs"
The interactive loop is stuck. Usually means:
- Rendering is broken (try `--classic` to disable GL)
- Input handling has a deadlock
- Physics loop is infinitely looping

### "Classic render differs from baseline"
If you changed anything in the rendering pipeline:
1. Run `python3 hustler.py --snap /tmp/new.png`
2. Compare `/tmp/new.png` to the R6.1 baseline
3. If the difference is visual (not a bug), update the baseline in the validation suite

---

## Asking for Help

If you're stuck:
1. Check [FINDINGS.md](FINDINGS.md) — most hard-won discoveries are documented there
2. Review the [HANDOFF_HUSTLER.md](HANDOFF_HUSTLER.md) project history for context
3. Run `git log --oneline` to see past decision commits
4. Open an issue with details of what you tried and what failed

Good luck, and thank you for contributing!
