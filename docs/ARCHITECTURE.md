# Architecture

## Overview

HUSTLER is a physics-first pool sandbox. The architecture separates concerns into independent layers, each with clear responsibilities:

1. **Simulation** (pymunk) — real-world physics in real units
2. **Geometry** (pure Python) — aiming prediction, pot assessment
3. **Rules** (state machine) — blackball gameplay logic
4. **AI** (utility scoring) — emergent shot selection
5. **Rendering** (classic + GL) — visual presentation
6. **GUI** (interaction) — player input, mode management

---

## Design Decisions

### Decision 1C: Hybrid Simulation (Real Units + Rendering Scale)

**Problem:** Pool physics happens in metres and seconds, but screen rendering uses pixels and frame timing. Mixing units breeds bugs.

**Solution:** 
- **pymunk simulation runs in real units** (metres, kilograms, seconds)
- **Rendering scales by a single constant** (`PX_PER_M`) at draw time
- **Geometry layer operates in real units** with no rendering dependencies

**Rationale:**
- Sourcing specs (WEPF, Mathavan, etc.) gives us real-world values directly
- No game-feel distortion of physics happens at the simulation level
- Rendering is independent; switching from rasterised to GL doesn't change physics

**Implementation:**
- All ball positions, velocities, forces in metres
- All times in seconds (PHYS_DT = 1/480 second)
- Table dimensions: 1.82 × 0.91 m (7 ft WEPF spec)
- At render time: `screen_x = world_x * PX_PER_M` (currently 800)

### Decision 2A: Pure Geometry Layer

**Problem:** Aiming overlay, pot assessment, and break analysis all need geometry—but pymunk objects are tied to the physics loop. Adding features requires callbacks and tricky synchronisation.

**Solution:** 
- **Geometry functions are pure Python**—no pymunk import in the geometry section
- Functions take ball positions/velocities as arguments, return predictions
- Predictions are precomputed before the physics loop commits

**Example:**
```python
def ghost_ball_position(cue_pos, target_pos, cue_angle):
    """Pure geometry: where should the cue ball be after contact?"""
    # No pymunk, no side effects
    # Input: 2D positions, returns 2D position
```

**Benefits:**
- Geometry functions are directly unit-testable (no pygame/pymunk setup needed)
- Predictions can be batched (e.g., all legal shots evaluated before the AI commits)
- Rendering can use the same predictions without depending on simulation state

**Trade-off:** Geometry is an approximation (e.g., one-bounce prediction doesn't model ball radius or spin precisely), but it's fast and good enough for aiming.

### Decision 3A: Utility-Based AI

**Problem:** Scripting shot decisions ("if X then do Y") leads to brittle, hard-to-tweak AI. Adding strategies requires more code.

**Solution:**
- **Every legal (ball, pocket) pot is scored by utility**
- Utility = probability × (positional advantage)
- AI selects the highest-utility shot (greedy)
- Personality emerges from two parameters: **greed** and **jitter**

**Example:**
```python
greed = 0.55  # SHARK personality
utility = pot_chance * ((1 - greed) + greed * leave_quality)

# greed=0: "pot with highest chance" (R4 exact)
# greed=0.55: "balance pot chance + good position" (position player)
# greed=1.0: "position everything, ignore pots" (safety-only)
```

**Benefits:**
- Personality is transparent (two numbers)
- Behaviour emerges without special cases
- Easy to test: vary greed, run `--aigame`, observe play styles

**Test:**
```bash
python3 hustler.py --aigame 100  # Run 100 AI vs AI games
# Observe: SHARK (0.55) plays more attacking; STEADY (0.25) plays safer
```

---

## Layer Details

### 1. Simulation (pymunk)

**File:** Top of `hustler.py`

**Responsibilities:**
- pymunk space setup (collision_slop 0.0002, gravity None for pool)
- Ball physics bodies (positions, velocities, rotations)
- Rail/cushion collision handling (restitution 0.75, friction 0.14)
- Pocket capture (balls inside throat get teleported off-table)
- Spin-to-velocity mapping (follow/draw/side kicks)

**Key Config:**
```python
PHYS_DT = 1 / 480  # 480 Hz physics tick
PHYS_SUBSTEPS = 10  # Per-tick sub-steps (total 4800 Hz)
BALL_RESTITUTION = 0.96
RAIL_RESTITUTION = 0.75
CUSHION_FRICTION = 0.14
ROLLING_RESISTANCE = 0.147  # m/s² deceleration on cloth
```

**Hard-Won Facts:**
- `collision_slop` defaults to 0.1 space-units (10 cm). Must override to 0.0002 or collisions are mush.
- pymunk 7 removed `add_collision_handler` — use `space.on_collision()` instead
- Spin to velocity uses simplified FOLLOW_KICK (0.60) and SIDE_KICK (0.35) model, not first-principles

### 2. Geometry (Pure Python)

**File:** Top of `hustler.py` + `cushion_path.py`

**Functions:**
- `ghost_ball_position(cue, target, cue_angle)` → cue ball trajectory
- `object_ball_line(ball, pocket)` — line of centres for contact
- `one_bounce_carry(cue_pos, velocity, first_rail)` — post-bounce carry
- `pot_estimate(cue, ball, pocket, cue_angle, spin)` → success probability
- `tangent_paths(ball, pockets)` → tangent lines for aim guides

**No Dependencies:** These are pure functions taking positions and velocities, returning positions or scores. No pymunk, no pygame.

**Testing:** All geometry is directly unit-testable in `--selftest`.

**Accuracy Trade-offs:**
- Ghost ball assumes point contact (real balls have radius)
- One-bounce ignores ball spin during carry
- Pot estimate uses a fixed jitter model, not measured AI skill

These are intentional simplifications; they're fast and good enough for aiming.

### 3. Rules (State Machine)

**File:** `Game` class in `hustler.py`

**State:**
```python
class Game:
    def __init__(self):
        self.player_colour = None  # RED | YELLOW (or None)
        self.turn = "player"       # "player" | "ai"
        self.balls_on_table = set()
        self.balls_pocketed = {"red": 0, "yellow": 0, "black": 0}
        self.game_over = False
        self.game_result = None
```

**Rules:**
1. **Colour assignment:** First pot by a player defines their colour
2. **Pot-to-continue:** Pot your colour → you get another shot
3. **Scratch:** Cue ball in a pocket → opponent's turn, re-spot behind baulk
4. **Black logic:**
   - Cannot pot black until your colour is cleared
   - Pot black and you win immediately
   - Pot black when it's not your turn → you lose immediately

**Methods:**
- `on_ball_potted(ball, player)` — handle a pot event
- `end_turn()` — pass control to the other player
- `check_win_condition()` — determine if game is over

### 4. AI (Utility Scoring)

**File:** `PoolAI` class in `hustler.py`

**Responsibilities:**
- Enumerate all legal (ball, pocket) shots
- Score each shot by utility (pot chance × positional advantage)
- Select the highest-utility shot (greedy)
- Return shot parameters (cue angle, power, spin)

**Personality:**
```python
class PoolAI:
    def __init__(self, greed=0.55, jitter=0.1):
        self.greed = greed          # Position balance: 0 (pot-first) to 1 (position-only)
        self.aim_jitter = jitter    # Random error in aim (radians)
        self.power_jitter = 0.2     # Random error in power (m/s)
```

**Scoring Example:**
```python
# For each legal (ball, pocket) pair:
pot_chance = estimate_pot_probability(ball, pocket, cue_angle)
leave_quality = estimate_leave_score(post_pot_cue_position)

utility = pot_chance * ((1 - greed) + greed * leave_quality)

# Choose shot with max utility
best_shot = max(all_shots, key=lambda s: s.utility)
```

**Emergent Behaviour:**
- **SHARK** (greed=0.55): Hunts position; will take risky pots with good leave
- **STEADY** (greed=0.25): Conservative; takes surest pots only
- **Adjustable:** Both adapt their shot selection based on table state

**Test:**
```bash
python3 hustler.py --aigame 100 --shark  # SHARK personality
python3 hustler.py --aigame 100 --steady  # STEADY personality
# Compare win rates and styles
```

### 5. Rendering

#### Classic Pipeline (pygame rasterised)

**File:** `draw_table()`, `draw_balls()`, etc. in `hustler.py`

**Flow:**
1. Clear screen
2. Draw table (rails, cushions, pockets, cloth)
3. Draw balls (circles with shading)
4. Draw UI (overlay, annotations, controls)
5. Flip display

**Key Functions:**
- `draw_table(surface)` — static geometry (rails, pockets)
- `draw_balls(surface, balls)` — dynamic (positions, spins)
- `draw_overlay(surface)` — ghost ball, pot estimates, etc.

**Performance:** 60 FPS target on nix5; slower on weak machines.

#### GL Post-Process Pipeline (2× SSAA + Bloom)

**File:** `GLPostProcessor` class in `hustler.py`

**Flow:**
1. Render classic scene to an offscreen **SSAA framebuffer** (2×2 supersampling)
2. Box-filter resolve to 1× target
3. Apply **bloom** (threshold → separable Gaussian blur → additive composite)
4. Composite panel UI on top (crisp, no bloom)
5. Display to screen

**Presets:**
```python
BLOOM_SUBTLE   = (0.7, 0.05, 1.5)  # (threshold, knee, intensity)
BLOOM_BALANCED = (0.6, 0.1, 2.0)   # Default
BLOOM_ARCADE   = (0.5, 0.2, 3.0)   # Dramatic
```

**Headless Validation:**
- `--smoke-gl` runs the GL path headless via EGL + llvmpipe (software rendering)
- Pixel-probe assertion verifies SSAA + bloom output is correct
- Core assertion (no GL): checks passthrough render matches classic exactly

**Dependency Management:**
```python
try:
    import moderngl
    HAS_GL = True
except ImportError:
    HAS_GL = False
```

GL features are optional; core chain stays green without them.

### 6. GUI & Interaction

**File:** `main_loop()` in `hustler.py`

**Modes:**
1. **SANDBOX:** Free striking, no rules, any ball anytime
2. **YOU vs AI:** Blackball rules, human player red, AI player yellow
3. **AI vs AI:** Spectator mode, watch two AIs play; auto-advance turns

**Input Handling:**
- Mouse: aim direction (cue ball → pointer)
- Keyboard: power/spin, mode cycling, parameters
- SPACE: strike (only if legal for current turn)

**Turn Management:**
- After a shot, check game rules:
  - Did you pot a ball? → Continue (your turn)
  - Did you pot nothing? → Pass (opponent's turn)
  - Did you scratch? → Opponent's turn, re-spot behind baulk
  - Did you pot black illegally? → You lose
- Balls must come to rest before next strike (sleep threshold check)

**Headless Modes:**
- `--selftest` — no GUI, assertions only
- `--batch N` — no GUI, N random strikes, stats
- `--aigame N` — no GUI, N AI-vs-AI games, tournament results
- `--smoke` — GUI loop on dummy display (dvfb), 90 frames, no actual rendering

---

## Data Flow

```
Input (mouse, keyboard)
    ↓
Aiming Geometry (ghost ball, prediction)
    ↓
Interactive Rendering (classic or GL)
    ↓ [if strike command]
    ↓
AI Decision (utility scoring) or Player Command
    ↓
Physics Step (pymunk, 480 Hz)
    ↓
Collision Callbacks (spin kicks, restitution)
    ↓
Pocket Capture (teleport balls off-table)
    ↓
Rules Check (pot, scratch, black logic)
    ↓
Turn Management (switch player if needed)
    ↓
Loop (next frame)
```

---

## Constants & Configuration

**Physics:**
```python
PHYS_DT = 1 / 480           # Simulation tick: 480 Hz
PHYS_SUBSTEPS = 10          # Sub-steps per tick
TABLE_L, TABLE_W = 1.82, 0.91  # Metres (WEPF 7 ft)
BALL_DIA = 0.0508           # 50.8 mm, WEPF spec
CUE_DIA_WEPF = 0.0476       # 47.6 mm, championship
CUE_DIA_CASUAL = 0.0508     # 50.8 mm, casual
BALL_MASS = 0.116           # kg, WEPF spec
CUE_MASS_WEPF = 0.094       # kg, championship
BALL_RESTITUTION = 0.96     # Pair restitution (ball-ball)
RAIL_RESTITUTION = 0.75     # Effective pair (ball-rail)
CUSHION_FRICTION = 0.14     # Mathavan et al.
MU_R = 0.015                # Rolling resistance (napped cloth)
```

**Rendering:**
```python
PX_PER_M = 800              # Pixels per metre at draw time
WIDTH, HEIGHT = 1456, 728   # Screen resolution (16:9 at default scale)
FPS = 60                    # Display refresh
```

**AI:**
```python
SHARK = {"greed": 0.55, "jitter": 0.05}   # Aggressive
STEADY = {"greed": 0.25, "jitter": 0.10}  # Conservative
```

---

## Testing Strategy

**Unit Tests (geometry layer):**
```bash
python3 hustler.py --selftest
```
All 27 assertions must pass.

**Containment Tests (physics layer):**
```bash
python3 hustler.py --batch 30
```
No balls should escape the table.

**Integration Tests (rules + AI):**
```bash
python3 hustler.py --aigame 50
```
Observe win rates and play styles; both should be reasonable.

**Visual Tests (rendering):**
```bash
python3 hustler.py --snap /tmp/baseline.png
```
Compare screenshot to baseline; render must be byte-identical to R6.1.

---

## Known Limitations & Trade-Offs

1. **One-bounce prediction is approximate** — doesn't model spin during carry
2. **Pocket assessment is heuristic** — uses fixed jitter model, not measured AI accuracy
3. **Spin model is simplified** — FOLLOW_KICK/SIDE_KICK constants, not full friction-spin coupling
4. **AI is greedy** — always chooses the immediately best shot, never looks ahead
5. **Glass physics** (zero elasticity) — no real cue-ball friction model during strike

These are intentional: they keep the code fast, understandable, and fun. Real pool physics is complex; this is a purposeful simplification.

---

## Future Directions

- **1B GL-native renderer** — per-pixel shaded sphere rendering, MSAA geometry
- **Increment 4 effects** — motion trails, slow-motion, pot "swallow" animation
- **WEPF rules** — safeties, fouls, penalty scoring
- **AI spin selection** — teach the AI to use spin strategically
- **Spectator polish** — shot-by-shot commentary, score banner, replay system
