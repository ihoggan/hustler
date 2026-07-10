# Contributing to HUSTLER

Thank you for your interest in contributing! This guide covers the contribution workflow and expectations.

## Before You Start

1. **Read** [DEVELOPMENT.md](docs/DEVELOPMENT.md) — this is essential
2. **Read** [HANDOFF_HUSTLER.md](docs/HANDOFF_HUSTLER.md) — project history and current work
3. **Check** [ROADMAP.md](ROADMAP.md) — what's signed off and queued
4. **Verify baseline:** Run `python3 hustler.py --selftest` (should show 27/27 ✓)

## Workflow

### 1. Pick a Task

- Check [ROADMAP.md](ROADMAP.md) for signed-off items
- Or [Issues](../../issues) if there's an open discussion
- **Always ensure the feature is signed off before coding**

### 2. Create a Feature Branch

```bash
git checkout -b feature/short-description
# Example: feature/fullscreen-window, feature/spin-ai, etc.
```

### 3. Design → Build → Validate

Follow the **decision → sign-off → build → validate** workflow:

**A. Decision Brief** (always in the code or commit message)
```
Feature: [short title]
Problem: [what are we solving?]
Approach: [how? any alternatives?]
Scope: [what's in/out?]
```

**B. Implement** (commit often, small changes)

**C. Add Selftest Assertion** (exactly one per feature)
```python
# In the --selftest suite
def test_my_feature():
    result = my_feature_function()
    assert expected_condition, "My feature works"
```

**D. Validate the Chain**
```bash
python -m py_compile hustler.py cushion_path.py
python3 hustler.py --selftest      # Must pass (27/27 → 28/28, etc.)
python3 hustler.py --batch 30      # No escapes
python3 hustler.py --smoke         # GUI loop OK
python3 hustler.py --snap /tmp/new.png  # (If render changes)
python3 hustler.py --smoke-gl      # (If GL changes, optional)
```

### 4. Commit with Context

```bash
git commit -m "Feature: [title]

[Longer explanation of the design and why it matters]

Validation:
- Selftest 28/28 ✓ (added pot_estimate_accuracy assertion)
- Batch 30 containment ✓ (0 escapes)
- Smoke ✓
- Classic render ✓ (byte-identical)
"
```

### 5. Push & Open a PR

```bash
git push origin feature/short-description
# Go to GitHub, open a PR with the same brief as your commits
```

## Code Standards

### Style

- **Python 3.12+** idioms
- **Docstrings** on geometry, AI, and rules functions
- **Inline comments** for physics (cite sources: WEPF, Mathavan, etc.)
- **Type hints** optional but welcome (improves clarity)
- **UK spelling:** colour, centre, favour, metres, etc.

### Physics

- Simulation in **real units** (metres, kg, seconds)
- Rendering scales via `PX_PER_M` only
- **No game-feel distortion** of table spec or ball physics
- Specs sourced from WEPF, Mathavan, or measured data

### AI

- Behaviour **emergent from utility scoring**, not scripts
- Personality via **parameters** (greed, jitter, risk), not decision trees
- Test by running `--aigame 50` and observing play style

### Rendering

- **Headless modes** (`--snap`, `--smoke`) render scene-only at R6.1 framing
- **Byte-identical invariant:** classic render must not change (unless intentional redesign)
- **Pixel-probe assertions:** every graphics feature gets a pixel-level test

### Testing

- **One assertion per feature** in `--selftest`
- **Dependency-aware:** GL assertions skip gracefully if moderngl unavailable
- **Fast:** `--selftest` should complete in < 1 second

## Common Patterns

### Adding a Physics Feature

1. Add constant to config (e.g., `NEW_FRICTION = 0.123`)
2. Implement in pymunk collision handler
3. Add geometry prediction (pure Python, no pymunk) if it affects aiming
4. Add selftest assertion
5. Validate: `--batch 30` (check containment)

**Example:**
```python
# hustler.py, top section
NEW_FRICTION = 0.05  # Custom friction (m/s²)

# In collision handler
def handle_new_friction(arbiter):
    normal_velocity = arbiter.contact_point_set.normal
    # Apply custom friction model

# In selftest
def test_new_friction():
    ball = Ball(...)
    result = simulate_with_new_friction(ball)
    assert result.velocity < expected, "Friction reduces velocity"
```

### Adding an AI Feature

1. Define the utility term (how does this contribute to shot quality?)
2. Add geometry estimation (if needed)
3. Integrate into `PoolAI.score_shot()` or similar
4. Add selftest assertion
5. Test with `--aigame 50` (observe play style changes)

**Example:**
```python
class PoolAI:
    def score_shot(self, ball, pocket, cue_angle):
        pot_chance = self.estimate_pot_chance(...)
        leave_quality = self.estimate_leave(...)
        # NEW FEATURE: foul risk term
        foul_risk = self.estimate_foul_risk(...)
        utility = pot_chance * leave_quality * (1 - foul_risk)
        return utility

# In selftest
def test_foul_risk_term():
    risky_pos = Position(near_wall=True, blocked=True)
    risk = ai.estimate_foul_risk(risky_pos)
    assert risk > 0.5, "Risky position detected"
```

### Adding a Graphics Feature

1. Implement render function (or shader for GL)
2. Add two assertions if GL-specific (classic + GL paths)
3. Keep headless modes rendering scene-only
4. Pixel-probe for render correctness
5. Test with `--gl` and `--classic`

**Example:**
```python
def render_my_feature(surface, game_state):
    """Render feature on surface."""
    # Classic path
    for ball in game_state.balls:
        draw_something(surface, ball)

# In selftest
def test_my_feature_classic():
    """Classic renderer produces expected pixels."""
    pixels = render_headless_classic()
    assert pixels[100, 100] == expected_color

def test_my_feature_gl():
    """GL renderer pixel-exact to classic."""
    pixels_gl = render_headless_gl()
    pixels_classic = render_headless_classic()
    diff = abs(pixels_gl - pixels_classic).max()
    assert diff <= 1, f"GL/classic mismatch {diff}"
```

## Troubleshooting

### Selftest Fails

**Issue:** Selftest 26/27
- Check: Did you add a new assertion?
- Is it dependency-aware if GL-related?

**Fix:**
```python
try:
    import moderngl
    result = test_gl_feature()
    assert result.passed
except ImportError:
    print("  [SKIP] GL feature (moderngl unavailable)")
```

### Batch Test: Escapes

**Issue:** Ball leaves the table
- Check: `collision_slop` (should be 0.0002)
- Check: Pocket capture points (inside the throat)
- Check: Rail geometry (no gaps or inversions)

**Fix:** Run `python3 hustler.py --batch 10` with verbose logging; identify which shot escapes; inspect that configuration.

### Classic Render Differs

**Issue:** Screenshot differs from R6.1 baseline
- Intentional redesign? Update baseline (with justification in PR)
- Unintentional bug? Revert render change

**Fix:**
```bash
python3 hustler.py --snap /tmp/new.png
# Compare to R6.1 baseline visually
# If correct: update baseline in validation suite
# If wrong: debug render code
```

### AI Behaves Strangely

**Issue:** AI makes weird shots
- Check: Is it emergent behaviour or a bug?
- Test: Run `--aigame 50`, observe if it's consistent or random

**Fix:** If consistent, it's probably emergent (check utility scoring). If random, it's probably a bug (add logging to `score_shot()`).

## Review Checklist (Maintainer)

- [ ] Feature is signed off in ROADMAP or HANDOFF
- [ ] Decision brief is clear
- [ ] Code is readable (docstrings, comments)
- [ ] One selftest assertion added
- [ ] Validation chain passes (py_compile → selftest 27+/27+ → batch 30 → smoke)
- [ ] Headless modes still work (`--snap`, `--smoke`)
- [ ] UK spelling used
- [ ] No new external dependencies (unless approved)
- [ ] AI is emergent (no scripts)
- [ ] Physics is sourced (citations included)

## Getting Help

1. **Check** [FINDINGS.md](docs/FINDINGS.md) — hard-won discoveries
2. **Read** [HANDOFF_HUSTLER.md](docs/HANDOFF_HUSTLER.md) — project context
3. **Search** issues and PRs — your question might be answered
4. **Ask** in an issue — describe what you're stuck on

## Code of Conduct

- Be respectful and constructive
- Assume good intent
- Give credit where due
- Focus on the code, not the person

---

Thank you for contributing! We appreciate your effort to improve HUSTLER.

For questions or suggestions about this guide, open an issue or a discussion.
