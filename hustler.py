#!/usr/bin/env python3
"""
HUSTLER — UK Pool Physics Sandbox (R6)
=======================================
Single-file pygame + pymunk sandbox for UK blackball-spec table physics.

Architecture (decision 1C — hybrid):
  * pymunk owns the simulation, running in REAL UNITS: metres, kilograms,
    seconds. Rendering scales to pixels only at draw time.
  * A pure-maths geometry layer owns aiming prediction (ghost ball, object
    line, cue tangent, one-bounce continuation, pot assessment) with no
    pymunk dependency, so it is directly unit-testable.

R3 (real-spec calibration + the break):
  * WEPF championship spec: 2" / 116 g object balls, 1-7/8" / 94 g cue ball
    (now the DEFAULT — K toggles a casual full-size cue), 1.82 x 0.91 m
    playing surface, pocket mouth = 1.6 x ball diameter at all six pockets,
    baulk line at 1/5 table length, black spotted at the centre of the top
    half. Sources: WEPF Annexe A equipment spec; manufacturer data.
  * Cloth: constant-deceleration rolling resistance (mu_r * g), replacing
    R2's exponential damping — the physical model. A slow ball now trickles.
    mu_r default 0.015 (napped UK pool cloth, slow end of the measured
    0.005-0.015 range).
  * Cushions: ball-ball pair restitution 0.96 (measured range 0.92-0.98);
    effective ball-rail pair restitution ~0.75 (measured range 0.6-0.9).
    Note: Mathavan et al. (Loughborough, 2010) measured NORMAL restitution
    0.98 with impact sliding friction 0.14 — their 0.98 is pre-friction;
    our pair value targets the observed effective rebound. Cushion contact
    friction set to 0.14 per that work.
  * Full blackball rack (7 red, 7 yellow, black on the spot) and a
    parameterised break: cue position on the baulk line, aim offset across
    the pack, power, spin — all scriptable (decision 1B).
  * Break analyser (decision 2A): --breaks N sweeps aim offset x power with
    seeded human-error jitter; reports pots, scratches, black-downs, spread
    and fair-break rate per configuration.
  * One-bounce cue-path prediction off the first cushion (decision 3A).
  * Pot drill gate (decision 4A): 18 straight pots from 0.6 m across all six
    pockets with lateral offsets must succeed at >= 90%, enforced in the
    selftest, so the jaws are calibrated against a target, not vibes.

Modes:
  python3 hustler.py               GUI: SANDBOX / YOU vs AI / AI vs AI (M cycles)
  python3 hustler.py --selftest    headless assertions (one per feature)
  python3 hustler.py --batch N     N random strikes headless, stats report
  python3 hustler.py --breaks N    break analyser, N trials per configuration
  python3 hustler.py --aigame N    N headless AI vs AI games, results report
  python3 hustler.py --smoke       GUI loop on dummy video driver, 90 frames
  python3 hustler.py --snap FILE   headless smoke run, save screenshot PNG

R4 (rules-lite + the utility AI):
  * Rules-lite blackball (decision 1B): colour assignment on first pot,
    pot-your-colour-to-continue, scratch = respot behind baulk + turn passes,
    black legal only once cleared — early black loses, clean black wins.
  * Geometric utility AI (decision 2A): every legal (ball, pocket) pot is
    scored from ghost-ball geometry, corridor clearance and an analytic
    success estimate vs the AI's own aim jitter; below-threshold positions
    become soft safeties. Behaviour emerges from parameters, never scripts.
    SHARK (true aim, attacks) vs STEADY (more jitter, needs better odds).
  * Three GUI modes (decision 3A): sandbox, YOU vs AI, AI-vs-AI spectator
    with the AI's planned shot previewed while it 'considers'.
R5 (positional play + spin break sweep):
  * AI leave term (decision A3): each candidate pot's estimated cue-ball
    rest position (analytic tangent/carry model, one cushion bounce) is
    scored by the best next-shot chance from there; utility
    u = p x ((1-greed) + greed x leave). greed is a personality parameter
    (SHARK 0.55 hunts position, STEADY 0.25 takes the surest pot);
    greed=0 reproduces R4 exactly. Emergent, never scripted.
  * Break analyser phase 2 (decision C2): spin sweep (follow/draw x side)
    at 7 m/s over the smash and folk-wisdom aims, with a cue-ball control
    metric (ctl = mean cue distance from table centre; scratch = 1.0 m)
    added to both phases — the sweep that can adjudicate §6.4.

Controls (GUI):
  All shot parameters (power, aim angle, spin) are HUD-only (R6.6) — the
  table's mouse has no bearing on aim; only the right-hand panel and the
  keys below set anything.
  SPACE         strike (only when all balls are at rest and it is a human turn)
  M             cycle mode: SANDBOX -> YOU vs AI -> AI vs AI
  T             rack up (sandbox: blackball rack, cue to baulk; game: new frame)
  K             toggle cue ball: 1-7/8" WEPF spec <-> casual 2"
  E / Shift+E   cushion elasticity + / - (0.05)
  F / Shift+F   rolling resistance + / - (0.02, clamp 0.02 .. 0.5)
  G             toggle prediction overlay (ghost ball, pot estimate)
  ESC / Q       quit
  -- sandbox mode only (ignored during a YOU-vs-AI / AI-vs-AI frame) --
  B / Shift+B   object ball radius +/- 1 mm (rebuilds)
  N             new object ball at random position
  C             clear object balls
  R             reset radius to 25.4 mm and rebuild the default layout
  -- right-hand panel (Shot / Table / Game tabs) --
  Shot          power slider; rotating aim-angle dial (drag = absolute
                angle, +/-1 deg nudge buttons for fine tuning); 2D spin pad
                (drag = follow/side, clamped to the unit circle); Reset
                spin; Shoot (mirrors SPACE's exact guard)
  Table         cushion elasticity / roll decel / ball radius sliders
                (radius greyed outside SANDBOX); cue-size toggle
  Game          mode-cycle, rack-up, overlay-toggle buttons

Command line:
  (none)        interactive window
  --selftest    headless assertion suite
  --batch N     N random strikes, containment report
  --breaks N    break analyser, N trials per config
  --aigame N    N headless AI-vs-AI games
  --smoke       GUI smoke on the dummy video driver
  --snap FILE   headless render, save a screenshot PNG
"""

import argparse
import math
import json
import os
import functools
import multiprocessing
import random
import sys

# ----------------------------------------------------------------------------
# Configuration — real units (decision 4B: dict + hotkeys)
# ----------------------------------------------------------------------------
CFG = {
    # Table (WEPF-legal 7 ft table: Blackball Elite playing surface)
    "PLAY_W_M": 1.82,
    "PLAY_H_M": 0.91,
    "BAULK_FRAC": 0.20,           # baulk line at 1/5 table length
    # Balls (WEPF Annexe A)
    "BALL_R_M": 0.0254,           # 2" object ball
    "BALL_MASS_KG": 0.116,
    "CUE_R_M": 0.0238,            # 1-7/8" cue ball — championship default
    "CUE_MASS_KG": 0.094,
    "CUE_CASUAL_R_M": 0.0254,     # K toggles to a casual full-size cue set
    "CUE_CASUAL_MASS_KG": 0.116,
    # Pockets (blackball: corner mouth = 1.6 x ball diameter; centre pockets
    # are cut wider on real UK tables — and a tangent-true 22mm-knuckle middle
    # needs mouth > ball + 2R = 94.8mm to admit the 50.8mm ball, so the WEPF
    # 1.6x figure jams the middle throat. R6 Fork C / C1: middles at 100mm.)
    "POCKET_MOUTH_M": 1.6 * 2 * 0.0254,
    "POCKET_MIDDLE_MOUTH_M": 0.100,
    # Materials (measured ranges — see module docstring)
    "BALL_ELASTICITY": 0.98,      # pair ball-ball = 0.98^2 = 0.96
    "CUSHION_ELASTICITY": 0.77,   # pair ball-rail = 0.98 * 0.77 ~= 0.75
    "CUSHION_FRICTION": 0.14,     # Mathavan et al. impact sliding friction
    "ROLL_DECEL": 0.147,          # mu_r 0.015 * g — constant deceleration
    "STOP_SPEED": 0.02,           # m/s — below this a ball is parked
    # Striking
    "POWER_MIN": 0.5,
    "POWER_MAX": 7.0,             # hard break territory
    "POWER_STEP": 0.25,
    "POWER_DEFAULT": 2.0,
    # Spin model (R2, unit-free: kicks scale with speed)
    "SPIN_DECAY": 0.9,
    "FOLLOW_KICK": 0.60,
    "SIDE_KICK": 0.35,
    # AI leave model (R5, decision A3 — analytic geometry-layer estimates)
    "LEAVE_TANGENT_KEEP": 0.95,   # share of tangent-line speed the cue keeps
    "LEAVE_CUE_CARRY": -0.09,     # carry along the aim line on full hits
                                  # (negative: the 94 g cue rebounds — see selftest 11)
    "LEAVE_CUSHION_E": 0.73,      # effective cushion rebound used by the estimate
    # Simulation / rendering
    "PHYS_DT": 1.0 / 480.0,       # 480 Hz: max travel ~14.6mm/step << the
                                  # 30.4mm ball+nose collision band, so a ball
                                  # kicked past POWER_MAX by a pack collision
                                  # cannot tunnel the thin tangent-true segments
                                  # (R6 containment fix; was 1/240).
    "FPS": 60,
    "REST_TIMEOUT_S": 45.0,
    "PX_PER_M": 420.0,
    "MARGIN_PX": 60,
    # Graphics Pass 3, Increment 3a -- fullscreen fit-to-region. Panel is an
    # empty placeholder until 3b wires real widgets; scale clamps keep the
    # fit sane at absurd window sizes without capping normal resizing.
    "PANEL_W_PX": 260,
    "FIT_MIN_SCALE": 0.35,
    "FIT_MAX_SCALE": 3.0,
    # Increment 4a -- spectator motion trails. Samples of recent position
    # per moving ball (one per rendered frame); classic AND GL both draw
    # these (unlike bloom), per Maker's call. Live-tunable by eye.
    "TRAIL_LEN": 10,
    # Increment 4b -- pot swallow animation + cup-glow. A captured ball
    # travels from its capture point to the cup centre over this many
    # rendered frames (ease-in), shrinking and darkening toward the pocket's
    # own hole colour; the pocket's glow flash shares the same duration.
    "SWALLOW_FRAMES": 14,
    # Increment 4c -- slow-mo black finale. A held, faded pause once a
    # black-pot win/loss actually resolves (not literal slow motion --
    # on_rest only fires once the table's already fully at rest); the
    # black ball's own cup stays lit through the fade. ~1.2s at 60 FPS.
    "FINALE_FRAMES": 70,
    # Increment 4d -- vignette. Always-on ambient darken toward the frame
    # edges. VIGNETTE_START is the fraction of the half-diagonal where
    # darkening begins (0 = centre, 1 = corner); VIGNETTE_MAX is the peak
    # alpha at the very corner. Live-tunable by eye.
    "VIGNETTE_START": 0.55,
    "VIGNETTE_MAX": 90,
}



def play_rect():
    """Playing surface rectangle in METRES: (0, 0, W, H)."""
    return (0.0, 0.0, CFG["PLAY_W_M"], CFG["PLAY_H_M"])


def ball_r():
    return CFG["BALL_R_M"]


def pocket_half_mouth():
    """Half the pocket mouth width — the rail setback for middle pockets."""
    return CFG["POCKET_MOUTH_M"] / 2.0


def pocket_middle_half_mouth():
    """Half the CENTRE-pocket mouth (wider than corners — see CFG note)."""
    return CFG["POCKET_MIDDLE_MOUTH_M"] / 2.0


def pocket_centres():
    """Six pocket mouth positions (for drawing): corners + middle long rails."""
    x0, y0, x1, y1 = play_rect()
    mx = (x0 + x1) / 2.0
    return [(x0, y0), (mx, y0), (x1, y0), (x0, y1), (mx, y1), (x1, y1)]


_capture_points_cache = {}


def capture_points():
    """
    Pocket capture points: (centre, radius) per pocket, inside the throat.
    A ball must genuinely enter the mouth to drop. Shared by simulation,
    assessor and drill so there is a single source of truth.

    r9: CACHED. This is fixed table geometry, but _capture_pockets() calls it
    inside a per-ball loop on every physics step -- a profile of one AI game
    showed 1.28 MILLION calls, rebuilding the identical six pockets from
    scratch each time, and _capture_pockets dominating the run at 22.8s
    cumulative. The r9 spin grid didn't cause that; it just made enough shots
    to expose it.

    The cache is keyed on the values this actually reads rather than being
    unconditional, because ball radius IS adjustable live from the panel (and
    the pocket mouths scale with it) -- a blind cache would silently freeze the
    pockets at their old size the moment that slider moved. Behaviour is
    identical; only the recomputation goes away."""
    key = (play_rect(), pocket_half_mouth(), pocket_middle_half_mouth())
    hit = _capture_points_cache.get(key)
    if hit is not None:
        return hit
    x0, y0, x1, y1 = key[0]
    pr = key[1]
    mx = (x0 + x1) / 2.0
    s2 = math.sqrt(2.0) / 2.0
    pts = []
    for (c, o) in [((x0, y0), (-s2, -s2)), ((x1, y0), (s2, -s2)),
                   ((x0, y1), (-s2, s2)), ((x1, y1), (s2, s2))]:
        pts.append(((c[0] + o[0] * pr * 0.5, c[1] + o[1] * pr * 0.5), pr * 0.8))
    prm = key[2]
    pts.append(((mx, y0 - prm * 0.6), prm * 0.7))
    pts.append(((mx, y1 + prm * 0.6), prm * 0.7))
    _capture_points_cache[key] = pts
    return pts


# ----------------------------------------------------------------------------
# Geometry layer — pure maths, no pymunk. Powers prediction and assessment.
# ----------------------------------------------------------------------------
def vnorm(vx, vy):
    d = math.hypot(vx, vy)
    if d < 1e-12:
        return (0.0, 0.0)
    return (vx / d, vy / d)


def ray_circle_first_hit(cx, cy, dx, dy, tx, ty, contact_dist):
    """First t >= 0 where a point moving along unit (dx,dy) from (cx,cy) is
    exactly contact_dist from (tx,ty) — the ghost-ball solve."""
    fx, fy = cx - tx, cy - ty
    b = fx * dx + fy * dy
    c = fx * fx + fy * fy - contact_dist * contact_dist
    disc = b * b - c
    if disc < 0.0:
        return None
    root = math.sqrt(disc)
    t = -b - root
    if t < 0.0:
        t = -b + root
        if t < 0.0:
            return None
    return t


def ghost_ball(cue_pos, aim_dir, targets, r_cue, r_obj):
    """First object ball struck along aim_dir; ghost centre, object line,
    cue tangent, contact fullness (1.0 full ball .. 0.0 thinnest edge)."""
    dx, dy = vnorm(*aim_dir)
    if dx == 0.0 and dy == 0.0:
        return None
    best_t, best_target = None, None
    for (tx, ty) in targets:
        t = ray_circle_first_hit(cue_pos[0], cue_pos[1], dx, dy, tx, ty, r_cue + r_obj)
        if t is not None and (best_t is None or t < best_t):
            best_t, best_target = t, (tx, ty)
    if best_t is None:
        return None
    gx, gy = cue_pos[0] + dx * best_t, cue_pos[1] + dy * best_t
    ox, oy = vnorm(best_target[0] - gx, best_target[1] - gy)
    dot = dx * ox + dy * oy
    cue_dir = vnorm(dx - dot * ox, dy - dot * oy)
    return {
        "ghost": (gx, gy),
        "target": best_target,
        "obj_dir": (ox, oy),
        "cue_dir": cue_dir,
        "fullness": max(0.0, min(1.0, dot)),
        "t": best_t,
    }


def ray_rect_exit(cx, cy, dx, dy, inset):
    """First point where a ball centre travelling along (dx,dy) meets the
    playing rect inset by the ball radius, or None if degenerate."""
    x0, y0, x1, y1 = play_rect()
    x0, y0, x1, y1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
    best = None
    if dx > 1e-12:
        t = (x1 - cx) / dx
        if t >= 0:
            best = t if best is None else min(best, t)
    elif dx < -1e-12:
        t = (x0 - cx) / dx
        if t >= 0:
            best = t if best is None else min(best, t)
    if dy > 1e-12:
        t = (y1 - cy) / dy
        if t >= 0:
            best = t if best is None else min(best, t)
    elif dy < -1e-12:
        t = (y0 - cy) / dy
        if t >= 0:
            best = t if best is None else min(best, t)
    if best is None:
        return None
    return (cx + dx * best, cy + dy * best)


def reflect_off_rect(hit, d, inset, eps=1e-6):
    """Reflect direction d at a point on the inset playing rect boundary.
    Flips the component normal to whichever wall was struck."""
    x0, y0, x1, y1 = play_rect()
    x0, y0, x1, y1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
    dx, dy = d
    if abs(hit[0] - x0) < eps or abs(hit[0] - x1) < eps:
        dx = -dx
    if abs(hit[1] - y0) < eps or abs(hit[1] - y1) < eps:
        dy = -dy
    return (dx, dy)


def one_bounce_path(start, d, inset, tail=0.40):
    """Prediction helper (decision 3A): path from start along d to the first
    cushion, plus a reflected tail segment. Returns list of points."""
    d = vnorm(*d)
    if d == (0.0, 0.0):
        return [start]
    hit = ray_rect_exit(start[0], start[1], d[0], d[1], inset)
    if hit is None:
        return [start]
    d2 = reflect_off_rect(hit, d, inset)
    tail_end = (hit[0] + d2[0] * tail, hit[1] + d2[1] * tail)
    return [start, hit, tail_end]


def pot_assessment(gb):
    """Best-aligned pocket for the object line plus a difficulty heuristic:
    angular error vs pocket acceptance half-angle, cut thinness, cue travel.
    An estimate, not a promise."""
    tx, ty = gb["target"]
    ox, oy = gb["obj_dir"]
    best = None
    for (pc, cap_r) in capture_points():
        dx, dy = pc[0] - tx, pc[1] - ty
        dist = math.hypot(dx, dy)
        if dist < 1e-9:
            continue
        cosang = max(-1.0, min(1.0, (ox * dx + oy * dy) / dist))
        ang = math.acos(cosang)
        if best is None or ang < best[1]:
            best = (pc, ang, dist, cap_r)
    if best is None:
        return None
    pc, ang, dist, cap_r = best
    tol = math.asin(min(1.0, cap_r / max(dist, cap_r)))
    thin = max(0.15, gb["fullness"])
    p = math.exp(-0.5 * (ang / max(tol, 1e-9)) ** 2)
    p *= thin ** 0.5
    p *= math.exp(-gb["t"] / 7.0)
    return {"pocket": pc, "angle_deg": math.degrees(ang),
            "dist": dist, "prob": max(0.0, min(1.0, p))}


def seg_point_dist(a, b, p):
    """Shortest distance from point p to segment ab."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-18:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


CORRIDOR_SIGMA_K = 2.0   # r20: how many sigma of aim jitter the corridor check
                         # must survive. 2.0 = a ~95% band; see cue_corridor().


def corridor_clear(a, b, clearance, obstacles):
    """True if no obstacle centre lies within `clearance` of segment ab.
    Used by the AI to check the cue path and the object-ball path."""
    return all(seg_point_dist(a, b, ob) >= clearance for ob in obstacles)


def cue_corridor(r_cue, r_obj, jitter, t_cue):
    """r20: half-width the CUE path must keep clear of any obstacle centre.

    Two bugs are fixed here, and they compounded (measured: ~10% of ALL pot
    attempts struck the wrong ball first, flat across every confidence bin, and
    those attempts potted at 1.4% while being rated 56%).

    1. GEOMETRY. Two balls graze when their centres are (r_cue + r_obj) apart,
       so that IS the clearance. The old code passed `r_cue + r_obj - 0.002`,
       an unjustified 2mm shave off the very margin the test exists to enforce
       -- a ball 2mm inside a genuine collision was reported clear.

    2. JITTER. The old check validated the IDEAL aim line, but _execute() then
       perturbs that line by aim_jitter before the cue is struck. So the AI was
       clearing a line it had no intention of shooting. The lateral drift at the
       object ball is jitter * t_cue, which routinely DWARFS the margin that was
       shaved off: at t_cue 0.9m, 1 sigma is already 9.9mm.

    Adding CORRIDOR_SIGMA_K sigma of that drift makes the check ask the right
    question -- "will the shot I am ACTUALLY going to play clear this ball?"
    rather than "would a perfect robot clear it?". It is also properly emergent:
    a jittery player demands wider corridors and so plays more conservatively,
    and that falls straight out of the existing aim_jitter parameter rather than
    any new rule or scripted caution."""
    return r_cue + r_obj + CORRIDOR_SIGMA_K * jitter * max(0.0, t_cue)


def object_corridor(r_obj, jitter, t_cue):
    """r20: half-width the OBJECT ball's path to the pocket must keep clear.

    Two object balls graze at (2 * r_obj) apart -- the old code passed
    `2*r_obj - 0.006`, a 6mm shave, so up to 6mm of REAL overlap was called
    clear. The object ball carries no aim jitter of its own, but it inherits the
    cue's: an aim error rotates the contact point, which swings the object
    ball's departure line. Same CORRIDOR_SIGMA_K allowance, same reasoning."""
    return 2.0 * r_obj + CORRIDOR_SIGMA_K * jitter * max(0.0, t_cue)


def pot_estimate(cp, t, pc, cap_r, r_cue, r_obj, jitter):
    """Analytic pot-chance estimate for a cue ball at cp potting the ball at
    t into pocket capture point pc: ghost-ball aim, pocket acceptance angle
    narrowed by cut thinness and by cue-ball throw distance, distance decay.
    Single source of truth shared by the AI's shot choice and its leave-quality
    assessment (R5). Returns None if the shot is degenerate or the cut too thin.

    Calibration fix (r16): `jitter` is an aim-angle error measured at the CUE
    ball; `tol` is a pocket-acceptance angle measured at the OBJECT ball, over
    the object-to-pocket distance. These pivot from different points separated
    by t_cue (the cue-to-object travel distance) -- comparing them directly,
    as the pre-r16 formula did, ignores that the same angular aim error swings
    the actual contact point further off target the longer the cue ball has to
    travel to reach it. `lever` folds that in: it is 1.0 at point-blank range
    (t_cue -> 0, unchanged from the old formula) and shrinks smoothly as t_cue
    grows relative to the ball-to-ball contact scale (r_cue + r_obj, ~51mm --
    far smaller than a typical 0.3-2m shot), narrowing `allowed` accordingly."""
    d_tp = math.dist(t, pc)
    if d_tp < 1e-6:
        return None
    od = vnorm(pc[0] - t[0], pc[1] - t[1])
    G = (t[0] - od[0] * (r_cue + r_obj), t[1] - od[1] * (r_cue + r_obj))
    aim = (G[0] - cp[0], G[1] - cp[1])
    t_cue = math.hypot(*aim)
    if t_cue < 1e-6:
        return None
    ad = vnorm(*aim)
    fullness = ad[0] * od[0] + ad[1] * od[1]
    if fullness < 0.10:
        return None                 # cut too thin / wrong side
    tol = math.asin(min(1.0, cap_r / max(d_tp, cap_r)))
    contact = r_cue + r_obj
    lever = contact / (t_cue + contact)   # r16: cue-throw lever arm, 1.0 at t_cue=0
    allowed = tol * max(fullness, 0.15) * lever
    p = math.exp(-0.5 * (jitter / max(allowed, 1e-5)) ** 2)
    p *= math.exp(-t_cue / 10.0)
    return {"p": p, "aim": aim, "ghost": G, "ad": ad, "od": od,
            "fullness": fullness, "t_cue": t_cue, "d_tp": d_tp}


def estimate_leave(est, power, follow=0.0, side=0.0):
    """Analytic cue-ball leave (R5, decision A3; r9 phase 2 adds spin):
    estimated rest position of the cue ball after the pot described by `est`
    (a pot_estimate dict), struck at `power` m/s with `follow` (+ = follow,
    - = draw) and `side` english.

    Model: constant-decel approach to contact, tangent-line deflection scaled
    by cut thinness, a small carry along the aim line on full hits (negative --
    the 94 g cue rebounds), constant-decel travel with at most one cushion
    reflection at reduced energy.

    r9: `follow` adds (or, for draw, subtracts) a component along the aim line
    after contact -- the same physical effect FOLLOW_KICK applies in the live
    sim, so the estimate and the simulation agree on the sign and roughly on
    the magnitude. `side` biases the post-cushion direction, mirroring
    SIDE_KICK. Pure geometry, no simulation. An estimate, not a promise."""
    a = CFG["ROLL_DECEL"]
    v2 = max(0.0, power * power - 2.0 * a * est["t_cue"])
    v_c = math.sqrt(v2)
    f = est["fullness"]
    ad, od = est["ad"], est["od"]
    tvx, tvy = ad[0] - f * od[0], ad[1] - f * od[1]
    tn = math.hypot(tvx, tvy)
    v_tan = v_c * math.sqrt(max(0.0, 1.0 - f * f)) * CFG["LEAVE_TANGENT_KEEP"]
    v_fwd = v_c * f * f * CFG["LEAVE_CUE_CARRY"]
    # r9 phase 2: spin. Follow drives the cue on THROUGH the contact along the
    # aim line; draw (negative) pulls it back down that same line. Scaled by
    # the same FOLLOW_KICK constant the live sim uses, so the AI's prediction
    # and the physics don't disagree about which way the ball will go.
    v_fwd += v_c * CFG["FOLLOW_KICK"] * follow
    if tn > 1e-9:
        vx = (tvx / tn) * v_tan + ad[0] * v_fwd
        vy = (tvy / tn) * v_tan + ad[1] * v_fwd
    else:
        vx, vy = ad[0] * v_fwd, ad[1] * v_fwd
    s = math.hypot(vx, vy)
    if s < 1e-6:
        return {"rest": est["ghost"], "speed": 0.0}
    d = vnorm(vx, vy)
    travel = s * s / (2.0 * a)
    pos = est["ghost"]
    r = CFG["CUE_R_M"]
    hit = ray_rect_exit(pos[0], pos[1], d[0], d[1], r)
    d_wall = math.dist(pos, hit) if hit else float("inf")
    if travel <= d_wall:
        rest = (pos[0] + d[0] * travel, pos[1] + d[1] * travel)
    else:
        v_hit2 = max(0.0, s * s - 2.0 * a * d_wall)
        e = CFG["LEAVE_CUSHION_E"]
        rem = (e * e * v_hit2) / (2.0 * a)
        d2 = reflect_off_rect(hit, d, r)
        # r9 phase 2: side english deflects the rebound along the cushion
        # tangent, same sign convention as SIDE_KICK in _cue_cushion_contact.
        if abs(side) > 0.02:
            tx, ty = -d2[1], d2[0]
            k = CFG["SIDE_KICK"] * side
            d2 = vnorm(d2[0] + tx * k, d2[1] + ty * k)
        rest = (hit[0] + d2[0] * rem, hit[1] + d2[1] * rem)
        x0, y0, x1, y1 = play_rect()
        rest = (min(max(rest[0], x0 + r), x1 - r),
                min(max(rest[1], y0 + r), y1 - r))   # clamp beyond one bounce
    return {"rest": rest, "speed": s}


def scratch_risk(rest, speed):
    """r9 phase 2 (foul-risk term): 0..1 estimate that the cue ball ends up in
    a pocket -- i.e. a scratch, which is a foul. Pure geometry: how close the
    PREDICTED cue rest position sits to a capture point, relative to that
    pocket's capture radius, softened by how fast the cue is still moving
    (a cue crawling to a stop beside a jaw is far more likely to drop than one
    still travelling that merely passes nearby).

    This is deliberately an estimate over the predicted rest position, not a
    simulation: the AI stays emergent -- it scores a risk and lets utility do
    the rest -- rather than being scripted to avoid specific pockets."""
    worst = 0.0
    for (pc, cap_r) in capture_points():
        d = math.dist(rest, pc)
        if d >= cap_r * 3.0:
            continue
        near = max(0.0, 1.0 - d / (cap_r * 3.0))     # 1 at the pocket, 0 at 3r
        slow = 1.0 / (1.0 + speed)                   # slower -> likelier to drop
        worst = max(worst, near * (0.5 + 0.5 * slow))
    return min(1.0, worst)


def safety_quality(rest, opp_targets, obstacles, r_cue, r_obj, jitter):
    """r9 phase 2 (safety term): how GOOD a safety leaves the table, 0..1.
    A safety is good exactly when the opponent's best available pot is bad, so
    this is 1 - (their best pot chance from where we leave the cue). Snookers
    score highest, because corridor_clear inside leave_quality rejects every
    blocked line and their best chance collapses to zero.

    Note this scores the OPPONENT's prospects, which is why it takes their
    targets, not ours -- the one place in the AI where we evaluate the table
    from the other side."""
    opp_best = leave_quality(rest, opp_targets, obstacles, r_cue, r_obj, jitter)
    return 1.0 - opp_best


def leave_quality(rest, targets, obstacles, r_cue, r_obj, jitter):
    """Best analytic pot chance available from `rest` over `targets`,
    corridor-checked against `obstacles`. 0.0 if nothing is on (R5)."""
    best = 0.0
    for t in targets:
        obs = [o for o in obstacles if o != t]
        for (pc, cap_r) in capture_points():
            est = pot_estimate(rest, t, pc, cap_r, r_cue, r_obj, jitter)
            if est is None:
                continue
            if not corridor_clear(rest, est["ghost"],
                                  cue_corridor(r_cue, r_obj, jitter,
                                               est["t_cue"]), obs):
                continue
            if not corridor_clear(t, pc,
                                  object_corridor(r_obj, jitter,
                                                  est["t_cue"]), obs):
                continue
            if est["p"] > best:
                best = est["p"]
    return best


# ----------------------------------------------------------------------------
# Simulation layer — pymunk in metres/kg/seconds.
# ----------------------------------------------------------------------------
import pymunk  # noqa: E402  (import after geometry so geometry stays pure)
import cushion_path as cushion_geo  # noqa: E402  (R6 tangent-true table geometry)

COLL_CUE, COLL_OBJ, COLL_CUSHION = 1, 2, 3
# r17 (perf item 3): two pocket-sensor collision types, one per ball size, so
# the cue ball and object balls each get sensor shapes shrunk by THEIR OWN
# radius (see _build_pockets) -- a single shared sensor size would silently
# widen the capture zone for whichever ball is smaller than the other.
COLL_POCKET_CUE, COLL_POCKET_OBJ = 4, 5

# R6 Fork C: adopt cushion_path.py's tangent-true nose loop (22mm knuckle arcs,
# C1 jaws) as the physical cushions, driven at this table's 7ft dimensions and
# the WEPF 1.6x-diameter mouth. Rails keep the calibrated rail restitution; the
# non-rail pocket primitives are deadened so the throat swallows true shots
# rather than banking them, mirroring the legacy horn/back tuning. Flip
# USE_TANGENT_CUSHIONS to False to fall back to the legacy straight-facing
# builder for A/B comparison (drill/batch deltas are findings, not failures).
USE_TANGENT_CUSHIONS = True
CUSHION_JAW_E  = 0.25   # knuckle arcs + straight jaws (was 0.25 on legacy horns)
CUSHION_BACK_E = 0.10   # flat pocket backs, entirely behind the mouth (dead)


class Sim:
    """Owns the pymunk space, balls, cushions, pockets and the rack."""

    CUE_ID = 0

    def __init__(self, layout="default"):
        self.space = None
        self.balls = {}            # id -> (body, shape)
        self.colours = {}          # id -> 'cue'|'red'|'yellow'|'black' (persists past potting)
        self.black_id = None
        self.next_id = 1
        self.potted_log = []
        # r22: GAME-scoped pot history, in order. `potted_log` above is
        # SHOT-scoped -- strike() clears it every shot, deliberately (r9: the
        # rules must see what went down on THIS shot to judge a foul). The r12
        # potted-ball chamber wrongly read that same list expecting a whole-game
        # history, so it showed the current shot's pots and then emptied on the
        # next strike -- the "only shows one ball then it disappears" bug.
        # Two features wanted the same variable to mean two different things;
        # they now get one each. potted_log KEEPS its exact meaning (the rules
        # engine depends on it), and the chamber reads potted_all instead.
        # Never cleared by strike(); only a rebuild/new rack resets it.
        self.potted_all = []
        self.last_pot_events = []  # Increment 4b: (bid, colour, pos, radius)
                                    # captured in the MOST RECENT step() call
                                    # only -- a pure event report, consumed by
                                    # the render layer for the swallow
                                    # animation. Never read by physics/rules/
                                    # AI; potted_log remains the single
                                    # source of truth there.
        self.last_hit_events = []  # Sound effects: (kind, strength) logged
                                    # in the MOST RECENT step() call only --
                                    # 'strength' is arbiter.total_impulse's
                                    # magnitude, a physically-grounded proxy
                                    # for how hard the contact was, used to
                                    # scale playback volume. Pure event
                                    # logging, same as last_pot_events --
                                    # never applies any force itself, never
                                    # read by physics/rules/AI.
        self._live_side = 0.0
        self._live_follow = 0.0
        self._cue_prev = (0.0, 0.0)

        # --- Rules (r9 phase 1): shot-scoped event report ----------------------
        # UNLIKE last_pot_events/last_hit_events (per-STEP, pure, render/sound
        # only), these are per-SHOT and ARE read by the rules engine -- they
        # exist precisely because the most common real foul, "wrong ball hit
        # first", is NOT derivable from potted_log. potted_log records what went
        # DOWN; nothing recorded what the cue ball TOUCHED. Reset in strike(),
        # read by Game.on_rest() once the table settles.
        #
        # This is a DELIBERATE, signed-off exception to the standing rule that
        # the (COLL_OBJ, COLL_OBJ) handler carries "no gameplay behaviour,
        # ever": it now also feeds first-contact/cushion facts to the rules.
        # It still applies no force and alters no trajectory -- physics is
        # untouched; it only *observes*.
        self.first_contact = None      # colour of the FIRST object ball the cue
                                       # ball touched this shot (None = cue hit
                                       # nothing at all -> a foul in itself)
        self.cushion_after_contact = False  # did ANY ball reach a cushion after
                                            # the cue's first object contact?
        self._contact_made = False     # internal latch: has first contact
                                       # happened yet this shot?
        self.rebuild(layout=layout)

    # -- construction --------------------------------------------------------
    def rebuild(self, keep_positions=None, layout="default"):
        self.space = pymunk.Space()
        # CRITICAL in metre units: pymunk's default collision_slop is 0.1
        # space-units — 10 cm of allowed overlap. Set a sub-millimetre slop.
        self.space.collision_slop = 0.0002
        self.space.on_collision(collision_type_a=COLL_CUE, collision_type_b=COLL_OBJ,
                                post_solve=self._cue_ball_contact)
        self.space.on_collision(collision_type_a=COLL_CUE, collision_type_b=COLL_CUSHION,
                                post_solve=self._cue_cushion_contact)
        self.space.on_collision(collision_type_a=COLL_OBJ, collision_type_b=COLL_OBJ,
                                post_solve=self._obj_ball_contact)
        # Rules (r9): NEW handler. There was deliberately no (OBJ, CUSHION)
        # handler until now because nothing needed one. The "no cushion, no
        # pot" foul needs one -- pure observation, no force applied.
        self.space.on_collision(collision_type_a=COLL_OBJ, collision_type_b=COLL_CUSHION,
                                post_solve=self._obj_cushion_contact)
        # r17 (perf item 3): pocket capture moves into pymunk's own collision
        # detection (sensor shapes, built in _build_pockets below) instead of
        # a Python distance loop polled every substep. begin() only APPENDS
        # to self._pending_pot_ids -- it never mutates the space mid-step
        # (unsafe) -- and _capture_pockets() (called right after space.step(),
        # same cadence as before) does the actual removal/logging.
        self.space.on_collision(collision_type_a=COLL_CUE, collision_type_b=COLL_POCKET_CUE,
                                begin=self._pocket_sensor_hit)
        self.space.on_collision(collision_type_a=COLL_OBJ, collision_type_b=COLL_POCKET_OBJ,
                                begin=self._pocket_sensor_hit)
        self._pending_pot_ids = set()
        self._build_cushions()
        self._build_pockets()
        old = keep_positions or {}
        self.balls = {}
        if old:
            for bid, pos in old.items():
                self._add_ball(bid, pos, self.colours.get(bid, "red"))
        elif layout == "default":
            self._default_layout()
        # layout == "empty": leave the table bare (drills, rack setup)

    def _build_cushions(self):
        if USE_TANGENT_CUSHIONS:
            self._build_cushions_tangent()
        else:
            self._build_cushions_legacy()

    def _build_cushions_tangent(self):
        """R6 Fork C: tangent-true nose loop from cushion_path.py, driven at
        this table's 7ft dimensions and the WEPF 1.6x mouth. Built primitive
        by primitive (arcs tessellated at 3 deg) so each surface class carries
        its own restitution: the six rails stay live at the calibrated rail
        elasticity; pocket knuckles and jaws are deadened so the throat
        swallows true shots; the flat pocket backs (entirely behind the mouth)
        are dead. Coordinates convert mm -> m at the build boundary."""
        MM = 1000.0
        cushion_geo.configure(
            play_w=CFG["PLAY_W_M"] * MM, play_h=CFG["PLAY_H_M"] * MM,
            corner_mouth=CFG["POCKET_MOUTH_M"] * MM,
            middle_mouth=CFG["POCKET_MIDDLE_MOUTH_M"] * MM,
        )
        e  = CFG["CUSHION_ELASTICITY"]
        fr = CFG["CUSHION_FRICTION"]
        nose = 0.005   # cushion nose radius (m) — matches legacy
        rail_idx = {0, 6, 12, 18, 24, 30}     # the six straight rails
        back_idx = {3, 9, 15, 21, 27, 33}     # the six flat pocket backs
        path = cushion_geo.build_cushion_path()

        def seg(a, b, elast):
            s = pymunk.Segment(self.space.static_body, a, b, nose)
            s.elasticity = elast
            s.friction = fr
            s.collision_type = COLL_CUSHION
            self.space.add(s)

        for i, prim in enumerate(path):
            elast = e if i in rail_idx else (
                CUSHION_BACK_E if i in back_idx else CUSHION_JAW_E)
            if prim[0] == "line":
                pts = [prim[1], prim[2]]
            else:
                _, c, r, a0, a1 = prim
                n = max(2, int(math.ceil(abs(a1 - a0) / 3.0)))
                pts = [cushion_geo.arc_point(c, r, a0 + (a1 - a0) * k / n)
                       for k in range(n + 1)]
            for j in range(len(pts) - 1):
                a = (pts[j][0] / MM, pts[j][1] / MM)
                b = (pts[j + 1][0] / MM, pts[j + 1][1] / MM)
                seg(a, b, elast)

    def _build_cushions_legacy(self):
        x0, y0, x1, y1 = play_rect()
        pr = pocket_half_mouth()
        # Corner setback so the diagonal opening equals the spec mouth width
        cpr = pr * math.sqrt(2.0)
        e = CFG["CUSHION_ELASTICITY"]
        fr = CFG["CUSHION_FRICTION"]
        mx = (x0 + x1) / 2.0
        nose = 0.005   # cushion nose radius (m)

        def seg(a, b, elast):
            s = pymunk.Segment(self.space.static_body, a, b, nose)
            s.elasticity = elast
            s.friction = fr
            s.collision_type = COLL_CUSHION
            self.space.add(s)

        for a, b in [
            ((x0 + cpr, y0), (mx - pr, y0)), ((mx + pr, y0), (x1 - cpr, y0)),
            ((x0 + cpr, y1), (mx - pr, y1)), ((mx + pr, y1), (x1 - cpr, y1)),
            ((x0, y0 + cpr), (x0, y1 - cpr)), ((x1, y0 + cpr), (x1, y1 - cpr)),
        ]:
            seg(a, b, e)

        # Pocket jaws: horns funnel true shots in, rattle near-misses out.
        # Blackball pockets have rounded entrances and nearly parallel sides —
        # jaw banking does not work, so horns are deadened (low elasticity).
        s2 = math.sqrt(2.0) / 2.0
        corners = [
            ((x0, y0), (-s2, -s2), (cpr, 0.0), (0.0, cpr)),
            ((x1, y0), (s2, -s2), (-cpr, 0.0), (0.0, cpr)),
            ((x0, y1), (-s2, s2), (cpr, 0.0), (0.0, -cpr)),
            ((x1, y1), (s2, s2), (-cpr, 0.0), (0.0, -cpr)),
        ]
        for (c, o, ra, rb) in corners:
            for roff in (ra, rb):
                ex, ey = c[0] + roff[0], c[1] + roff[1]
                seg((ex, ey), (ex + o[0] * pr * 0.9, ey + o[1] * pr * 0.9), 0.25)
            bcx, bcy = c[0] + o[0] * pr * 1.6, c[1] + o[1] * pr * 1.6
            tx, ty = -o[1], o[0]
            seg((bcx - tx * pr * 1.1, bcy - ty * pr * 1.1),
                (bcx + tx * pr * 1.1, bcy + ty * pr * 1.1), 0.1)
        for (py, oy) in [(y0, -1.0), (y1, 1.0)]:
            for sx in (-1.0, 1.0):
                seg((mx + sx * pr, py),
                    (mx + sx * pr * 0.7, py + oy * pr * 0.85), 0.25)
            seg((mx - pr * 1.1, py + oy * pr * 1.5),
                (mx + pr * 1.1, py + oy * pr * 1.5), 0.1)

    def _build_pockets(self):
        """r17 (perf item 3): one sensor shape per pocket per ball SIZE (cue
        vs object), attached to the static body. Sensor shapes report overlap
        without any physical response, so this adds no force/behaviour of its
        own -- it only tells us when a ball has entered a pocket, via pymunk's
        own collision broad-phase instead of a Python distance loop.

        Radius is cap_r MINUS the relevant ball's own radius. This is the bit
        that makes it an exact substitute rather than a lenient one: a plain
        cap_r-radius sensor would fire on CIRCLE overlap (distance < cap_r +
        ball_radius), which is a bigger, earlier-triggering zone than the old
        centre-point test (distance < cap_r alone). Shrinking the sensor by
        the ball's radius first means overlap now happens at EXACTLY
        distance < (cap_r - r) + r == cap_r -- the same threshold as before,
        just tested by pymunk's C broad-phase instead of our own math.dist
        loop. Clamped at a small epsilon in case a live ball-radius slider is
        ever pushed larger than a pocket's own capture radius (not the case
        at any WEPF-spec default, where cap_r - r is 7-11mm of headroom)."""
        for (pc, cap_r) in capture_points():
            r_cue = max(1e-6, cap_r - CFG["CUE_R_M"])
            s_cue = pymunk.Circle(self.space.static_body, r_cue, pc)
            s_cue.sensor = True
            s_cue.collision_type = COLL_POCKET_CUE
            self.space.add(s_cue)
            r_obj = max(1e-6, cap_r - ball_r())
            s_obj = pymunk.Circle(self.space.static_body, r_obj, pc)
            s_obj.sensor = True
            s_obj.collision_type = COLL_POCKET_OBJ
            self.space.add(s_obj)

    def _pocket_sensor_hit(self, arbiter, space, data):
        """begin() callback for a ball/pocket-sensor overlap. Queues the ball
        id only -- NEVER mutates self.balls or self.space here (unsafe mid-
        step); _capture_pockets(), called right after space.step() returns,
        does the actual removal at the same cadence pot capture always ran
        at (every substep, not just once per frame -- see its docstring)."""
        for bid, (body, shape) in self.balls.items():
            if shape in arbiter.shapes:
                self._pending_pot_ids.add(bid)
                return

    def _default_layout(self):
        x0, y0, x1, y1 = play_rect()
        w, h = x1 - x0, y1 - y0
        self._add_ball(self.CUE_ID, (x0 + w * 0.22, y0 + h * 0.5), "cue")
        self._add_ball(self.alloc_id(), (x0 + w * 0.62, y0 + h * 0.42), "red")
        self._add_ball(self.alloc_id(), (x0 + w * 0.70, y0 + h * 0.58), "yellow")
        self._add_ball(self.alloc_id(), (x0 + w * 0.80, y0 + h * 0.30), "red")

    def alloc_id(self):
        i = self.next_id
        self.next_id += 1
        return i

    def _add_ball(self, bid, pos, colour="red"):
        if bid == self.CUE_ID:
            r, mass = CFG["CUE_R_M"], CFG["CUE_MASS_KG"]
            colour = "cue"
        else:
            r, mass = ball_r(), CFG["BALL_MASS_KG"]
        body = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, r))
        body.position = pos
        shape = pymunk.Circle(body, r)
        shape.elasticity = CFG["BALL_ELASTICITY"]
        shape.friction = 0.05    # ball-ball friction, measured 0.03-0.08
        shape.collision_type = COLL_CUE if bid == self.CUE_ID else COLL_OBJ
        self.space.add(body, shape)
        self.balls[bid] = (body, shape)
        self.colours[bid] = colour
        if colour == "black":
            self.black_id = bid
        return bid

    def rack(self):
        """Blackball rack: 7 red, 7 yellow, black ON THE SPOT (centre of the
        top half), apex toward baulk. One legal arrangement — the rules only
        fix the black's position. Cue ball respotted to the baulk line."""
        self.clear_objects()
        x0, y0, x1, y1 = play_rect()
        w, h = x1 - x0, y1 - y0
        r = ball_r()
        spot = (x0 + w * 0.75, y0 + h * 0.5)      # pyramid spot
        row_dx = r * math.sqrt(3.0) * 1.001
        pitch = 2.0 * r * 1.001
        pattern = [
            ["red"],
            ["yellow", "red"],
            ["red", "black", "yellow"],
            ["yellow", "red", "yellow", "red"],
            ["red", "yellow", "red", "yellow", "yellow"],
        ]
        apex_x = spot[0] - 2 * row_dx             # so the black lands on the spot
        ids = []
        for i, row in enumerate(pattern):
            rx = apex_x + i * row_dx
            for j, colour in enumerate(row):
                ry = spot[1] + (j - i / 2.0) * pitch
                ids.append(self._add_ball(self.alloc_id(), (rx, ry), colour))
        # Cue to the baulk line, centre
        cue = self.cue()
        baulk_x = x0 + w * CFG["BAULK_FRAC"]
        if cue is None:
            self._add_ball(self.CUE_ID, (baulk_x, y0 + h / 2), "cue")
        else:
            cue.position = (baulk_x, y0 + h / 2)
            cue.velocity = (0.0, 0.0)
        return ids

    def break_shot(self, power=6.0, cue_y_off=0.0, aim_off=0.0,
                   side=0.0, follow=0.0):
        """Parameterised break (decision 1B). cue_y_off: lateral cue position
        on the baulk line (m). aim_off: lateral offset of the aim point across
        the pack apex (m) — 0 is dead full on the apex ball."""
        x0, y0, x1, y1 = play_rect()
        w, h = x1 - x0, y1 - y0
        cue = self.cue()
        cue.position = (x0 + w * CFG["BAULK_FRAC"], y0 + h / 2 + cue_y_off)
        cue.velocity = (0.0, 0.0)
        objs = self.object_positions()
        apex = min(objs, key=lambda p: p[0]) if objs else (x0 + w * 0.75, y0 + h / 2)
        aim = (apex[0] - cue.position.x, apex[1] + aim_off - cue.position.y)
        self.strike(aim, power, side=side, follow=follow)

    def add_random_ball(self, rng=random):
        x0, y0, x1, y1 = play_rect()
        r = ball_r()
        for _ in range(200):
            p = (rng.uniform(x0 + r * 2, x1 - r * 2), rng.uniform(y0 + r * 2, y1 - r * 2))
            if all(math.dist(p, b.position) > r * 2.4 for b, _ in self.balls.values()):
                return self._add_ball(self.alloc_id(), p, "red")
        return None

    def clear_objects(self):
        for bid in [i for i in self.balls if i != self.CUE_ID]:
            body, shape = self.balls.pop(bid)
            self.space.remove(body, shape)
        self.black_id = None

    def set_ball_radius(self, r_m):
        CFG["BALL_R_M"] = max(0.015, min(0.035, r_m))
        keep = {bid: tuple(b.position) for bid, (b, _) in self.balls.items()}
        self.rebuild(keep_positions=keep)

    def set_cushion_elasticity(self, e):
        CFG["CUSHION_ELASTICITY"] = max(0.05, min(1.0, e))
        keep = {bid: tuple(b.position) for bid, (b, _) in self.balls.items()}
        vels = {bid: tuple(b.velocity) for bid, (b, _) in self.balls.items()}
        self.rebuild(keep_positions=keep)
        for bid, (b, _) in self.balls.items():
            b.velocity = vels.get(bid, (0, 0))

    def toggle_cue_size(self):
        """WEPF 1-7/8" 94 g cue (default) <-> casual full-size 2" 116 g."""
        if abs(CFG["CUE_R_M"] - 0.0238) < 1e-9:
            CFG["CUE_R_M"] = CFG["CUE_CASUAL_R_M"]
            CFG["CUE_MASS_KG"] = CFG["CUE_CASUAL_MASS_KG"]
        else:
            CFG["CUE_R_M"] = 0.0238
            CFG["CUE_MASS_KG"] = 0.094
        keep = {bid: tuple(b.position) for bid, (b, _) in self.balls.items()}
        self.rebuild(keep_positions=keep)

    # -- runtime -------------------------------------------------------------
    def cue(self):
        return self.balls.get(self.CUE_ID, (None, None))[0]

    def strike(self, aim_dir, power, side=0.0, follow=0.0):
        body = self.cue()
        if body is None:
            return
        dx, dy = vnorm(*aim_dir)
        body.velocity = (dx * power, dy * power)
        self._live_side = max(-1.0, min(1.0, side))
        self._live_follow = max(-1.0, min(1.0, follow))
        self.potted_log = []
        # Rules (r9): shot-scoped, so they reset here with potted_log -- not in
        # step(), which fires many times per shot and would wipe the very facts
        # the rules need to see at rest.
        self.first_contact = None
        self.cushion_after_contact = False
        self._contact_made = False

    def step(self, dt):
        self.last_pot_events = []  # Increment 4b: fresh per step() call
        self.last_hit_events = []  # Sound effects: fresh per step() call
        steps = max(1, int(round(dt / CFG["PHYS_DT"])))
        h = CFG["PHYS_DT"]
        spin_decay = math.exp(-CFG["SPIN_DECAY"] * h)
        dv = CFG["ROLL_DECEL"] * h
        for _ in range(steps):
            cue = self.cue()
            if cue is not None:
                self._cue_prev = (cue.velocity.x, cue.velocity.y)
            # Constant-deceleration rolling resistance (the physical model)
            for body, _ in self.balls.values():
                sp = body.velocity.length
                if sp > 1e-9:
                    if sp <= dv:
                        body.velocity = (0.0, 0.0)
                    else:
                        f = (sp - dv) / sp
                        body.velocity = (body.velocity.x * f, body.velocity.y * f)
            self.space.step(h)
            # Capture every sub-step, not just per frame: at max power a ball
            # can cross a pocket's capture zone and tunnel through the thin
            # deadened back segment between frame boundaries (rare escape found
            # after the R6 tangent-true adoption). Capture points sit deep in
            # the throat, so this only catches genuine droppers, not rattlers.
            self._capture_pockets()
            self._live_side *= spin_decay
            self._live_follow *= spin_decay
        self._park_slow_balls()
        self._capture_pockets()

    def _park_slow_balls(self):
        for body, _ in self.balls.values():
            if body.velocity.length < CFG["STOP_SPEED"]:
                body.velocity = (0.0, 0.0)
                body.angular_velocity = 0.0

    def _capture_pockets(self):
        # r17 (perf item 3): DETECTION now happens via the pocket sensor
        # shapes' begin() callback during space.step() (see _build_pockets /
        # _pocket_sensor_hit); this only does the REMOVAL, at the same
        # cadence as before (called right after every space.step(), not just
        # once per frame -- same tunnelling protection this always had).
        if not self._pending_pot_ids:
            return
        hits, self._pending_pot_ids = self._pending_pot_ids, set()
        pots = []
        for bid, (body, shape) in list(self.balls.items()):
            if bid in hits:
                pots.append((bid, tuple(body.position), shape.radius))
        for bid, pos, radius in pots:
            body, shape = self.balls.pop(bid)
            self.space.remove(body, shape)
            self.potted_log.append(bid)
            self.potted_all.append(bid)   # r22: game-scoped, survives strike()
            self.last_pot_events.append((bid, self.colours.get(bid, "red"), pos, radius))
            if bid == self.CUE_ID:
                # Sandbox/rules-lite behaviour: respot behind baulk, nudged
                self._live_side = 0.0
                self._live_follow = 0.0
                self._respot_cue()


    def _record_first_contact(self, arbiter):
        """Rules (r9): latch the colour of the FIRST object ball the cue ball
        touched this shot. Pure observation -- applies no force, alters no
        trajectory. Identifies the ball by matching the arbiter's shapes back
        to self.balls, since pymunk hands us shapes, not our ids."""
        if self._contact_made:
            return
        for bid, (body, shape) in self.balls.items():
            if bid == self.CUE_ID:
                continue
            if shape in arbiter.shapes:
                self.first_contact = self.colours.get(bid)
                self._contact_made = True
                return

    # -- spin callbacks (pymunk post_solve) -----------------------------------
    def _cue_ball_contact(self, arbiter, space, data):
        self.last_hit_events.append(("ball_hit", arbiter.total_impulse.length))
        # Rules (r9): first-contact latch, unconditional, BEFORE the early
        # return below -- a soft graze that produces no follow-kick is still
        # very much a contact as far as the rules are concerned.
        self._record_first_contact(arbiter)
        if abs(self._live_follow) < 0.02:
            return
        cue = self.cue()
        if cue is None:
            return
        pvx, pvy = self._cue_prev
        speed = math.hypot(pvx, pvy)
        if speed < 0.01:
            return
        k = CFG["FOLLOW_KICK"] * self._live_follow * speed
        cue.velocity = (cue.velocity.x + (pvx / speed) * k,
                        cue.velocity.y + (pvy / speed) * k)
        self._live_follow = 0.0

    def _obj_ball_contact(self, arbiter, space, data):
        # Sound effects, and (r9, deliberate signed-off exception) rules
        # observation. This handler previously carried "no gameplay behaviour,
        # ever"; it now also feeds the rules engine, because "wrong ball hit
        # first" cannot be derived from potted_log. It STILL applies no force
        # and alters no trajectory -- physics is completely untouched. It only
        # observes.
        self.last_hit_events.append(("ball_hit", arbiter.total_impulse.length))

    def _obj_cushion_contact(self, arbiter, space, data):
        # Rules (r9): new handler. WEPF requires that, after the cue ball
        # strikes a legal object ball, EITHER a ball is potted OR some ball
        # reaches a cushion -- otherwise it's a foul (the "no cushion, no pot"
        # rule, which stops a player nudging balls around safely forever).
        # Cue-cushion contacts were already handled for side-spin; object-ball
        # cushion contacts had no handler at all because nothing needed one.
        # This feature needs one. Pure observation, applies no force.
        if self._contact_made:
            self.cushion_after_contact = True

    def _cue_cushion_contact(self, arbiter, space, data):
        # Rules (r9): a cue-ball cushion contact counts for the "no cushion,
        # no pot" rule too, but ONLY if it happens after the first object
        # contact -- a cue ball that hits a cushion on its way TO the object
        # ball satisfies nothing.
        if self._contact_made:
            self.cushion_after_contact = True
        if abs(self._live_side) < 0.02:
            return
        cue = self.cue()
        if cue is None:
            return
        n = arbiter.normal
        tx, ty = -n.y, n.x
        speed = cue.velocity.length
        k = CFG["SIDE_KICK"] * self._live_side * speed
        cue.velocity = (cue.velocity.x + tx * k, cue.velocity.y + ty * k)
        self._live_side *= 0.35

    # -- queries ---------------------------------------------------------------
    def all_at_rest(self):
        return all(b.velocity.length < 1e-9 for b, _ in self.balls.values())

    def run_to_rest(self, timeout_s=None):
        timeout_s = timeout_s or CFG["REST_TIMEOUT_S"]
        t, dt = 0.0, 1.0 / 60.0
        while t < timeout_s:
            self.step(dt)
            t += dt
            if self.all_at_rest():
                return t
        return t

    def in_bounds(self):
        x0, y0, x1, y1 = play_rect()
        slack = pocket_half_mouth() * 2.5
        return all(
            (x0 - slack) <= b.position.x <= (x1 + slack)
            and (y0 - slack) <= b.position.y <= (y1 + slack)
            for b, _ in self.balls.values()
        )

    def remaining(self, colour):
        """Count of balls of the given colour still on the table."""
        return sum(1 for bid in self.balls
                   if bid != self.CUE_ID and self.colours.get(bid) == colour)

    def _respot_cue(self):
        """Respot the cue on the baulk line, nudged clear of any ball."""
        x0, y0, x1, y1 = play_rect()
        bx = x0 + (x1 - x0) * CFG["BAULK_FRAC"]
        cy = (y0 + y1) / 2
        r = ball_r()
        for k in range(0, 30):
            off = (k // 2 + 1) * r * (1 if k % 2 == 0 else -1) if k else 0.0
            p = (bx, cy + off)
            if y0 + r < p[1] < y1 - r and all(
                    math.dist(p, b.position) > 2.2 * r
                    for b, _ in self.balls.values()):
                self._add_ball(self.CUE_ID, p, "cue")
                return
        self._add_ball(self.CUE_ID, (bx, cy), "cue")

    def object_positions(self):
        return [tuple(b.position) for bid, (b, _) in self.balls.items() if bid != self.CUE_ID]

    def potted_colours(self):
        """SHOT-scoped: what went down on the CURRENT shot. The rules engine
        depends on this being cleared by strike() -- do not repoint it."""
        return [self.colours.get(b, "?") for b in self.potted_log]

    def potted_colours_all(self):
        """r22, GAME-scoped: everything potted this rack, in the order it went
        down. This is what the r12 potted-ball chamber wants -- a real table's
        chamber shows the whole game's history, not just the last shot."""
        return [self.colours.get(b, "?") for b in self.potted_all]


# ----------------------------------------------------------------------------
# Rules-lite blackball (decision 1B)
# ----------------------------------------------------------------------------
class Game:
    """WEPF blackball rules engine (r9 -- was "rules-lite" through R6).

    Now covered:
      * turn order; colour assignment on the first potted colour (open table)
      * pot-your-colour-to-continue
      * FOULS (r9 phase 1), all of which now end the visit and hand the
        opponent a free shot plus two visits:
          - scratch (cue potted)             -> cue respotted behind baulk
          - cue ball hits NOTHING at all
          - WRONG BALL FIRST: the cue's first object contact was not a legal
            colour. This is the most common real foul and was completely
            invisible before, because on_rest() only ever looked at what went
            DOWN (potted_log), never at what the cue ball TOUCHED. It needs
            sim.first_contact, which is why the collision handlers now observe
            it (a deliberate, signed-off exception -- they still apply no force).
          - NO CUSHION, NO POT: after a legal contact, nothing was potted and
            no ball reached a cushion. Stops a player nudging balls around
            safely forever.
      * FREE SHOT + TWO VISITS (r9 phase 3): after a foul, the incoming player
        gets two visits (they may miss once and still shoot again) and, on the
        first of them, a free shot -- wrong-ball-first does not foul.
      * black legal only once your colour is cleared BEFORE the shot; potting
        the black early, or with a foul, loses.

    Simplifications still standing (documented, not accidental): on a free shot
    the player may hit any ball first, but potting the opponent's colour still
    doesn't extend their visit; no re-racks; no nominated-ball declarations.
    """

    def __init__(self, names=("SHARK", "STEADY"), controllers=("ai", "ai")):
        self.names = list(names)
        self.controllers = list(controllers)
        self.current = 0
        self.colours = {}          # player index -> 'red'|'yellow'
        self.over = False
        self.winner = None
        self.reason = ""
        self.visits = 0
        self.fouls = 0
        self.shots = 0
        self.last_event = "break to open"
        # r9 phase 3 -- penalty state, always describing the CURRENT striker.
        self.free_shot = False     # this shot cannot foul on wrong-ball-first
        self.visits_left = 1       # 2 after the opponent fouls: miss once, shoot again
        # r13: ball in hand. True on the BREAK and after any FOUL -- the striker
        # may reposition the cue ball anywhere in baulk before playing (WEPF
        # blackball: "in hand in baulk"). NOT the D -- see baulk_rect().
        self.ball_in_hand = True

    def own_colour(self, i=None):
        return self.colours.get(self.current if i is None else i)

    def legal_colours(self, sim):
        """Colours the current striker may target."""
        own = self.own_colour()
        if self.free_shot:
            # r9: on a free shot ANY ball may be struck first, so everything
            # on the table is a legal first contact.
            return ["red", "yellow", "black"] if own is None or sim.remaining(own) == 0 \
                   else ["red", "yellow"]
        if own is None:
            return ["red", "yellow"]
        if sim.remaining(own) == 0:
            return ["black"]
        return [own]

    def assess_foul(self, sim, legal, potted, scratch):
        """r9 phase 1: pure foul determination for the shot just completed.
        Returns a reason string, or None if the shot was legal. Split out from
        on_rest() specifically so it can be unit-tested without a live table."""
        if scratch:
            return "scratch"
        obj_potted = [c for c in potted if c in ("red", "yellow", "black")]
        if sim.first_contact is None:
            # An object ball in a pocket is itself proof the cue ball hit
            # something -- trust the evidence over a missing latch. Without
            # this, any path that pots a ball without the contact handler
            # firing (a replayed//constructed state, a resumed shot) would be
            # wrongly called a foul. Only a shot that potted NOTHING can
            # honestly be judged "the cue ball never touched anything".
            if not obj_potted:
                return "no contact"
        elif not self.free_shot and sim.first_contact not in legal:
            return f"wrong ball first ({sim.first_contact})"
        if not potted and not sim.cushion_after_contact:
            return "no cushion, no pot"
        return None

    def on_rest(self, sim):
        """Apply the rules to the shot just completed."""
        if self.over:
            return
        self.shots += 1
        striker = self.current
        potted = sim.potted_colours()
        scratch = "cue" in potted
        obj = [c for c in potted if c in ("red", "yellow")]
        own = self.colours.get(striker)
        # Snapshot the legality the shot was PLAYED under, before any colour
        # assignment below mutates it.
        legal = self.legal_colours(sim)
        was_free = self.free_shot

        if "black" in potted:
            foul = self.assess_foul(sim, legal, potted, scratch)
            legal_black = (own is not None and sim.remaining(own) == 0
                           and not any(c == own for c in obj) and foul is None)
            self.over = True
            self.winner = striker if legal_black else 1 - striker
            self.reason = ("black potted cleanly" if legal_black
                           else f"black potted illegally ({foul or 'early'})")
            self.last_event = f"{self.names[self.winner]} wins: {self.reason}"
            return

        # Open table: first potted colour assigns. A foul shot still assigns if
        # a colour went down -- the ball is gone either way.
        if not self.colours and obj:
            first = obj[0]
            other = "yellow" if first == "red" else "red"
            self.colours = {striker: first, 1 - striker: other}
            own = first
            self.last_event = f"{self.names[striker]} is {first.upper()}S"

        foul = self.assess_foul(sim, legal, potted, scratch)
        self.free_shot = False     # a free shot is consumed by the shot itself
        self.ball_in_hand = False  # r13: and so is ball-in-hand

        if foul is not None:
            self.fouls += 1
            self.last_event = f"foul — {foul}"
            # r9 phase 3: fouling ends the visit outright -- the fouler's own
            # remaining visits are forfeit, they do NOT get to use a second one
            # to "recover". The table passes, and the incoming player receives
            # the penalty: a free shot, and two visits.
            #
            # visits_left ALWAYS describes the CURRENT striker, so it must be
            # set explicitly on every single handover, never left to carry over
            # from whoever was at the table before (which was the bug the old
            # `rules` selftest caught: the penalty was leaking to the wrong
            # player and the turn bounced back and forth).
            self.current = 1 - striker
            self.visits += 1
            self.free_shot = True
            self.visits_left = 2
            return

        keep_going = own is not None and any(c == own for c in obj)
        if keep_going:
            if not was_free:
                self.last_event = "potted — continue"
            return                  # striker stays at the table, visits_left intact

        # Legal shot, nothing of theirs potted. r9 phase 3: if they arrived on
        # two visits (because the opponent fouled), they get the second one
        # rather than handing the table straight back.
        if self.visits_left > 1:
            self.visits_left -= 1
            self.last_event = "missed — second visit"
            return
        self.current = 1 - striker
        self.visits += 1
        self.visits_left = 1        # normal handover: one visit, no penalty
        self.last_event = "dry visit — turn passes"


# ----------------------------------------------------------------------------
# Geometric utility AI (decision 2A) — judgement from scores, never scripted
# ----------------------------------------------------------------------------
class PoolAI:
    """Evaluates every legal (ball, pocket) pot via ghost-ball geometry,
    corridor clearance and an analytic success estimate. Candidates that
    beat the confidence threshold are ranked by utility

        u = p_pot x ((1 - greed) + greed x leave_quality) x (1 - caution x foul_risk)

    where leave_quality is the best analytic next-shot chance from the
    estimated cue-ball rest position (R5), and foul_risk (r9 phase 2) is the
    estimated chance the cue ball scratches -- so the AI now genuinely weighs
    a pot against the foul it might concede, instead of ignoring fouls
    entirely. greed=0, caution=0 reproduces the R4 pot-chance-only behaviour.

    Spin (r9 phase 2): once the best shot is chosen, a coarse 3x3 (follow x
    side) grid is scored over it and the spin that best serves position --
    while not raising foul risk -- is applied. Deliberately NOT a joint
    ball x pocket x spin search: that multiplies the candidate space for
    little gain, and this keeps --aigame batch times sane.

    Safety (r9 phase 2): when nothing beats the threshold, the AI no longer
    just rolls at the nearest ball. It scores real safety candidates by
    safety_quality -- how badly the leave hurts the OPPONENT -- while still
    requiring a legal first contact, so its own safeties don't foul.

    Personality comes only from the numbers. Nothing here is scripted."""

    def __init__(self, name, aim_jitter=0.010, threshold=0.15, greed=0.0,
                 caution=0.5, rng=None):
        self.name = name
        self.aim_jitter = aim_jitter     # radians (sigma)
        self.threshold = threshold       # minimum estimated pot chance
        self.greed = greed               # 0 = pure pot chance, 1 = position-led
        self.caution = caution           # r9: 0 = ignores fouls, 1 = foul-averse
        self.rng = rng or random.Random()

    # r9 phase 2: the coarse spin grid. Kept small on purpose -- these are
    # PARAMETERS the AI scores over, never a scripted "use draw here" rule.
    SPIN_GRID = (-0.7, 0.0, 0.7)

    def choose(self, sim, legal_colours):
        cue = sim.cue()
        if cue is None:
            return None
        return self._search(sim, legal_colours,
                            (cue.position.x, cue.position.y))

    def place_cue(self, sim, legal_colours):
        """r13 (ball in hand): choose where to put the cue ball in baulk.

        EMERGENT, not scripted: every candidate position across baulk is scored
        by re-running the AI's OWN shot search from there, and the position that
        yields the best shot wins. There is no table of 'put it here in this
        situation' -- the placement falls out of exactly the same utility the AI
        already uses to pick a shot, so a greedy AI naturally sets up a pot and a
        cautious one naturally sets up something safe.

        Returns the chosen position, or None if the cue isn't on the table."""
        cue = sim.cue()
        if cue is None:
            return None
        rc = CFG["CUE_R_M"]
        existing = [((b.position.x, b.position.y), s.radius)
                    for bid, (b, s) in sim.balls.items() if bid != Sim.CUE_ID]
        best_pos, best_u = None, -1.0
        for cand in baulk_candidates():
            if not can_place_cue(cand, existing, rc):
                continue
            shot = self._search(sim, legal_colours, cand, execute=False)
            u = shot["u"] if shot else 0.0
            if u > best_u:
                best_pos, best_u = cand, u
        if best_pos is None:
            return None
        cue.position = best_pos
        cue.velocity = (0.0, 0.0)
        return best_pos

    def _search(self, sim, legal_colours, cp, execute=True):
        """The shot search, parameterised by cue position `cp` so it can be run
        from a HYPOTHETICAL position (r13 ball-in-hand) as well as the real one.
        With execute=False it scores and returns the best shot WITHOUT applying
        aim jitter or committing anything -- so placement can compare candidates
        on equal terms."""
        rc, ro = CFG["CUE_R_M"], ball_r()
        targets = [(bid, tuple(b.position)) for bid, (b, _) in sim.balls.items()
                   if bid != Sim.CUE_ID and sim.colours.get(bid) in legal_colours]
        if not targets:
            return None
        all_pos = {bid: tuple(b.position) for bid, (b, _) in sim.balls.items()}
        # r9: the opponent's balls -- needed to score safeties from their side.
        opp_targets = [tuple(b.position) for bid, (b, _) in sim.balls.items()
                       if bid != Sim.CUE_ID
                       and sim.colours.get(bid) not in legal_colours
                       and sim.colours.get(bid) != "black"]
        best = None
        for (bid, t) in targets:
            others = [p for k, p in all_pos.items()
                      if k not in (bid, Sim.CUE_ID)]
            for (pc, cap_r) in capture_points():
                est = pot_estimate(cp, t, pc, cap_r, rc, ro, self.aim_jitter)
                if est is None:
                    continue
                if not corridor_clear(cp, est["ghost"],
                                      cue_corridor(rc, ro, self.aim_jitter,
                                                   est["t_cue"]), others):
                    continue      # cue path blocked
                if not corridor_clear(t, pc,
                                      object_corridor(ro, self.aim_jitter,
                                                      est["t_cue"]), others):
                    continue      # object path blocked
                p = est["p"]
                if p < self.threshold:
                    continue      # not confident enough to attempt
                d = est["t_cue"] + est["d_tp"]
                power = min(3.5, 1.0 + 1.1 * d)
                leave = 0.5       # neutral when position is not evaluated
                lv = estimate_leave(est, power)
                if self.greed > 0.0:
                    rem = [q for (qid, q) in targets if qid != bid]
                    if rem:
                        leave = leave_quality(lv["rest"], rem, others,
                                              rc, ro, self.aim_jitter)
                # r9: foul risk -- a pot that scratches is a pot that hands the
                # opponent a free shot and two visits, so it must cost something.
                risk = scratch_risk(lv["rest"], lv["speed"])
                u = (p * ((1.0 - self.greed) + self.greed * leave)
                     * (1.0 - self.caution * risk))
                if best is None or u > best["u"]:
                    best = {"type": "pot", "aim": est["aim"], "p": p, "u": u,
                            "leave": leave, "risk": risk, "target": t,
                            "ghost": est["ghost"], "pocket": pc, "d": d,
                            "est": est, "power": power,
                            "rem": [q for (qid, q) in targets if qid != bid],
                            "others": others}
        if best is not None:
            if not execute:
                return best        # r13: scoring only -- no jitter, nothing committed
            follow, side = self._choose_spin(best, rc, ro)
            return self._execute(best, best["power"], follow=follow, side=side)
        return self._choose_safety(sim, cp, targets, opp_targets, all_pos, rc, ro,
                                   execute=execute)

    def _choose_spin(self, shot, rc, ro):
        """r9 phase 2: score the coarse 3x3 (follow x side) grid over the
        already-chosen shot and take the spin that best serves position without
        raising the foul risk. Emergent: the spin falls out of the same
        leave/risk scores everything else uses -- there is no table of
        'situation -> spin'. Returns (follow, side)."""
        best = (0.0, 0.0, -1.0)     # follow, side, score
        for follow in self.SPIN_GRID:
            for side in self.SPIN_GRID:
                lv = estimate_leave(shot["est"], shot["power"],
                                    follow=follow, side=side)
                risk = scratch_risk(lv["rest"], lv["speed"])
                if shot["rem"]:
                    leave = leave_quality(lv["rest"], shot["rem"],
                                          shot["others"], rc, ro, self.aim_jitter)
                else:
                    leave = 0.5
                score = leave * (1.0 - self.caution * risk)
                if score > best[2]:
                    best = (follow, side, score)
        return best[0], best[1]

    def _choose_safety(self, sim, cp, targets, opp_targets, all_pos, rc, ro,
                       execute=True):
        """r9 phase 2: a real safety, scored rather than assumed. Rolls at each
        legal ball at a few powers, and takes whichever leaves the OPPONENT
        worst off (safety_quality) while keeping the cue ball out of a pocket.
        Crucially it also requires a CLEAR path to the target -- the old
        'nearest legal ball' fallback could send the cue straight through an
        illegal ball, which under r9's rules is now a wrong-ball-first foul."""
        best = None
        for (bid, t) in targets:
            others = [p for k, p in all_pos.items()
                      if k not in (bid, Sim.CUE_ID)]
            # A safety that fouls is not a safety. Legal first contact only.
            # r20: a safety fires a REAL, jittered cue like any other shot, so
            # it needs the same jitter-aware corridor -- the old -0.002 shave
            # let the cue clip an illegal ball on its way to the target, which
            # under r9's rules is a wrong-ball-first foul.
            if not corridor_clear(cp, t,
                                  cue_corridor(rc, ro, self.aim_jitter,
                                               math.dist(cp, t)), others):
                continue
            for power in (0.8, 1.2, 1.8):
                # Straight roll onto the ball: contact is full, so the leave
                # model's ghost is the ball itself.
                aim = (t[0] - cp[0], t[1] - cp[1])
                d = math.hypot(*aim)
                if d < 1e-9:
                    continue
                est = pot_estimate(cp, t, t, ro, rc, ro, self.aim_jitter)
                if est is None:
                    continue
                lv = estimate_leave(est, power)
                risk = scratch_risk(lv["rest"], lv["speed"])
                q = safety_quality(lv["rest"], opp_targets, others, rc, ro,
                                   self.aim_jitter)
                u = q * (1.0 - self.caution * risk)
                if best is None or u > best["u"]:
                    best = {"type": "safety", "aim": aim, "p": 0.0, "u": u,
                            "leave": 0.0, "risk": risk, "safety": q,
                            "target": t, "ghost": t, "pocket": None, "d": d,
                            "power": power}
        if best is not None:
            if not execute:
                return best        # r13: scoring only
            return self._execute(best, best["power"])
        # Nothing legal and clear at all -- roll at the nearest legal ball and
        # take what comes. Better than not striking, which is always a foul.
        (bid, t) = min(targets, key=lambda kv: math.dist(cp, kv[1]))
        aim = (t[0] - cp[0], t[1] - cp[1])
        fallback = {"type": "safety", "aim": aim, "p": 0.0,
                    "u": 0.0, "leave": 0.0, "risk": 0.0,
                    "target": t, "ghost": t, "pocket": None,
                    "d": math.hypot(*aim)}
        if not execute:
            return fallback
        return self._execute(fallback, 1.0)

    def _execute(self, shot, power, follow=0.0, side=0.0):
        ang = math.atan2(shot["aim"][1], shot["aim"][0])
        ang += self.rng.gauss(0.0, self.aim_jitter)
        shot["aim"] = (math.cos(ang), math.sin(ang))
        shot["power"] = max(CFG["POWER_MIN"],
                            power * (1.0 + self.rng.gauss(0.0, 0.02)))
        # r9 phase 2: spin travels with the shot so every caller (headless
        # --aigame, the GUI, the drills) applies exactly the shot the AI chose.
        shot["follow"] = follow
        shot["side"] = side
        return shot


def new_game(controllers=("ai", "ai"), names=("SHARK", "STEADY")):
    """Fresh racked game: returns (sim, game)."""
    sim = Sim(layout="empty")
    sim._respot_cue()
    sim.rack()
    return sim, Game(names=names, controllers=controllers)


STUDY_JITTER = 0.011   # r18: the SHARED skill level of both study personalities.
                       # Deliberately ONE constant, not two: see default_ais().


def default_ais(rng=None):
    """Two distinguishable players from STRATEGY parameters alone: SHARK
    attempts more, plays for position and risks more (threshold 0.10, greed
    0.55, caution 0.35); STEADY demands a better chance, takes the surest pot
    and avoids fouls (threshold 0.18, greed 0.25, caution 0.70).

    r18: both now aim with the SAME aim_jitter (STUDY_JITTER), and this is the
    whole point of the pass. aim_jitter is a SKILL parameter; threshold/greed/
    caution are STRATEGY. Before r18 SHARK had both the better strategy-of-
    aggression AND a truer cue (0.008 vs 0.014), so a win-rate gap could not be
    attributed to either -- and after the r16 calibration fix made pot chance
    far more sensitive to aim error, skill came to SWAMP strategy outright.
    Measured over 20 games/arm, holding strategy fixed and moving only jitter:

        as-shipped (SHARK .008 / STEADY .014)   SHARK 90%
        matched    (both .011)                  SHARK 65%
        SWAPPED    (SHARK .014 / STEADY .008)   SHARK 45%

    i.e. handing SHARK the WORSE cue while leaving its entire aggressive
    playbook intact collapsed it from 90% to 45%. The study was measuring who
    aimed straighter, not whose strategy was better. Matching the jitter makes
    the AI-vs-AI study answer the question it exists to answer; skill is now an
    independent axis, swept deliberately (pass a different aim_jitter) rather
    than smuggled into the matchup."""
    rng = rng or random.Random()
    return [PoolAI("SHARK", aim_jitter=STUDY_JITTER, threshold=0.10, greed=0.55,
                   caution=0.35, rng=rng),
            PoolAI("STEADY", aim_jitter=STUDY_JITTER, threshold=0.18, greed=0.25,
                   caution=0.70, rng=rng)]


STUDY_SCHEMA = 2   # bump when the JSONL record shape changes, so old study
                   # files can never be silently misread by a newer analysis.
                   # 2 (r19): added cut_deg / t_cue / d_tp -- the pot geometry.


def make_shot_record(n, striker, name, colour, plan, potted, first_contact,
                     cushion_after, foul, event, ball_in_hand, free_shot,
                     cue_placed):
    """r15 (study output): one shot -> one plain, JSON-safe dict.

    The payload that matters for analysis is `p_pred` (what the AI THOUGHT the
    pot chance was) alongside `potted` (what actually happened). Those two
    together are the only way to ask whether pot_estimate is CALIBRATED -- i.e.
    whether shots the AI rates at 80% actually go in 80% of the time. That
    question is unanswerable from a game-summary log, which is exactly why the
    per-shot log earns its keep.

    r19: also logs the POT GEOMETRY -- cut_deg (how thin the cut is), t_cue
    (cue-to-object distance) and d_tp (object-to-pocket distance). r16 fixed a
    calibration bug that was ultimately ABOUT geometry, and the follow-up
    investigation then stalled because none of it was in the log: 'are thin cuts
    over-rated, or long pots?' was unanswerable, and total distance had to be
    reverse-engineered from the power formula, which is a hack. These three
    fields are exactly the inputs pot_estimate() already computes and throws
    away, so logging them is free and makes the residual directly diagnosable.

    Pure: no sim, no pygame, no file I/O -- just values in, dict out."""
    est = plan.get("est") or {}
    fullness = est.get("fullness")
    return {
        "n": n,
        "striker": striker,
        "striker_name": name,
        "colour": colour,
        "type": plan.get("type"),
        "p_pred": round(float(plan.get("p", 0.0)), 4),
        "u": round(float(plan.get("u", 0.0)), 4),
        "risk": round(float(plan.get("risk", 0.0)), 4),
        "power": round(float(plan.get("power", 0.0)), 4),
        "follow": round(float(plan.get("follow", 0.0)), 3),
        "side": round(float(plan.get("side", 0.0)), 3),
        # r19 pot geometry -- None on a safety, which carries no ghost-ball est
        "cut_deg": (round(math.degrees(math.acos(max(-1.0, min(1.0, fullness)))), 2)
                    if fullness is not None else None),
        "t_cue": (round(float(est["t_cue"]), 4) if "t_cue" in est else None),
        "d_tp": (round(float(est["d_tp"]), 4) if "d_tp" in est else None),
        "ball_in_hand": bool(ball_in_hand),
        "free_shot": bool(free_shot),
        "cue_placed": ([round(cue_placed[0], 4), round(cue_placed[1], 4)]
                       if cue_placed else None),
        "potted": list(potted),
        "first_contact": first_contact,
        "cushion_after": bool(cushion_after),
        "foul": foul,
        "event": event,
    }


def wilson_interval(wins, n, z=1.96):
    """r15 (study output): 95% Wilson score interval for a win rate.

    This is the whole point of larger-N. "SHARK 5 - 7 STEADY" over 12 games
    means NOTHING -- it sits well inside coin-flip noise, and reporting it as a
    result would be a lie. Wilson (rather than the naive normal interval)
    because it stays sane at small n and near 0 or 1, which is exactly where a
    study starts. Returns (lo, hi). Pure."""
    if n <= 0:
        return (0.0, 1.0)
    p = wins / n
    d = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def pot_calibration(shot_records, bins=5):
    """r15 (study output): is pot_estimate honest?

    Bins every attempted POT by the chance the AI predicted, and reports what
    fraction actually went down. A well-calibrated model has predicted ~= actual
    in every bin. If the AI's 80% shots only land 50% of the time, its whole
    utility function is built on a lie -- and no amount of tuning greed/caution
    would fix that, because the inputs are wrong.

    r21: FREE SHOTS ARE EXCLUDED, and this correction matters more than it
    sounds. On a free shot (r9, awarded after the opponent fouls) ANY ball may
    legally be struck first, so the AI will quite properly cannon into an
    opponent's ball if that is the best-utility line -- it is exploiting the
    rule, not misplaying. Measured, 39.2% of free-shot pot attempts strike
    another colour first, against 5.4% on a normal shot. Leaving them in scores
    pot_estimate against shots where the AI was not really trying to pot its own
    colour at all, which silently drags 'actual' down and makes the model look
    worse-calibrated than it is. A calibration table is only meaningful over a
    population of COMPARABLE attempts.

    (This was found the hard way: a 'wrong ball first' rate that looked like a
    collision bug, and survived a corridor fix, turned out to be half legal free
    shots. The lesson worth keeping: before treating a failure mode as a defect,
    check whether it is even against the rules.)

    Returns [(lo, hi, n, predicted_mean, actual_rate), ...]. Pure."""
    out = []
    pots = [s for s in shot_records
            if s.get("type") == "pot" and not s.get("free_shot")]
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [s for s in pots
               if (lo <= s.get("p_pred", 0.0) < hi
                   or (b == bins - 1 and s.get("p_pred", 0.0) == 1.0))]
        if not sel:
            continue
        pred = sum(s["p_pred"] for s in sel) / len(sel)
        # "actual" = the striker's OWN colour went down. Potting the opponent's
        # ball is not a successful pot, it's a foul -- counting it would flatter
        # the model.
        made = sum(1 for s in sel
                   if s.get("colour") and s["colour"] in s.get("potted", []))
        out.append((lo, hi, len(sel), pred, made / len(sel)))
    return out


def play_ai_game(seed=0, max_shots=300, verbose=False, log_shots=False):
    """Headless AI-vs-AI game. Returns a result record.

    r15: with log_shots=True the record also carries a per-shot event log and
    everything needed to REPLAY the game exactly (the seed, and the AI
    parameters). Without those, an interesting outlier is a curiosity you can
    never reproduce."""
    rng = random.Random(seed)
    sim, game = new_game()
    ais = default_ais(rng)
    # Player 0 breaks
    sim.break_shot(power=6.0 * rng.gauss(1.0, 0.02),
                   aim_off=rng.gauss(0.0, 0.0015))
    sim.run_to_rest()
    game.on_rest(sim)
    safeties = 0
    shot_log = []
    while not game.over and game.shots < max_shots:
        ai = ais[game.current]
        striker = game.current
        # r13: ball in hand (break / after a foul) -- the AI places the cue
        # ball first, scoring candidate positions across baulk with its own
        # shot search. Emergent: no scripted 'put it here'.
        bih = game.ball_in_hand
        free = game.free_shot
        cue_placed = None
        if game.ball_in_hand:
            cue_placed = ai.place_cue(sim, game.legal_colours(sim))
        shot = ai.choose(sim, game.legal_colours(sim))
        if shot is None:
            break
        if shot["type"] == "safety":
            safeties += 1
        if verbose:
            print(f"    shot {game.shots:3d}: {ai.name:6s} {shot['type']:6s} "
                  f"p={shot['p']:.2f} pow={shot['power']:.2f}")
        colour = game.colours.get(striker)
        n_shot = game.shots + 1
        sim.strike(shot["aim"], shot["power"],
                   side=shot.get("side", 0.0), follow=shot.get("follow", 0.0))
        sim.run_to_rest()
        # Snapshot what the shot actually DID, before on_rest() mutates state.
        potted = sim.potted_colours()
        first_contact = sim.first_contact
        cushion_after = sim.cushion_after_contact
        fouls_before = game.fouls
        game.on_rest(sim)
        if log_shots:
            foul = (game.last_event[len("foul — "):]
                    if game.fouls > fouls_before
                    and game.last_event.startswith("foul") else None)
            shot_log.append(make_shot_record(
                n_shot, striker, ai.name, colour, shot, potted, first_contact,
                cushion_after, foul, game.last_event, bih, free, cue_placed))
    rec = {"over": game.over, "winner": game.winner,
           "winner_name": game.names[game.winner] if game.winner is not None else "-",
           "reason": game.reason, "shots": game.shots, "visits": game.visits,
           "fouls": game.fouls, "safeties": safeties}
    if log_shots:
        rec["schema"] = STUDY_SCHEMA
        rec["seed"] = seed
        rec["players"] = [{"name": a.name, "aim_jitter": a.aim_jitter,
                           "threshold": a.threshold, "greed": a.greed,
                           "caution": a.caution} for a in ais]
        rec["shot_log"] = shot_log
    return rec


def aigame_batch(n, jsonl=None, seed=1000):
    """r15: run n headless AI-vs-AI games, optionally streaming a per-shot JSONL
    study log, and report the result WITH a confidence interval.

    JSONL (one game per line) rather than one-file-per-game or a single array:
    it streams, it appends, it survives a run that dies mid-study, and jq/pandas
    read it directly. Written incrementally as each game finishes, so a study
    that is killed at game 400 of 500 still leaves 400 usable games.

    r17 (perf item 4): games are independent, so they run across a
    multiprocessing.Pool rather than one at a time -- stdlib only, no physics
    touched. pool.imap() (not .map()) is deliberate: it yields each game's
    result in SEED ORDER as soon as it's ready, so the per-game print/flush
    below still happens one game at a time in the same order as before, and
    the mid-study crash resilience (every completed game already on disk)
    is preserved rather than traded away for the parallel speedup."""
    print(f"HUSTLER AI vs AI — {n} headless game(s), seed base {seed}")
    wins = {"SHARK": 0, "STEADY": 0}
    incomplete = 0
    all_shots = []
    fh = open(jsonl, "w", encoding="utf-8") if jsonl else None
    worker = functools.partial(play_ai_game, log_shots=bool(jsonl))
    try:
        with multiprocessing.Pool() as pool:
            results = pool.imap(worker, (seed + i for i in range(n)))
            for i, rec in enumerate(results):
                if rec["over"]:
                    wins[rec["winner_name"]] += 1
                else:
                    incomplete += 1
                if fh:
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()          # a killed study keeps every completed game
                    all_shots.extend(rec.get("shot_log", []))
                print(f"  game {i+1:3d}: {'winner ' + rec['winner_name'] if rec['over'] else 'NO RESULT':18s}"
                      f"  ({rec['reason'] or 'shot cap reached'})  shots {rec['shots']:3d}"
                      f"  visits {rec['visits']:3d}  fouls {rec['fouls']}  safeties {rec['safeties']}")
    finally:
        if fh:
            fh.close()

    decided = wins["SHARK"] + wins["STEADY"]
    print(f"  totals: SHARK {wins['SHARK']} — {wins['STEADY']} STEADY"
          f"{'' if not incomplete else f'  ({incomplete} incomplete)'}")
    if decided:
        lo, hi = wilson_interval(wins["SHARK"], decided)
        rate = wins["SHARK"] / decided
        # Say plainly whether this is a RESULT or just noise. A win count with no
        # interval invites exactly the false conclusion larger-N exists to avoid.
        verdict = ("inconclusive — interval spans 50%" if lo <= 0.5 <= hi
                   else "significant at 95%")
        print(f"  SHARK win rate: {rate*100:.1f}%  "
              f"(95% CI {lo*100:.1f}–{hi*100:.1f}%)  → {verdict}")
    if all_shots:
        print(f"  shot log: {len(all_shots)} shots → {jsonl}")
        cal = pot_calibration(all_shots)
        if cal:
            print("  pot_estimate calibration (predicted vs actual):")
            for lo_b, hi_b, cnt, pred, act in cal:
                print(f"    p {lo_b:.1f}-{hi_b:.1f}: n={cnt:5d}  "
                      f"predicted {pred*100:5.1f}%  actual {act*100:5.1f}%")
    return incomplete == 0


# ----------------------------------------------------------------------------
# GUI layer
# ----------------------------------------------------------------------------
COL = {
    "baize": (66, 138, 64), "cushion": (44, 110, 48), "nose": (32, 84, 38),
    "wood": (124, 82, 49), "wood_dark": (86, 55, 32),
    "rim": (176, 178, 184), "bolt": (172, 176, 182), "bolt_ring": (96, 100, 106),
    "line": (215, 215, 215),
    "cue": (240, 236, 220), "red": (190, 30, 30), "yellow": (215, 180, 40),
    "black": (25, 25, 25), "ghost": (245, 245, 245), "objline": (250, 210, 60),
    "tanline": (80, 220, 235), "pocket": (8, 8, 8), "hud": (235, 235, 235),
}

# ----------------------------------------------------------------------------
# Fullscreen + fit-to-region (Graphics Pass 3, Increment 3a)
# ----------------------------------------------------------------------------
# Pure layout maths, no pygame: given the actual window size and a reserved
# right-hand panel width, find the largest uniform scale that fits the
# table's reference (1x) frame into the space left of the panel WITHOUT
# distorting it -- the SAME scale multiplies both axes, so whatever exact
# aspect the reference frame has (built from the exact 2:1 table + fixed
# margins) survives untouched. Dependency-free on purpose so it gets a plain
# selftest assertion, dependency-free.
def fit_to_region(win_w, win_h, base_w, base_h, panel_w,
                   min_scale=None, max_scale=None):
    """Largest uniform scale fitting a base_w x base_h frame into
    (win_w - panel_w) x win_h, clamped to [min_scale, max_scale].
    Returns (scale, fitted_w, fitted_h). A floor clamp may overflow the
    region at absurdly small windows rather than shrink to nothing."""
    if min_scale is None:
        min_scale = CFG["FIT_MIN_SCALE"]
    if max_scale is None:
        max_scale = CFG["FIT_MAX_SCALE"]
    avail_w = max(1, win_w - panel_w)
    avail_h = max(1, win_h)
    scale = min(avail_w / base_w, avail_h / base_h)
    scale = max(min_scale, min(max_scale, scale))
    return scale, max(1, round(base_w * scale)), max(1, round(base_h * scale))


# ----------------------------------------------------------------------------
# Hand-rolled UI widget primitives (Graphics Pass 3, Increment 3b). Pure,
# dependency-free maths only -- the drawable widget classes that use these
# live inside run_gui (they need pygame, which is lazily imported there per
# the existing convention). Kept here, pygame-free, so they get plain
# selftest assertions with zero new dependencies.
# ----------------------------------------------------------------------------
def slider_frac(value, lo, hi):
    """Value -> fraction [0, 1] along a slider track, clamped."""
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def slider_value(frac, lo, hi):
    """Fraction [0, 1] -> value in [lo, hi]. Inverse of slider_frac (up to
    clamping at the ends -- a value already outside [lo, hi] round-trips to
    the nearest end, by design)."""
    frac = max(0.0, min(1.0, frac))
    return lo + frac * (hi - lo)


def spin_pad_map(dx, dy, radius):
    """2D spin pad: a contact offset (dx, dy) in pixels from the pad centre
    -> (follow, side) in [-1, 1], clamped to the UNIT CIRCLE (not the
    square) so a diagonal drag can't exceed the physical spin budget. Screen
    y grows downward, so follow is the negated, radius-normalised dy."""
    if radius <= 0:
        return 0.0, 0.0
    fx, fy = dx / radius, -dy / radius
    mag = math.hypot(fx, fy)
    if mag > 1.0:
        fx, fy = fx / mag, fy / mag
    return fy, fx  # (follow, side)


def pot_chance_colour(p):
    """r14 (aim overlay): map a 0..1 pot chance to a colour -- RED (dead) through
    AMBER (marginal) to GREEN (on). The single most useful thing the overlay can
    tell you, and it was previously computed by pot_assessment() and then thrown
    away into a text string. Colour is read instantly; text has to be parsed.

    Interpolates red->amber over the bottom half and amber->green over the top,
    so the amber band sits at p=0.5 where a shot genuinely is a coin-flip.
    Pure -- no pygame, so the ramp is testable on its own."""
    p = max(0.0, min(1.0, p))
    # NB amber's red channel must be <= red's, or the red channel RISES as the
    # shot gets better before falling -- which is exactly the bug the selftest
    # caught on the first cut of this (red 232 -> amber 240). The ramp has to be
    # monotonic in both channels or it misreports at a glance, which defeats the
    # entire point of using colour instead of text.
    red, amber, green = (232, 62, 58), (228, 176, 48), (86, 214, 106)
    if p < 0.5:
        t = p / 0.5
        a, b = red, amber
    else:
        t = (p - 0.5) / 0.5
        a, b = amber, green
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def aim_taper_alpha(i, n, lo=40, hi=210):
    """r14 (aim overlay): alpha for segment i of n along the aim line, fading
    from `hi` at the cue ball to `lo` at the far end.

    A flat, uniform hairline is exactly what reads as a 1980s vector overlay --
    real aim guides fade with distance, because certainty does. Pure."""
    if n <= 1:
        return hi
    t = i / (n - 1)
    return int(hi + (lo - hi) * t)


def baulk_rect():
    """r13 (ball in hand): the baulk area -- the rectangle bounded by the baulk
    line and the three cushions at the head of the table. This is the legal
    region for cue-ball placement on the break and after a foul.

    NOT the 'D'. The D is a snooker/English-billiards marking; on modern UK pool
    tables the rules moved on, and blackball simply gives ball-in-hand ANYWHERE
    IN BAULK. Since r9 implements proper WEPF rules, restricting to a D would
    knowingly diverge from the ruleset the rest of the engine follows.

    Returns (x0, y0, x1, y1) in metres. Derived from BAULK_FRAC, the same
    constant that already positions the baulk line and _respot_cue()."""
    x0, y0, x1, y1 = play_rect()
    baulk_x = x0 + (x1 - x0) * CFG["BAULK_FRAC"]
    return (x0, y0, baulk_x, y1)


def in_baulk(pos, r=0.0):
    """r13: is a ball of radius r wholly inside the baulk area? A ball straddling
    the baulk line is NOT in baulk -- it has to be fully behind it."""
    bx0, by0, bx1, by1 = baulk_rect()
    return (bx0 + r <= pos[0] <= bx1 - r) and (by0 + r <= pos[1] <= by1 - r)


def can_place_cue(pos, existing, r_cue):
    """r13: may the cue ball be placed at `pos`? It must be legal table-wise
    (can_place_ball: inside the cushions, clear of pockets, not overlapping
    anything) AND wholly within baulk. `existing` is [(pos, radius), ...].

    Pure -- so the ball-in-hand rule is testable with no table and no window."""
    return in_baulk(pos, r_cue) and can_place_ball(pos, existing, r_cue,
                                                   [r for (_, r) in existing])


def baulk_candidates(nx=6, ny=4):
    """r13: a coarse grid of candidate cue positions across baulk, for the AI's
    ball-in-hand search. Coarse on purpose -- the AI re-runs its whole pot search
    from each candidate, and profiling already showed AI games are slow, so this
    stays small. Inset by a ball's width so candidates aren't born illegal."""
    bx0, by0, bx1, by1 = baulk_rect()
    r = CFG["CUE_R_M"] * 1.2
    xs = [bx0 + r + (bx1 - bx0 - 2 * r) * (i + 0.5) / nx for i in range(nx)]
    ys = [by0 + r + (by1 - by0 - 2 * r) * (j + 0.5) / ny for j in range(ny)]
    return [(x, y) for x in xs for y in ys]


def chamber_slots(n, width, d_max, gap):
    """r12 (potted-ball chamber): lay out n potted balls left-to-right inside a
    `width`-px strip, at most d_max across, with `gap` px between them.

    Returns (diameter, [x_centre, ...]). If n balls at d_max won't fit, the
    DIAMETER SHRINKS until they do -- a blackball rack is 15 object balls, and a
    fixed size that fits 15 would be uselessly tiny for the common case of 2 or
    3. The order is the order they were potted, which is the whole point: a real
    table's chamber shows you exactly what went down, and in what order.

    Pure geometry, no pygame -- so the fit rule is testable without a window."""
    if n <= 0 or width <= 0:
        return 0, []
    d = min(d_max, (width - gap * (n - 1)) / n)
    d = max(1.0, d)
    total = n * d + gap * (n - 1)
    x = (width - total) / 2.0 + d / 2.0      # centre the row in the strip
    return d, [x + i * (d + gap) for i in range(n)]


def wrap_fields(fields, max_width, measure=len, sep="  "):
    """r11 (persistent panel status strip): greedily pack short field strings
    into as few lines as possible, none wider than max_width.

    `measure` maps a string to its width -- len() by default, so the packing
    logic is testable with no pygame at all, while the renderer passes
    font.size(s)[0] to pack by ACTUAL pixel width instead of character count
    (a proportional font makes those two very different things).

    A single field wider than max_width still gets its own line rather than
    being dropped or split mid-token -- a clipped-but-present readout beats a
    silently missing one. The panel is only 260px wide and the vertical budget
    is ~70px, so this packing is what makes a 5-field physics readout fit at
    all."""
    lines = []
    cur = ""
    for f in fields:
        if not f:
            continue
        cand = f if not cur else cur + sep + f
        if cur and measure(cand) > max_width:
            lines.append(cur)
            cur = f
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def nudge_spin(follow, side, d_follow, d_side):
    """r10 (HUD fine adjustment): apply a small delta to the spin contact point
    and re-clamp to the UNIT CIRCLE, exactly as spin_pad_map does for a drag.

    Nudging must obey the same physical spin budget as dragging -- otherwise the
    buttons could walk the contact point outside the circle one 0.01 step at a
    time and reach a spin the pad itself cannot express. Pure, no pygame."""
    f = follow + d_follow
    s = side + d_side
    mag = math.hypot(f, s)
    if mag > 1.0:
        f, s = f / mag, s / mag
    return f, s


# r10 custom mode: ball kinds the user can place. "cue" is special -- there can
# only ever be one, so placing a second REPLACES the first rather than adding.
PLACE_KINDS = ["cue", "red", "yellow", "black"]


def can_place_ball(pos, existing, r_new, r_others):
    """r10 custom mode: is `pos` a legal spot to drop a ball?

    Legal means: fully inside the cushion nose (not embedded in a rail), not
    overlapping any existing ball, and not sitting where the pocket would
    instantly swallow it. `existing` is a list of (pos, radius). Pure geometry,
    no pygame, no pymunk -- so the editor's placement rule is testable without
    a table.

    r22: the pocket rule was `dist < cap_r + r_new`, which reserved a whole
    extra BALL RADIUS (25mm) around every pocket for no physical reason and
    made it impossible to set a ball on the jaws ready to pot -- exactly the
    trick-shot setup custom mode exists for. Capture is a test on the ball's
    CENTRE (see _capture_pockets: centre within cap_r), so the real constraint
    is `dist >= cap_r`, plus a hair so it can't drop the instant physics
    resumes. 1mm of clearance, not 25mm."""
    x0, y0, x1, y1 = play_rect()
    if not (x0 + r_new <= pos[0] <= x1 - r_new
            and y0 + r_new <= pos[1] <= y1 - r_new):
        return False
    for (pc, cap_r) in capture_points():
        if math.dist(pos, pc) < cap_r + 0.001:
            return False
    for (p, r) in existing:
        if math.dist(pos, p) < r_new + r + 0.0005:   # 0.5mm breathing room
            return False
    return True


def serialise_layout(balls):
    """r10 custom mode: (kind, (x, y)) list -> a plain JSON-safe dict.

    Positions are stored in METRES, the same real WEPF units the physics layer
    uses -- NOT pixels. A layout saved on one window size must load identically
    on another, and pixels would silently break that."""
    return {"version": 1,
            "balls": [{"kind": k, "x": float(p[0]), "y": float(p[1])}
                      for (k, p) in balls]}


def deserialise_layout(data):
    """r10 custom mode: inverse of serialise_layout. Skips any entry that is
    malformed or names an unknown ball kind rather than raising -- a hand-edited
    or truncated layout file should cost you that ball, not crash the game."""
    out = []
    for b in (data or {}).get("balls", []):
        try:
            kind = b["kind"]
            if kind not in PLACE_KINDS:
                continue
            out.append((kind, (float(b["x"]), float(b["y"]))))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def shoot_enabled(cue_present, all_at_rest, my_turn):
    """Pure mirror of the SPACE-to-strike guard (cue present, table at rest,
    player's turn) -- the Shoot button calls this directly so it can never
    drift from the key it mirrors."""
    return bool(cue_present and all_at_rest and my_turn)


def rotate_vector(dx, dy, degrees):
    """Rotate (dx, dy) by degrees (screen convention, y-down) about the
    origin. Used to turn the cue-angle dial's absolute angle into an aim
    direction vector."""
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    return dx * c - dy * s, dx * s + dy * c


def dial_angle(dx, dy):
    """Rotating cue-angle dial: a contact offset (dx, dy) from the dial's
    centre -> absolute aim angle in degrees [0, 360), screen convention
    (atan2(dy, dx)). Inverse of rotate_vector(1, 0, angle) -- round-trips
    with it (mod 360)."""
    if dx == 0.0 and dy == 0.0:
        return 0.0
    return math.degrees(math.atan2(dy, dx)) % 360.0


def hud_icon_x(default_x, text_right_edge, gap, icon_r, frame_right_edge):
    """Aim-icon centre-x (Increment 3b HUD-crowding fix). The icon normally
    sits at default_x (right-anchored, unchanged look) -- its own floor,
    independent of the font's floor. It is pushed further right (never
    left, never smaller) to clear the HUD text's actual rendered width once
    the text's fixed-size floor makes it encroach, then clamped so it still
    fits inside the frame at absurd window sizes (floor-clamps gracefully,
    same doctrine as fit_to_region)."""
    x = max(default_x, text_right_edge + gap + icon_r)
    return min(x, frame_right_edge - icon_r)


def trail_dot_style(age_idx, trail_len):
    """Increment 4a (spectator motion trails): age_idx counts from the
    NEWEST sample (0) back to the OLDEST (trail_len - 1) -- returns
    (radius_frac, fade_t), where radius_frac shrinks a trail dot toward a
    floor as it ages and fade_t is how far to blend its colour toward the
    cloth (0 = ball colour, unchanged; 1 = fully cloth-coloured, i.e.
    invisible). age_idx=0 -> (1.0, 0.0); the oldest sample -> (MIN_FRAC,
    1.0). A single-sample trail (trail_len <= 1) doesn't fade or shrink."""
    if trail_len <= 1:
        return 1.0, 0.0
    MIN_FRAC = 0.25
    t = age_idx / (trail_len - 1)      # 0 at newest, 1 at oldest
    return 1.0 - t * (1.0 - MIN_FRAC), t


def swallow_progress(age_frames, duration_frames):
    """Increment 4b (pot swallow animation): eased progress fraction t in
    [0, 1] for a ball 'age_frames' frames into its swallow, over
    'duration_frames' total. t=0 at the moment of capture (still at the
    mouth); t=1 once it has fully travelled to the cup centre and vanished.
    Ease-in (t**2) -- starts slow near the mouth, accelerates into the
    throat -- rather than a linear drop. Clamped both ends so a caller can
    pass an age past the duration without special-casing it. duration<=0 is
    treated as an instant drop (t=1 immediately) rather than dividing by
    zero."""
    if duration_frames <= 0:
        return 1.0
    lin = max(0.0, min(1.0, age_frames / duration_frames))
    return lin * lin


def finale_fade(age_frames, duration_frames):
    """Increment 4c (slow-mo black finale): the fade-to-black envelope
    covering the whole finale window -- 0 at the start, 0 at the end,
    peaking at 1 at the midpoint, smoothly (half-sine, not a linear
    triangle) so the ramp in and out both ease rather than snapping.
    age_frames outside [0, duration_frames] clamps to 0 -- no fade before
    the trigger fires or after the window ends. duration_frames<=0 means no
    fade window at all (always 0), rather than dividing by zero."""
    if duration_frames <= 0:
        return 0.0
    t = age_frames / duration_frames
    if t < 0.0 or t > 1.0:
        return 0.0
    return math.sin(math.pi * t)


def vignette_alpha(d, start=0.55, max_alpha=90):
    """Increment 4d (vignette): darken alpha (0-255) at a point whose
    distance from the frame centre, as a fraction of the half-diagonal, is
    'd' (0 = centre, 1 = corner). Flat 0 out to 'start', then rises
    smoothly (half-cosine ease-in, not linear) to max_alpha exactly at
    d=1 -- the darkening only ever appears toward the edges, never in the
    middle of the table, and never exceeds max_alpha. d<=start is always 0;
    d>=1 clamps to max_alpha rather than continuing to grow past the
    corner."""
    if d <= start:
        return 0
    t = min(1.0, (d - start) / (1.0 - start)) if start < 1.0 else 1.0
    eased = 1.0 - math.cos(t * math.pi / 2.0)
    return int(max_alpha * eased)


GRADE_DEFS = [
    # (label, colour, blend, strength) -- "normal" blends the colour in via
    # true alpha compositing (a translucent Surface blit, same technique as
    # 4c's darken layer -- NOT a raw pygame.draw call, which writes flat
    # RGBA with no compositing); "mult" multiplies the frame by the colour
    # with no alpha needed, the multiply factor itself sets the strength.
    # Contrast has no per-pixel curve available without a new numpy
    # dependency (pygame.surfarray needs it) -- this is a flat multiply-
    # darken, a deliberate approximation, not a true tone curve.
    ("Warm", (255, 178, 110), "normal", 22),
    ("Cool", (110, 160, 225), "normal", 22),
    ("Contrast", (222, 222, 230), "mult", 255),
]


def grade_params(idx):
    """Colour-grade (Table tab TabStrip): returns the (label, colour,
    blend, strength) tuple for grade index idx. Pure lookup, no pygame, so
    the TabStrip's labels/order stay verifiably in sync with what actually
    gets blended. idx outside [0, len(GRADE_DEFS)) clamps to the nearest
    valid entry rather than raising -- it's driven by a UI control that
    can't produce anything else, but the render loop shouldn't crash if it
    ever did."""
    idx = max(0, min(len(GRADE_DEFS) - 1, idx))
    return GRADE_DEFS[idx]


def synth_tone_samples(freq_hz, duration_s, sample_rate, decay, noise_mix=0.0, seed=0):
    """Sound effects: pure, dependency-free (stdlib `math`/`random` only --
    no numpy) waveform generator. A sine tone at freq_hz, optionally mixed
    with seeded pseudo-random noise (noise_mix in [0,1], 0=pure tone,
    1=pure noise -- deterministic given the same seed, so this is exactly
    reproducible/testable), under an exponential decay envelope shaping it
    into a physical-impact-style transient rather than a sustained note.
    Returns a list of int16 sample values (-32768..32767), length
    round(duration_s * sample_rate). This is the one shared primitive
    behind all three sound 'voices' (cue strike / ball hit / pot) -- they
    differ only in the parameters passed in, listed in SOUND_VOICES below,
    same pattern as ball_shades/GRADE_DEFS elsewhere in this file."""
    n = max(1, int(round(duration_s * sample_rate)))
    rng = random.Random(seed)
    out = []
    for i in range(n):
        t = i / sample_rate
        tone = math.sin(2.0 * math.pi * freq_hz * t)
        noise = rng.uniform(-1.0, 1.0)
        s = tone * (1.0 - noise_mix) + noise * noise_mix
        env = math.exp(-decay * t)
        v = int(max(-1.0, min(1.0, s * env)) * 32767)
        out.append(v)
    return out


SOUND_VOICES = {
    # (freq_hz, duration_s, decay, noise_mix) -- first-pass placeholder
    # values, tunable by EAR once actually heard (unlike the visual passes,
    # nothing here can be eyeballed/verified by me -- these numbers are a
    # reasonable starting guess, not a considered final mix).
    # NOTE: "ball_hit" is no longer synthesised from this table -- it has its
    # own three-layer impact model below (synth_impact_samples). Left here
    # because cue_strike/pot still use synth_tone_samples, and as a record of
    # the old single-sine voice that sounded like clinking glass.
    "cue_strike": (1400.0, 0.05, 40.0, 0.35),
    "ball_hit":   (900.0, 0.06, 35.0, 0.25),
    "pot":        (220.0, 0.18, 9.0, 0.10),
}


HIT_IMPULSE_REF = 0.35  # kg*m/s -- the impulse mapped to full (1.0) ball-hit
                        # playback volume. Placeholder, tunable by ear.
                        # Defined here (above the r8 impact model) because it
                        # now drives BOTH loudness and timbre.


# ---- Ball-hit impact model (r8) -------------------------------------------
# Replaces the old single 900Hz sine voice, which read as clinking glass for
# two reasons, both visible in its parameters: the carrier sat less than half
# way to a phenolic ball's actual resonance, and with decay=35 over a 0.06s
# buffer the envelope was still at ~12% amplitude when the buffer ENDED --
# hard-truncated mid-ring. A tonal carrier plus an audible cut-off is a
# bottle. The model here is instead the physical one for a rigid, high-density
# phenolic impact: a sharp broadband transient (the chaotic instant of
# contact), a short high-frequency resonance (the ball's internal vibration),
# and a brief low-frequency thud (perceived mass), all under an AD envelope --
# attack then exponential decay, NO sustain phase. Sustain is exactly what
# made the old voice ring like glass, so there deliberately isn't one.

IMPACT_ATTACK_S     = 0.0005   # s -- attack ramp. Halved from r8 (was 1.2ms):
                               # still non-zero, because a buffer that starts at
                               # full amplitude on sample 0 is a step
                               # discontinuity and clicks -- but a real contact
                               # lasts only ~200us, so a 1.2ms attack was
                               # actually SLOWER than the physical event.

# r8.2 -- "sounds like glass, not solid polymer". The r8 model was still wrong
# in three ways, all of which push a sound TOWARDS glass:
#   1. TOO TONAL AND TOO LONG. A single sine at 1900-2600Hz under a decay of
#      55-95 rings for 40-60ms. A struck wine glass rings; a struck phenolic
#      ball does not. Real ball contact lasts ~200 MICROseconds and the body
#      rings down in a few ms.
#   2. TOO HIGH. Glass is characterised by a high, clean, sustained tone. The
#      2000-2500Hz band (my own earlier suggestion) sits right in it.
#   3. HISSY NOISE. The noise layer ran at FULL bandwidth to 22kHz. Broadband
#      hiss reads as ceramic/glass; a real polymer knock has its energy rolling
#      off hard above a few kHz.
# The fix inverts the whole model: NOISE is now the body of the sound and the
# tonal part merely colours it, the modal band drops well below the glass
# region, decay rates go up ~5x so it dies in millisconds, and everything is
# lowpassed so nothing hisses.

IMPACT_PARTIAL_RATIOS = (1.0, 1.58, 2.24)   # INHARMONIC. A struck sphere excites
                                            # several modes at once, and it's the
                                            # inharmonicity that makes it read as
                                            # a "knock" rather than a "note" --
                                            # a single sine is always a pitch.
IMPACT_PARTIAL_HZ_SOFT = 620.0  # fundamental modal freq at a gentle kiss
IMPACT_PARTIAL_HZ_HARD = 980.0  # ...and at a full-power hit (brighter, still
                                # far below the old glassy 1900-2600Hz band)
IMPACT_DECAY_SOFT   = 190.0    # exp decay, soft: body gone in ~15ms
IMPACT_DECAY_HARD   = 420.0    # exp decay, hard: body gone in ~7ms (a harder hit
                               # is SHORTER and sharper, not longer)
IMPACT_NOISE_SOFT   = 0.74     # r8.2: noise is now the BODY of the sound, not a
IMPACT_NOISE_HARD   = 0.90     # garnish on the front of a tone. This inversion
                               # is the single biggest change here.
IMPACT_NOISE_DECAY  = 1500.0   # the contact crack itself: ~2ms
IMPACT_LP_HZ_SOFT   = 2100.0   # one-pole lowpass cutoff, soft hit (duller)
IMPACT_LP_HZ_HARD   = 4300.0   # ...and hard hit (brighter). Rolling off the top
                               # end is what stops the noise layer sounding like
                               # a hiss -- i.e. what stops it sounding like glass.
IMPACT_THUD_HZ      = 150.0    # low-frequency body -- perceived MASS. Raised from
                               # 90Hz, which was so low it was felt more than
                               # heard on small speakers.
IMPACT_THUD_DECAY   = 110.0    # thud gone in ~25ms
IMPACT_THUD_MIX     = 0.55     # more weight than r8's 0.35 -- "solid, dense"
IMPACT_DURATION_S   = 0.035    # halved (was 0.07). With decay >= 190 the sound is
                               # long dead by here; a longer buffer was just
                               # silence, and silence costs memory and latency.
IMPACT_TIERS        = 6        # pre-rendered timbre tiers (Maker's call: tiers
                               # cached at init, not per-impact synthesis -- a
                               # pure-Python buffer per collision would run in
                               # the main thread, and a break puts a dozen
                               # near-simultaneous contacts in a single frame)


def impact_params(hardness):
    """Ball-hit impact model: map a 0..1 impact 'hardness' to the timbre
    parameters of the sound. Pure, no pygame -- this is the testable core of
    the velocity->timbre mapping.

    hardness is the collision impulse normalised by HIT_IMPULSE_REF and
    clamped (see impact_hardness) -- impulse, not raw velocity, because
    arbiter.total_impulse already folds in the masses, which is what actually
    determines how hard two bodies hit each other.

    Harder impacts get a BRIGHTER, SHORTER, noisier knock; softer ones a
    duller, slightly longer, cleaner one. Every parameter interpolates linearly
    between its SOFT and HARD constant, so the mapping is monotonic by
    construction. Returns a dict (r8.2: was a 3-tuple -- there are now five
    parameters, and positional unpacking of five things is a bug waiting to
    happen)."""
    h = max(0.0, min(1.0, hardness))
    lerp = lambda a, b: a + (b - a) * h
    return {
        "partial_hz": lerp(IMPACT_PARTIAL_HZ_SOFT, IMPACT_PARTIAL_HZ_HARD),
        "decay":      lerp(IMPACT_DECAY_SOFT, IMPACT_DECAY_HARD),
        "noise_mix":  lerp(IMPACT_NOISE_SOFT, IMPACT_NOISE_HARD),
        "lp_hz":      lerp(IMPACT_LP_HZ_SOFT, IMPACT_LP_HZ_HARD),
    }


def one_pole_lowpass(samples, cutoff_hz, sample_rate):
    """Single-pole IIR lowpass: y[n] = y[n-1] + a*(x[n] - y[n-1]).

    r8.2: this is what stops the sound being GLASS. The noise layer is the body
    of a polymer knock, but noise at full bandwidth (up to Nyquist, 22kHz here)
    is a HISS, and hiss is the signature of glass/ceramic. Real phenolic impact
    energy rolls off hard above a few kHz. Rolling the top end off turns a
    'tss' into a 'knock'. Pure, stdlib-only, trivially testable."""
    if cutoff_hz <= 0.0 or not samples:
        return list(samples)
    dt = 1.0 / sample_rate
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    a = dt / (rc + dt)
    out = []
    y = 0.0
    for x in samples:
        y += a * (x - y)
        out.append(y)
    return out


def synth_impact_samples(hardness, sample_rate, seed=0):
    """Ball-hit impact model (r8.2): a solid, dense polymer knock.

    Pure, dependency-free (stdlib math/random only, no numpy), deterministic
    given the same seed -- so it's exactly reproducible, unit-testable, and safe
    to cache and replay.

    The r8 model was inverted from reality: a sustained ~2kHz sine with noise
    sprinkled on the front. That is a struck wine glass. Here the NOISE is the
    body of the sound and the tonal content merely colours it:

      1. contact crack -- seeded broadband noise, decaying in ~2ms. This is now
         the loudest layer (noise_mix 0.74-0.90), not a garnish.
      2. modal body   -- THREE INHARMONIC partials (620-980Hz fundamental, times
         IMPACT_PARTIAL_RATIOS). Inharmonic on purpose: a struck sphere excites
         several modes at once, and it's the inharmonicity that makes the ear
         hear a "knock" rather than a "note". A single sine is always a pitch.
      3. thud        -- 150Hz, dead in ~25ms: perceived mass/density.

    Envelope is attack (linear, 0.5ms) then exp(-decay*t) with decay 190-420, so
    the whole thing is over in 7-15ms. No sustain: a rigid-body impact has none.

    The summed mix is then LOWPASSED (2.1-4.3kHz depending on hardness), which
    is what removes the glassy hiss from the noise layer.

    Returns a list of int16 samples (-32768..32767)."""
    p = impact_params(hardness)
    n = max(1, int(round(IMPACT_DURATION_S * sample_rate)))
    rng = random.Random(seed)
    raw = []
    for i in range(n):
        t = i / sample_rate
        # 1. contact crack -- the BODY of the sound now.
        crack = rng.uniform(-1.0, 1.0) * math.exp(-IMPACT_NOISE_DECAY * t)
        # 2. inharmonic modal body -- colours the crack, doesn't dominate it.
        modal = 0.0
        for k, ratio in enumerate(IMPACT_PARTIAL_RATIOS):
            # higher modes decay faster, as they do in a real solid
            modal += (math.sin(2.0 * math.pi * p["partial_hz"] * ratio * t)
                      * math.exp(-p["decay"] * (1.0 + 0.6 * k) * t)
                      / (k + 1.0))
        modal /= sum(1.0 / (k + 1.0) for k in range(len(IMPACT_PARTIAL_RATIOS)))
        # 3. thud -- weight.
        thud = (math.sin(2.0 * math.pi * IMPACT_THUD_HZ * t)
                * math.exp(-IMPACT_THUD_DECAY * t) * IMPACT_THUD_MIX)
        nm = p["noise_mix"]
        body = crack * nm + modal * (1.0 - nm) + thud
        # AD envelope: linear attack, then exponential decay. No sustain.
        if t < IMPACT_ATTACK_S:
            env = t / IMPACT_ATTACK_S
        else:
            env = math.exp(-p["decay"] * (t - IMPACT_ATTACK_S))
        raw.append(body * env)
    # Lowpass the whole mix -- the step that turns hiss into knock.
    filt = one_pole_lowpass(raw, p["lp_hz"], sample_rate)
    peak = max((abs(v) for v in filt), default=0.0)
    if peak < 1e-9:
        return [0] * n
    # Normalise: the lowpass costs a lot of amplitude, and the level must not
    # depend on the filter cutoff (which varies with hardness) -- loudness is
    # scale_ball_hit_volume's job, and its alone.
    g = 0.92 / peak
    return [int(max(-1.0, min(1.0, v * g)) * 32767) for v in filt]


def impact_hardness(impulse, ref=HIT_IMPULSE_REF):
    """Ball-hit impact model: collision impulse (kg*m/s, real WEPF units) ->
    0..1 hardness driving impact_params. Same normalisation and clamp as
    scale_ball_hit_volume, deliberately: one number drives BOTH how loud the
    hit is and how bright it is, so they can never disagree."""
    if impulse <= 0.0:
        return 0.0
    return min(1.0, impulse / ref)


def impact_tier(hardness, tiers=IMPACT_TIERS):
    """Ball-hit impact model: quantise 0..1 hardness to a pre-rendered tier
    index in [0, tiers-1]. Timbre steps in `tiers` increments; volume stays
    continuous (scale_ball_hit_volume), so the quantisation isn't audible as
    steps -- it just stops us synthesising a fresh buffer per collision."""
    h = max(0.0, min(1.0, hardness))
    return min(tiers - 1, int(h * tiers))


def scale_ball_hit_volume(impulse, ref=HIT_IMPULSE_REF):
    """Sound effects: maps a collision's arbiter.total_impulse magnitude
    (real WEPF units, kg*m/s) to a 0..1 playback volume. Linear up to
    'ref' (a gentle kiss should be near-silent, not clamped up to a
    noticeable floor), then clamped at 1.0 for anything harder -- a
    break-shot pile-up shouldn't try to play louder than 'full volume'
    just because the impulse number is large. impulse<=0 is always 0."""
    if impulse <= 0.0:
        return 0.0
    return min(1.0, impulse / ref)


def write_wav(path, samples, sample_rate):
    """Sound effects: write int16 mono samples to a WAV file. Stdlib `wave` +
    `array` only -- no new dependency, same discipline as the synthesis itself.

    This exists because of the r8.1 mixer bug: for a long time the sounds we
    THOUGHT we were generating and the sounds actually reaching the speakers
    were different (a mono buffer being read as stereo, so double-pitched),
    and no amount of parameter tuning could fix that -- we were tuning the
    wrong end. Exporting the buffer straight to disk lets it be auditioned
    for real, independent of pygame's mixer config entirely. Returns the
    number of samples written."""
    import wave
    import array as _array
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)                       # int16
        w.setframerate(sample_rate)
        w.writeframes(_array.array("h", samples).tobytes())
    return len(samples)


def sound_probe(out_dir=".", sample_rate=44100):
    """Sound effects: dump every voice to WAV so it can be heard directly,
    with no mixer, no game and no guessing. Writes each ball-hit tier (soft ->
    hard) plus the cue_strike/pot voices. Prints what it wrote."""
    written = []
    for i in range(IMPACT_TIERS):
        h = (i + 0.5) / IMPACT_TIERS
        p = impact_params(h)
        samples = synth_impact_samples(h, sample_rate, seed=1000 + i)
        path = os.path.join(out_dir, f"probe_ball_hit_tier{i}.wav")
        write_wav(path, samples, sample_rate)
        written.append(f"{path}  (hardness {h:.2f}: {p['partial_hz']:.0f}Hz, "
                       f"decay {p['decay']:.0f}, noise {p['noise_mix']:.2f}, "
                       f"lowpass {p['lp_hz']:.0f}Hz)")
    for kind in ("cue_strike", "pot"):
        freq, dur, decay, noise_mix = SOUND_VOICES[kind]
        samples = synth_tone_samples(freq, dur, sample_rate, decay, noise_mix,
                                     seed=hash(kind) & 0xFFFF)
        path = os.path.join(out_dir, f"probe_{kind}.wav")
        write_wav(path, samples, sample_rate)
        written.append(f"{path}  ({freq:.0f}Hz, {dur:.3f}s)")
    print(f"sound probe — {len(written)} WAV files at {sample_rate}Hz mono:")
    for line in written:
        print("  " + line)
    return written


def run_gui(smoke=False, smoke_frames=90, snap_path=None):
    if smoke:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.init()
    if not smoke:
        # Sound effects: mono, matching synth_tone_samples/synth_impact_samples
        # and array('h', ...) below. Gated `not smoke` -- no point opening an
        # audio device for a headless batch/dummy-driver run, same doctrine as
        # every visual Increment-4 overlay never touching --snap/--smoke.
        #
        # r8.1 -- THE BUG THAT MADE EVERY SOUND SOUND "PLINKY":
        # pygame.init() ALREADY initialises the mixer, with ITS defaults
        # (44100, -16, STEREO). A later pygame.mixer.init(...) is a silent
        # NO-OP -- it returns cleanly and changes nothing. So every previous
        # `mixer.init(frequency=22050, ..., channels=1)` here did nothing at
        # all, and the mixer was running in STEREO the whole time.
        #
        # That is fatal for us: we hand Sound() a MONO int16 buffer, and a
        # stereo mixer reads that same raw buffer as interleaved L/R pairs --
        # consuming TWO of our samples per output frame. Everything therefore
        # played back at DOUBLE speed and DOUBLE PITCH, in half the duration.
        # The old 900Hz "ball hit" was really sounding at ~1800Hz; the r8
        # 1900-2600Hz resonance was coming out at ~3800-5200Hz. A short, thin,
        # high blip -- i.e. "plinky", and immune to any amount of parameter
        # tuning, because the mangling dominated the timbre.
        #
        # The fix is mixer.quit() FIRST, then init with what we actually want.
        SOUND_SAMPLE_RATE = 44100
        pygame.mixer.quit()
        pygame.mixer.init(frequency=SOUND_SAMPLE_RATE, size=-16, channels=1,
                          buffer=512)
        # Never trust it silently again: assert what we actually got, and say
        # so if the device refused (some drivers force stereo/resample).
        _mix = pygame.mixer.get_init()
        if _mix is None or _mix[0] != SOUND_SAMPLE_RATE or _mix[2] != 1:
            print(f"WARNING: mixer is {_mix}, wanted "
                  f"({SOUND_SAMPLE_RATE}, -16, 1) -- sounds may be pitched "
                  f"wrong. Pass --sound-probe to audition the raw buffers.")
        sound_cache = {}

        def get_sound(kind):
            snd = sound_cache.get(kind)
            if snd is None:
                import array
                freq, dur, decay, noise_mix = SOUND_VOICES[kind]
                samples = synth_tone_samples(freq, dur, SOUND_SAMPLE_RATE,
                                              decay, noise_mix, seed=hash(kind) & 0xFFFF)
                snd = pygame.mixer.Sound(buffer=array.array('h', samples))
                sound_cache[kind] = snd
            return snd

        # r8: ball_hit no longer comes from SOUND_VOICES/get_sound -- it has
        # IMPACT_TIERS pre-rendered variants, brighter/shorter with hardness.
        # Built once here at init (Maker's call over per-impact synthesis: a
        # break lands a dozen contacts in one frame, and synthesising a
        # pure-Python buffer per contact would do that work in the main
        # thread). Each tier gets its own seed so the noise transient differs
        # between them -- reusing one noise sequence across all six would make
        # every hit sound like the same click at different brightness.
        import array as _array
        _impact_tiers = []
        for _i in range(IMPACT_TIERS):
            _h = (_i + 0.5) / IMPACT_TIERS   # tier's representative hardness
            _samples = synth_impact_samples(_h, SOUND_SAMPLE_RATE, seed=1000 + _i)
            _impact_tiers.append(pygame.mixer.Sound(buffer=_array.array('h', _samples)))

        def play_sound(kind, volume):
            snd = get_sound(kind)
            snd.set_volume(max(0.0, min(1.0, volume)))
            snd.play()

        def play_impact(impulse):
            """r8 ball-hit: one impulse drives BOTH brightness (which tier)
            and loudness (volume), so a gentle kiss is quiet AND dull while a
            break-crack is loud AND bright -- they can never disagree."""
            h = impact_hardness(impulse)
            snd = _impact_tiers[impact_tier(h)]
            snd.set_volume(max(0.0, min(1.0, scale_ball_hit_volume(impulse))))
            snd.play()
    else:
        def play_sound(kind, volume):
            pass

        def play_impact(impulse):
            pass

    # Desktop resolution for F11, captured BEFORE any window exists. Info()
    # only reliably reports the true desktop mode pre-set_mode; querying it
    # again later would return the current WINDOW's size on some backends,
    # silently turning "fullscreen" into a same-size no-op.
    _di = pygame.display.Info()
    DESKTOP_W, DESKTOP_H = _di.current_w, _di.current_h
    # Render scale. Was 2 for the (since-removed, R6.10) GL backend's true
    # supersampling; classic is RS=1, so every *RS below is a no-op kept in
    # place rather than stripped out -- same numbers, lower-risk diff.
    RS = 1
    PXM = CFG["PX_PER_M"]
    MG = CFG["MARGIN_PX"]
    x0, y0, x1, y1 = play_rect()
    # Reference (FS=1) frame size -- identical maths to the old fixed window.
    # Increment 3a scales this uniformly by the fit scale FS; the headless
    # guard (smoke/snap) always renders it at FS=1 with no panel, so the
    # byte-identical invariant is untouched.
    BASE_W1 = int(x1 * PXM + 2 * MG)
    BASE_H1 = int(y1 * PXM + 2 * MG + 46)
    PANEL_W = CFG["PANEL_W_PX"]
    fullscreen = False

    if smoke:
        win_w, win_h = BASE_W1, BASE_H1
        display = pygame.display.set_mode((win_w, win_h))
    else:
        # r22: start BORDERLESS AT DESKTOP SIZE. The old default was a small
        # RESIZABLE window (BASE_W1 + PANEL_W), which on a real monitor is too
        # small to actually play on. Borderless (NOFRAME at the desktop's own
        # resolution) rather than pygame.FULLSCREEN by choice: it does not
        # change the display mode, so it can't fight the compositor or leave the
        # monitor in a bad state on alt-tab -- the same class of display trouble
        # that cost us the GL backend at R6.10. The F11 toggle and windowed_size
        # are untouched, so you can still drop back to a window.
        #
        # BASE_* stays the RENDER reference size; rebuild_render_targets()
        # already fits the scene to whatever the window actually is (FS), so
        # a bigger window just means a bigger table, not a broken layout.
        win_w, win_h = DESKTOP_W, DESKTOP_H
        display = pygame.display.set_mode((win_w, win_h), pygame.NOFRAME)
    # What F11 restores when leaving fullscreen: the modest windowed size, NOT
    # the borderless desktop size we now start at.
    windowed_size = (BASE_W1 + PANEL_W, BASE_H1)
    pygame.display.set_caption("HUSTLER — UK pool physics sandbox (R6)")

    FS = fit_W1 = fit_H1 = W = H = S = M = RSF = None
    screen = font = panel_font = None

    def rebuild_render_targets():
        # Fullscreen + fit-to-region (Increment 3a): recompute the largest
        # uniform scale that fits the reference frame into the window minus
        # the right-hand panel, then rebuild every size-dependent object off
        # it -- the offscreen frame surface and the HUD font. Called once at
        # start-up and again on every resize / fullscreen toggle. The
        # headless guard (smoke) always fits at FS=1 with no panel reserved --
        # this reproduces the exact R6.1 framing, untouched.
        nonlocal FS, fit_W1, fit_H1, W, H, S, M, RSF, screen, font, panel_font
        if smoke:
            FS, fit_W1, fit_H1 = 1.0, BASE_W1, BASE_H1
        else:
            FS, fit_W1, fit_H1 = fit_to_region(win_w, win_h, BASE_W1, BASE_H1, PANEL_W)
        W, H = fit_W1 * RS, fit_H1 * RS
        S = PXM * FS * RS
        M = MG * FS * RS
        RSF = RS * FS
        screen = pygame.Surface((W, H))
        try:
            font = pygame.font.SysFont("consolas,menlo,monospace",
                                        max(8, int(14 * RSF)))
        except Exception:
            font = pygame.font.Font(None, max(9, int(16 * RSF)))
        if not smoke:
            # Panel widgets are drawn straight onto the WINDOW surface, not
            # through the scene surface -- fixed size, independent of scene
            # scaling.
            try:
                panel_font = pygame.font.SysFont("consolas,menlo,monospace", 14)
            except Exception:
                panel_font = pygame.font.Font(None, 16)

    rebuild_render_targets()

    def present(frame):
        return frame

    clock = pygame.time.Clock()

    def w2s(p):
        return (int(M + p[0] * S), int(M + p[1] * S))

    def s2w(p):
        return ((p[0] - M) / S, (p[1] - M) / S)

    MODES = ["SANDBOX", "YOU vs AI", "AI vs AI"]
    # Shaded ball sprites (cached per colour and radius): radial gradient
    # stepped toward a top-left light source, specular highlight, soft cloth
    # shadow. Highlights are pre-blended opaque colours — pygame.draw writes
    # raw RGBA without blending, so translucent paint over the ball would
    # punch through to the baize when blitted.
    ball_shades = {
        "red": ((116, 10, 14), (240, 96, 72)),
        "yellow": ((148, 110, 18), (250, 230, 122)),
        "black": ((8, 8, 10), (86, 86, 98)),
        "cue": ((172, 163, 138), (255, 253, 242)),
    }
    sprite_pad = 4
    sprite_cache = {}

    def lerp3(a, b, t):
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

    def ball_sprite(kind, r_px):
        key = (kind, r_px)
        if key in sprite_cache:
            return sprite_cache[key]
        size = 2 * (r_px + sprite_pad)
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = (r_px + sprite_pad, r_px + sprite_pad)
        dark, light = ball_shades.get(kind, ball_shades["red"])
        # soft shadow on the cloth (translucent against the table is wanted)
        pygame.draw.circle(surf, (0, 0, 0, 70), (c[0] + 2, c[1] + 3), r_px)
        for i in range(4):
            col = lerp3(dark, light, i / 3.0)
            rr = max(1, int(r_px * (1.0 - 0.20 * i)))
            off = int(r_px * 0.11 * i)
            pygame.draw.circle(surf, col, (c[0] - off, c[1] - off), rr)
        hx = c[0] - int(r_px * 0.38)
        hy = c[1] - int(r_px * 0.38)
        pygame.draw.circle(surf, lerp3(light, (255, 255, 255), 0.7),
                           (hx, hy), max(1, int(r_px * 0.26)))
        pygame.draw.circle(surf, lerp3(light, (255, 255, 255), 0.95),
                           (hx, hy), max(1, int(r_px * 0.12)))
        pygame.draw.circle(surf, dark, c, r_px, 1)
        sprite_cache[key] = surf
        return surf

    def draw_ball(kind, pos, r_px):
        spr = ball_sprite(kind, r_px)
        screen.blit(spr, (pos[0] - r_px - sprite_pad, pos[1] - r_px - sprite_pad))

    # ------------------------------------------------------------------
    # Hand-rolled panel widgets (Graphics Pass 3, Increment 3b). Every
    # widget binds DIRECTLY to a get()/set() pair pointing at the same live
    # variable the matching key already mutates -- no shadow state, so
    # keyboard and widget can never disagree. Interactive-only (nested here,
    # not touched by the smoke/snap headless path). Pure geometry/mapping
    # maths lives in the module-level functions above (slider_frac etc.) so
    # it gets dependency-free selftest coverage.
    # ------------------------------------------------------------------
    class Slider:
        def __init__(self, rect, lo, hi, get, set_, label, fmt="{:.2f}",
                     enabled=lambda: True):
            self.rect = pygame.Rect(rect)
            self.lo, self.hi, self.get, self.set = lo, hi, get, set_
            self.label, self.fmt, self.enabled = label, fmt, enabled
            self.dragging = False

        def _track(self):
            return pygame.Rect(self.rect.x, self.rect.y + 20, self.rect.w, 6)

        def handle_event(self, ev):
            if not self.enabled():
                self.dragging = False
                return
            track = self._track()
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if track.inflate(0, 14).collidepoint(ev.pos):
                    self.dragging = True
                    self._apply(ev.pos[0], track)
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                self.dragging = False
            elif ev.type == pygame.MOUSEMOTION and self.dragging:
                self._apply(ev.pos[0], track)

        def _apply(self, x, track):
            frac = slider_frac(x, track.x, track.x + track.w)
            self.set(slider_value(frac, self.lo, self.hi))

        def draw(self, surf, font):
            en = self.enabled()
            track = self._track()
            pygame.draw.rect(surf, (60, 64, 72), track, border_radius=3)
            frac = slider_frac(self.get(), self.lo, self.hi)
            fill_w = int(track.w * frac)
            fill_col = (140, 170, 210) if en else (70, 74, 80)
            if fill_w > 0:
                pygame.draw.rect(surf, fill_col,
                                  (track.x, track.y, fill_w, track.h), border_radius=3)
            knob_col = (225, 230, 238) if en else (110, 112, 116)
            pygame.draw.circle(surf, knob_col,
                                (track.x + fill_w, track.y + track.h // 2), 7)
            txt_col = COL["hud"] if en else (120, 122, 126)
            txt = f"{self.label}: {self.fmt.format(self.get())}"
            surf.blit(font.render(txt, True, txt_col), (self.rect.x, self.rect.y))

    class Button:
        def __init__(self, rect, label, on_click, enabled=lambda: True):
            self.rect = pygame.Rect(rect)
            self.label, self.on_click, self.enabled = label, on_click, enabled

        def handle_event(self, ev):
            if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                    and self.enabled() and self.rect.collidepoint(ev.pos)):
                self.on_click()

        def draw(self, surf, font):
            en = self.enabled()
            pygame.draw.rect(surf, (90, 140, 90) if en else (52, 55, 60),
                              self.rect, border_radius=4)
            lbl = self.label() if callable(self.label) else self.label
            txt = font.render(lbl, True,
                               (240, 240, 240) if en else (120, 122, 126))
            surf.blit(txt, txt.get_rect(center=self.rect.center))

    class SpinPad:
        """Drag the contact point in the cue-ball circle: vertical = follow
        / draw, horizontal = side, clamped to the unit circle (spin_pad_map).
        HUD-only, like every other shot parameter (no mouse-table aiming)."""
        def __init__(self, centre, radius, get, set_):
            self.centre, self.radius, self.get, self.set = centre, radius, get, set_
            self.dragging = False

        def _hit(self, pos):
            dx, dy = pos[0] - self.centre[0], pos[1] - self.centre[1]
            return math.hypot(dx, dy) <= self.radius + 6

        def handle_event(self, ev):
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self._hit(ev.pos):
                self.dragging = True
                self._apply(ev.pos)
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                self.dragging = False
            elif ev.type == pygame.MOUSEMOTION and self.dragging:
                self._apply(ev.pos)

        def _apply(self, pos):
            dx, dy = pos[0] - self.centre[0], pos[1] - self.centre[1]
            self.set(*spin_pad_map(dx, dy, self.radius))

        def draw(self, surf, font):
            cx, cy = self.centre
            pygame.draw.circle(surf, (60, 64, 72), (cx, cy), self.radius)
            pygame.draw.circle(surf, (150, 150, 150), (cx, cy), self.radius, 1)
            pygame.draw.line(surf, (100, 100, 100), (cx - self.radius, cy), (cx + self.radius, cy), 1)
            pygame.draw.line(surf, (100, 100, 100), (cx, cy - self.radius), (cx, cy + self.radius), 1)
            follow, side = self.get()
            px, py = cx + side * self.radius, cy - follow * self.radius
            pygame.draw.circle(surf, (255, 90, 90), (int(px), int(py)), 5)
            lbl = font.render(f"spin  f{follow:+.2f} s{side:+.2f}", True, COL["hud"])
            surf.blit(lbl, (cx - self.radius, cy - self.radius - 18))

    class Dial:
        """Rotating cue-angle knob (Bug-report follow-up, R6.6): drag
        anywhere around the centre to set an ABSOLUTE aim angle [0, 360)
        via dial_angle() -- the table's mouse no longer has any bearing on
        aim at all, so this is the sole coarse-angle control. A handle dot
        on the rim shows the current direction."""
        def __init__(self, centre, radius, get, set_):
            self.centre, self.radius, self.get, self.set = centre, radius, get, set_
            self.dragging = False

        def _hit(self, pos):
            dx, dy = pos[0] - self.centre[0], pos[1] - self.centre[1]
            return math.hypot(dx, dy) <= self.radius + 6

        def handle_event(self, ev):
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self._hit(ev.pos):
                self.dragging = True
                self._apply(ev.pos)
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                self.dragging = False
            elif ev.type == pygame.MOUSEMOTION and self.dragging:
                self._apply(ev.pos)

        def _apply(self, pos):
            dx, dy = pos[0] - self.centre[0], pos[1] - self.centre[1]
            self.set(dial_angle(dx, dy))

        def draw(self, surf, font):
            cx, cy = self.centre
            pygame.draw.circle(surf, (60, 64, 72), (cx, cy), self.radius)
            pygame.draw.circle(surf, (150, 150, 150), (cx, cy), self.radius, 1)
            ang = self.get()
            hx, hy = rotate_vector(1.0, 0.0, ang)
            ex, ey = cx + hx * self.radius, cy + hy * self.radius
            pygame.draw.aaline(surf, (200, 200, 200), (cx, cy), (ex, ey))
            pygame.draw.circle(surf, (255, 90, 90), (int(ex), int(ey)), 6)
            lbl = font.render(f"aim angle  {ang:5.1f} deg", True, COL["hud"])
            surf.blit(lbl, (cx - self.radius, cy - self.radius - 18))

    class TabStrip:

        def __init__(self, rect, labels, get_index, set_index):
            self.rect, self.labels = pygame.Rect(rect), labels
            self.get, self.set = get_index, set_index

        def _tab_rect(self, i):
            w = self.rect.w // len(self.labels)
            return pygame.Rect(self.rect.x + i * w, self.rect.y, w, self.rect.h)

        def handle_event(self, ev):
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                for i in range(len(self.labels)):
                    if self._tab_rect(i).collidepoint(ev.pos):
                        self.set(i)

        def draw(self, surf, font):
            cur = self.get()
            for i, lab in enumerate(self.labels):
                r = self._tab_rect(i)
                pygame.draw.rect(surf, (60, 90, 120) if i == cur else (42, 45, 51), r)
                txt = font.render(lab, True, COL["hud"])
                surf.blit(txt, txt.get_rect(center=r.center))
            pygame.draw.line(surf, (68, 72, 80),
                              (self.rect.x, self.rect.bottom), (self.rect.right, self.rect.bottom), 1)

    sim = Sim()
    game = None
    ais = None
    ai_plan = None
    ai_wait = 0
    pending = False        # a struck shot awaits rules resolution
    mode = 0
    power = CFG["POWER_DEFAULT"]
    spin_side, spin_follow = 0.0, 0.0
    show_overlay = True
    aim_angle = 0.0          # degrees [0,360), absolute, HUD-only (no mouse aim)
    panel_tab = 0            # 0=Shot, 1=Table, 2=Game, 3=Custom (r10)
    # r10 custom mode (trick-shot / practice editor). Active only when the
    # Custom tab is selected -- see custom_active(). Ball placement uses MOUSE
    # CLICKS ON THE TABLE, which deliberately reverses R6.6's "HUD-only, no
    # mouse-table interaction" rule FOR THIS MODE ONLY (Maker signed this off
    # explicitly). Table clicks still do nothing in Shot/Table/Game.
    place_kind = 1           # index into PLACE_KINDS -- default "red"
    drag_bid = None          # id of the ball currently being dragged, or None
    layout_slot = 0          # which save slot the Save/Load buttons act on
    layout_msg = ""          # last save/load result, shown in the Custom tab
    trail_history = {}       # bid -> deque of recent (x, y), Increment 4a
    pot_anims = []            # list of dicts, Increment 4b (pot swallow anim)
    vignette_surface_cache = {}  # (W, H) -> Surface, Increment 4d -- static
                                   # per-size, rebuilt only on resize/fit
                                   # change, not per frame
    grade_idx = 0              # Colour-grade: 0=Warm, 1=Cool, 2=Contrast --
                                # user-switchable (Table tab TabStrip), no
                                # trigger, no "off" state, always one active
    grade_surface_cache = {}   # (W, H, grade_idx) -> Surface, resize cache
    last_black_cup = None     # world metres, Increment 4c -- set whenever a
                               # black is captured, so the finale (which only
                               # fires once the table has FULLY come to rest,
                               # frames after the actual capture) still knows
                               # where to keep the glow lit
    finale = None              # dict or None, Increment 4c (slow-mo black)
    frames = 0
    running = True
    last_shown = screen
    def start_game(m):
        controllers = ("human", "ai") if m == 1 else ("ai", "ai")
        names = ("YOU", "SHARK") if m == 1 else ("SHARK", "STEADY")
        s, g = new_game(controllers=controllers, names=names)
        return s, g, default_ais()

    # ------------------------------------------------------------------
    # Shared actions (Increment 3b): SPACE / M / T / X / G and the panel's
    # Shoot / mode / rack / reset-spin / overlay controls all call the SAME
    # function, so a widget and its mirrored key can never drift apart --
    # the lesson from finding 6.15 (glue bugs hiding behind a correct-looking
    # value) applied to controls, not just resize maths.
    # ------------------------------------------------------------------
    def my_turn():
        return (mode == 0 or (game is not None and not game.over
                and game.controllers[game.current] == "human"))

    def do_shoot():
        nonlocal pending
        cue = sim.cue()
        if not shoot_enabled(cue is not None, sim.all_at_rest(), my_turn()):
            return
        dx, dy = rotate_vector(1.0, 0.0, aim_angle)
        sim.strike((dx, dy), power, side=spin_side, follow=spin_follow)
        if not smoke:
            play_sound("cue_strike", power / CFG["POWER_MAX"])
        if game is not None:
            pending = True

    def do_cycle_mode():
        nonlocal mode, sim, game, ais, ai_plan, ai_wait, pending
        mode = (mode + 1) % len(MODES)
        ai_plan, ai_wait, pending = None, 0, False
        trail_history.clear()
        pot_anims.clear()
        if mode == 0:
            sim, game, ais = Sim(), None, None
        else:
            sim, game, ais = start_game(mode)
            if game.controllers[0] == "ai":
                sim.break_shot(power=6.0)
                pending = True
            else:
                game.last_event = "your break — aim at the pack"

    def do_rack():
        nonlocal sim, game, ais, ai_plan, ai_wait, pending
        trail_history.clear()
        pot_anims.clear()
        finale = None
        if mode == 0:
            sim.rack()
        else:
            sim, game, ais = start_game(mode)
            ai_plan, ai_wait, pending = None, 0, False
            if game.controllers[0] == "ai":
                sim.break_shot(power=6.0)
                pending = True
            else:
                game.last_event = "your break — aim at the pack"

    def do_reset_spin():
        nonlocal spin_side, spin_follow
        spin_side, spin_follow = 0.0, 0.0

    def do_toggle_overlay():
        nonlocal show_overlay
        show_overlay = not show_overlay

    def set_power(v):
        nonlocal power
        power = max(CFG["POWER_MIN"], min(CFG["POWER_MAX"], v))

    def set_aim_angle(v):
        nonlocal aim_angle
        aim_angle = v % 360.0

    def nudge_aim_angle(delta):
        nonlocal aim_angle
        aim_angle = (aim_angle + delta) % 360.0

    def set_spin(follow, side):
        nonlocal spin_follow, spin_side
        spin_follow, spin_side = follow, side

    def nudge_spin_by(d_follow, d_side):
        """r10: fine spin adjustment. Delegates the clamp to nudge_spin so the
        buttons obey exactly the same unit-circle spin budget as a pad drag."""
        nonlocal spin_follow, spin_side
        spin_follow, spin_side = nudge_spin(spin_follow, spin_side,
                                            d_follow, d_side)

    # ---- r10 custom mode ---------------------------------------------------
    def custom_active():
        """Mouse-table interaction is enabled ONLY here -- the Custom tab, in
        SANDBOX mode, with the table at rest. Everywhere else R6.6 still holds:
        the table is not clickable."""
        return (panel_tab == 3 and mode == 0 and sim.all_at_rest())

    def set_place_kind(i):
        nonlocal place_kind
        place_kind = i

    def set_layout_slot(i):
        nonlocal layout_slot
        layout_slot = i

    def do_clear_table():
        """Clear every object ball, leaving the cue. The cue is respotted rather
        than removed -- a table with no cue ball is not a practice setup, it's a
        broken state you'd have to click your way out of."""
        nonlocal layout_msg
        trail_history.clear()
        pot_anims.clear()
        sim.clear_objects()
        if sim.cue() is None:
            sim._respot_cue()
        layout_msg = "table cleared"

    def custom_balls():
        """Current table as a (kind, (x, y)) list, metres. 'kind' is the ball's
        colour, which is exactly what a layout needs to restore."""
        out = []
        for bid, (body, _) in sim.balls.items():
            kind = "cue" if bid == Sim.CUE_ID else sim.colours.get(bid, "red")
            out.append((kind, (body.position.x, body.position.y)))
        return out

    def place_ball_at(world_pos):
        """Drop the currently-selected ball kind at world_pos, if legal."""
        nonlocal layout_msg
        kind = PLACE_KINDS[place_kind]
        r_new = CFG["CUE_R_M"] if kind == "cue" else ball_r()
        existing = [((b.position.x, b.position.y), s.radius)
                    for bid, (b, s) in sim.balls.items()
                    if not (kind == "cue" and bid == Sim.CUE_ID)]
        if not can_place_ball(world_pos, existing, r_new,
                              [r for (_, r) in existing]):
            layout_msg = "can't place there"
            return
        if kind == "cue":
            # Only ever ONE cue ball: move the existing one rather than adding.
            cue = sim.cue()
            if cue is not None:
                cue.position = world_pos
                cue.velocity = (0.0, 0.0)
            else:
                sim._add_ball(Sim.CUE_ID, world_pos, "cue")
            layout_msg = "cue placed"
            return
        bid = sim.alloc_id()
        sim._add_ball(bid, world_pos, kind)
        if kind == "black":
            sim.black_id = bid
        layout_msg = f"{kind} placed"

    def ball_at(world_pos):
        """Which ball (if any) is under world_pos -- for drag and remove."""
        for bid, (body, shape) in sim.balls.items():
            if math.dist((body.position.x, body.position.y), world_pos) <= shape.radius:
                return bid
        return None

    def remove_ball_at(world_pos):
        nonlocal layout_msg
        bid = ball_at(world_pos)
        if bid is None:
            return
        if bid == Sim.CUE_ID:
            layout_msg = "can't remove the cue"
            return
        body, shape = sim.balls.pop(bid)
        sim.space.remove(body, shape)
        trail_history.pop(bid, None)
        layout_msg = "ball removed"

    def layout_path(slot):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            f"hustler_layout_{slot}.json")

    def do_save_layout():
        nonlocal layout_msg
        try:
            with open(layout_path(layout_slot), "w", encoding="utf-8") as f:
                json.dump(serialise_layout(custom_balls()), f, indent=2)
            layout_msg = f"saved slot {layout_slot + 1}"
        except OSError as e:
            layout_msg = f"save failed: {e.strerror}"

    def do_load_layout():
        nonlocal layout_msg
        path = layout_path(layout_slot)
        try:
            with open(path, "r", encoding="utf-8") as f:
                balls = deserialise_layout(json.load(f))
        except FileNotFoundError:
            layout_msg = f"slot {layout_slot + 1} is empty"
            return
        except (OSError, ValueError) as e:
            layout_msg = "load failed: bad file"
            return
        if not balls:
            layout_msg = "nothing in that layout"
            return
        trail_history.clear()
        pot_anims.clear()
        sim.clear_objects()
        for (kind, pos) in balls:
            if kind == "cue":
                cue = sim.cue()
                if cue is not None:
                    cue.position = pos
                    cue.velocity = (0.0, 0.0)
                else:
                    sim._add_ball(Sim.CUE_ID, pos, "cue")
            else:
                bid = sim.alloc_id()
                sim._add_ball(bid, pos, kind)
                if kind == "black":
                    sim.black_id = bid
        layout_msg = f"loaded slot {layout_slot + 1}"

    def set_tab(i):
        nonlocal panel_tab
        panel_tab = i

    def set_grade(i):
        nonlocal grade_idx
        grade_idx = i

    def set_roll_decel(v):
        CFG["ROLL_DECEL"] = max(0.02, min(0.5, v))

    def set_ball_radius(v):
        sim.set_ball_radius(max(0.015, min(0.035, v)))

    # Panel widget instances, rebuilt whenever the window (and hence the
    # panel's rect) changes size -- see build_panel_widgets() below.
    # r12.1: "Cust", not "Custom" -- four tabs do not fit the 260px tabstrip at
    # this font size, and the full word was clipped mid-glyph at the panel edge.
    # NB this is the LABEL only: panel_widgets is keyed by these strings, so the
    # Custom tab's widget list is registered under "Cust" too.
    TAB_LABELS = ["Shot", "Table", "Game", "Cust"]
    # r11: reserved height for the persistent status strip above the tabs. This
    # is where the old bottom-of-table HUD now lives (Maker's call), and unlike
    # the tab contents it is drawn on EVERY tab -- the readout has to be visible
    # while you're adjusting spin on Shot AND cushion e on Table, which a tabbed
    # panel fundamentally cannot do from inside a tab.
    # 113px = 7 lines at the panel font's 15px, plus padding. Sized to what the
    # readout ACTUALLY needs (measured: 6 physics fields pack to 3 lines, plus
    # spin, plus up to 3 lines of game status) -- NOT to whatever headroom
    # happened to be spare. A first pass sized it to spare headroom (62px) and
    # silently clipped the entire game-status line, which is the single most
    # important thing on screen during a game. The dial and spin pad were
    # shrunk slightly to pay for this; the aim/spin separation gap was NOT
    # touched, because that gap is the r10 fix.
    STATUS_STRIP_H = 113
    panel_widgets = {"tabstrip": None, "Shot": [], "Table": [], "Game": []}

    def build_panel_widgets():
        px = win_w - PANEL_W + 14           # inner-panel left margin
        pw = PANEL_W - 28                   # inner-panel usable width
        # r11: the persistent status strip lives ABOVE the tabs and is drawn on
        # EVERY tab -- that's the whole point of moving the bottom HUD here. A
        # tabbed panel can't show an always-visible readout, so the strip is
        # deliberately outside the tab system. STATUS_STRIP_H is reserved space:
        # the tabs and every tab's widgets start below it.
        y = STATUS_STRIP_H
        panel_widgets["tabstrip"] = TabStrip((win_w - PANEL_W, y, PANEL_W, 26),
                                              TAB_LABELS, lambda: panel_tab, set_tab)
        y += 32

        shot = []
        shot.append(Slider((px, y, pw, 34), CFG["POWER_MIN"], CFG["POWER_MAX"],
                            lambda: power, set_power, "power", "{:.2f} m/s"))
        y += 42

        # r11: dial/pad shrunk (48->38, 46->36) to pay for the taller status
        # strip. The aim/spin SEPARATION GAP below is deliberately NOT shrunk --
        # that gap is the r10 fix for aim buttons stealing clicks from the pad.
        dial_r = min(38, pw // 2 - 8)
        dial_cx, dial_cy = px + pw // 2, y + dial_r + 14
        shot.append(Dial((dial_cx, dial_cy), dial_r, lambda: aim_angle, set_aim_angle))
        y = dial_cy + dial_r + 8
        nudge_w = (pw - 8) // 2
        shot.append(Button((px, y, nudge_w, 22), "-1 deg",
                            lambda: nudge_aim_angle(-1.0)))
        shot.append(Button((px + nudge_w + 8, y, nudge_w, 22), "+1 deg",
                            lambda: nudge_aim_angle(1.0)))
        y += 25
        shot.append(Button((px, y, nudge_w, 22), "-0.1 deg",
                            lambda: nudge_aim_angle(-0.1)))
        shot.append(Button((px + nudge_w + 8, y, nudge_w, 22), "+0.1 deg",
                            lambda: nudge_aim_angle(0.1)))
        y += 25
        # r10: 0.01 deg -- Maker's finding that 0.1 deg still isn't fine enough
        # to land a dead-true angle on long/thin cuts.
        shot.append(Button((px, y, nudge_w, 22), "-0.01 deg",
                            lambda: nudge_aim_angle(-0.01)))
        shot.append(Button((px + nudge_w + 8, y, nudge_w, 22), "+0.01 deg",
                            lambda: nudge_aim_angle(0.01)))
        # r10: HARD SEPARATION between the aim group and the spin group. The
        # 0.1 deg row used to sit flush against the SpinPad's hit circle (which
        # extends radius+6 px), so aim clicks landed on the pad and vice versa.
        # This gap is the fix -- it is not decorative, don't close it up.
        y += 34

        pad_r = min(36, pw // 2 - 4)
        pad_cx, pad_cy = px + pw // 2, y + pad_r + 12
        shot.append(SpinPad((pad_cx, pad_cy), pad_r,
                             lambda: (spin_follow, spin_side), set_spin))
        y = pad_cy + pad_r + 8
        # r10: spin fine adjustment. The pad is drag-only, and a drag can't
        # resolve better than one pixel -- at this pad size that's ~0.02 of spin
        # per pixel, so a precise contact point was simply unreachable. These
        # nudge in 0.01 steps, re-clamped to the unit circle by nudge_spin so
        # they can never walk outside the pad's own physical spin budget.
        q = (pw - 12) // 4
        shot.append(Button((px, y, q, 22), "draw",
                            lambda: nudge_spin_by(-0.01, 0.0)))
        shot.append(Button((px + q + 4, y, q, 22), "foll",
                            lambda: nudge_spin_by(0.01, 0.0)))
        shot.append(Button((px + 2 * (q + 4), y, q, 22), "left",
                            lambda: nudge_spin_by(0.0, -0.01)))
        shot.append(Button((px + 3 * (q + 4), y, q, 22), "right",
                            lambda: nudge_spin_by(0.0, 0.01)))
        y += 28
        shot.append(Button((px, y, pw // 2 - 4, 26), "Reset spin", do_reset_spin))
        shot.append(Button((px + pw // 2 + 4, y, pw // 2 - 4, 26), "Shoot", do_shoot,
                            enabled=lambda: shoot_enabled(
                                sim.cue() is not None, sim.all_at_rest(), my_turn())))
        panel_widgets["Shot"] = shot

        table = []
        y2 = STATUS_STRIP_H + 34   # r11: below the persistent status strip
        table.append(Slider((px, y2, pw, 34), 0.05, 1.0,
                             lambda: CFG["CUSHION_ELASTICITY"],
                             lambda v: sim.set_cushion_elasticity(v),
                             "cushion e", "{:.2f}"))
        y2 += 42
        table.append(Slider((px, y2, pw, 34), 0.02, 0.5,
                             lambda: CFG["ROLL_DECEL"], set_roll_decel,
                             "roll decel", "{:.3f} m/s2"))
        y2 += 42
        table.append(Slider((px, y2, pw, 34), 0.015, 0.035,
                             lambda: CFG["BALL_R_M"], set_ball_radius,
                             "ball radius", "{:.4f} m", enabled=lambda: mode == 0))
        y2 += 42
        table.append(Button((px, y2, pw, 28),
                             lambda: ("Cue: 1-7/8\" 94g" if CFG["CUE_R_M"] < 0.025
                                      else "Cue: 2\" 116g"),
                             sim.toggle_cue_size))
        y2 += 36
        table.append(TabStrip((px, y2, pw, 26),
                               [g[0] for g in GRADE_DEFS],
                               lambda: grade_idx, set_grade))
        panel_widgets["Table"] = table

        game_w = []
        y3 = STATUS_STRIP_H + 34   # r11: below the persistent status strip
        game_w.append(Button((px, y3, pw, 28),
                              lambda: f"Mode: {MODES[mode]} (M)", do_cycle_mode))
        y3 += 36
        game_w.append(Button((px, y3, pw, 28), "Rack up (T)", do_rack))
        y3 += 36
        game_w.append(Button((px, y3, pw, 28), "Toggle overlay (G)", do_toggle_overlay))
        panel_widgets["Game"] = game_w

        # r10 Custom tab -- trick-shot / practice editor. All of this is inert
        # unless mode == SANDBOX (custom_active()), and the buttons say so.
        custom = []
        y4 = STATUS_STRIP_H + 34   # r11: below the persistent status strip
        custom.append(TabStrip((px, y4, pw, 26),
                                [k.capitalize() for k in PLACE_KINDS],
                                lambda: place_kind, set_place_kind))
        y4 += 34
        custom.append(Button((px, y4, pw, 26), "Clear table", do_clear_table,
                              enabled=lambda: mode == 0))
        y4 += 34
        custom.append(TabStrip((px, y4, pw, 26), ["1", "2", "3", "4"],
                                lambda: layout_slot, set_layout_slot))
        y4 += 34
        half = pw // 2 - 4
        custom.append(Button((px, y4, half, 26), "Save", do_save_layout,
                              enabled=lambda: mode == 0))
        custom.append(Button((px + pw // 2 + 4, y4, half, 26), "Load",
                              do_load_layout, enabled=lambda: mode == 0))
        panel_widgets["Cust"] = custom   # key MUST match TAB_LABELS (r12.1)

    if smoke:
        mode = 2
        sim, game, ais = start_game(mode)
        sim.break_shot(power=6.0)
        pending = True
        spin_side, spin_follow = -0.5, 0.5
    else:
        build_panel_widgets()

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                shift = ev.mod & pygame.KMOD_SHIFT
                if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif ev.key == pygame.K_SPACE:
                    do_shoot()
                elif ev.key == pygame.K_m:
                    do_cycle_mode()
                elif ev.key == pygame.K_k:
                    sim.toggle_cue_size()
                elif ev.key == pygame.K_t:
                    do_rack()
                elif ev.key == pygame.K_e:
                    sim.set_cushion_elasticity(
                        CFG["CUSHION_ELASTICITY"] + (-0.05 if shift else 0.05))
                elif ev.key == pygame.K_f:
                    CFG["ROLL_DECEL"] = max(0.02, min(0.5,
                        CFG["ROLL_DECEL"] + (-0.02 if shift else 0.02)))
                elif ev.key == pygame.K_b and mode == 0:
                    sim.set_ball_radius(CFG["BALL_R_M"] + (-0.001 if shift else 0.001))
                elif ev.key == pygame.K_n and mode == 0:
                    sim.add_random_ball()
                elif ev.key == pygame.K_c and mode == 0:
                    sim.clear_objects()
                elif ev.key == pygame.K_r and mode == 0:
                    CFG["BALL_R_M"] = 0.0254
                    sim.rebuild()
                    trail_history.clear()
                    pot_anims.clear()
                    finale = None
                elif ev.key == pygame.K_g:
                    do_toggle_overlay()
                elif ev.key == pygame.K_F11 and not smoke:
                    fullscreen = not fullscreen
                    if fullscreen:
                        windowed_size = (win_w, win_h)
                        win_w, win_h = DESKTOP_W, DESKTOP_H
                        display = pygame.display.set_mode((win_w, win_h), pygame.FULLSCREEN)
                    else:
                        win_w, win_h = windowed_size
                        # SDL quirk: the FIRST set_mode() back out of
                        # FULLSCREEN is sometimes a no-op (the surface stays
                        # at the fullscreen size) -- calling it twice is the
                        # standard workaround and is otherwise harmless.
                        pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
                        display = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
                    rebuild_render_targets()
                    build_panel_widgets()
            elif ev.type == pygame.VIDEORESIZE and not smoke and not fullscreen:
                win_w, win_h = ev.w, ev.h
                display = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
                rebuild_render_targets()
                build_panel_widgets()
            elif (ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                              pygame.MOUSEMOTION) and not smoke):
                # Panel widgets only claim events inside their own rects
                # (each widget hit-tests itself) -- everything left of the
                # panel (aiming, SPACE) is untouched.
                panel_widgets["tabstrip"].handle_event(ev)
                for w in panel_widgets[TAB_LABELS[panel_tab]]:
                    w.handle_event(ev)

                # r10 custom mode -- MOUSE ON THE TABLE. This is the deliberate,
                # signed-off reversal of R6.6's "HUD-only, no mouse-table
                # interaction" rule, and it is scoped as narrowly as possible:
                # custom_active() requires the Custom tab AND sandbox mode AND a
                # table at rest, so in Shot/Table/Game the table remains exactly
                # as unclickable as R6.6 made it. Nothing here touches aiming --
                # aim is still HUD-only, always.
                if custom_active():
                    on_panel = (ev.__dict__.get("pos", (0, 0))[0]
                                >= win_w - PANEL_W)
                    if (ev.type == pygame.MOUSEBUTTONDOWN and not on_panel):
                        wp = s2w(ev.pos)
                        if ev.button == 1:
                            hit = ball_at(wp)
                            if hit is not None:
                                drag_bid = hit      # grab and drag an existing ball
                            else:
                                place_ball_at(wp)   # empty baize: drop a new one
                        elif ev.button == 3:
                            remove_ball_at(wp)
                    elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                        drag_bid = None
                    elif (ev.type == pygame.MOUSEMOTION and drag_bid is not None
                          and not on_panel):
                        wp = s2w(ev.pos)
                        entry = sim.balls.get(drag_bid)
                        if entry is not None:
                            body, shape = entry
                            others = [((b.position.x, b.position.y), s.radius)
                                      for bid, (b, s) in sim.balls.items()
                                      if bid != drag_bid]
                            if can_place_ball(wp, others, shape.radius,
                                              [r for (_, r) in others]):
                                body.position = wp
                                body.velocity = (0.0, 0.0)
                # r13 ball in hand -- the HUMAN may reposition the cue ball in
                # baulk on the break and after a foul. This extends the R6.6
                # mouse-table reversal to a second narrow case (custom mode was
                # the first): it is gated to a human striker who actually HAS
                # ball in hand, on a table at rest, and the cue ball ONLY -- no
                # other ball is touchable, and aiming remains HUD-only always.
                elif (game is not None and game.ball_in_hand and my_turn()
                      and sim.all_at_rest()):
                    on_panel = (ev.__dict__.get("pos", (0, 0))[0]
                                >= win_w - PANEL_W)
                    if not on_panel and ev.type in (pygame.MOUSEBUTTONDOWN,
                                                    pygame.MOUSEMOTION):
                        pressed = (ev.type == pygame.MOUSEBUTTONDOWN
                                   and ev.button == 1) or \
                                  (ev.type == pygame.MOUSEMOTION
                                   and ev.buttons[0])
                        if pressed:
                            wp = s2w(ev.pos)
                            cue = sim.cue()
                            others = [((b.position.x, b.position.y), s.radius)
                                      for bid, (b, s) in sim.balls.items()
                                      if bid != Sim.CUE_ID]
                            if cue is not None and can_place_cue(
                                    wp, others, CFG["CUE_R_M"]):
                                cue.position = wp
                                cue.velocity = (0.0, 0.0)
                else:
                    drag_bid = None

        sim.step(1.0 / CFG["FPS"])

        # ---- game logic (modes 1 and 2) ----
        if game is not None and sim.all_at_rest():
            if pending:
                was_over = game.over
                game.on_rest(sim)
                pending = False
                ai_plan, ai_wait = None, 0
                # Increment 4c: the finale is a pure render-layer reaction
                # to the win/loss RESOLVING -- rules/game.over/winner are
                # entirely unaffected by whether this fires or gets drawn.
                # last_black_cup is set (in the 4b block below) whenever a
                # black is captured, which is always the case here: the
                # only way on_rest() ever sets game.over is the black-pot
                # branch. Gated `not smoke` at the point it's actually
                # drawn, same doctrine as 4a/4b.
                if not smoke and not was_over and game.over:
                    finale = {"start_frame": frames,
                              "cup": last_black_cup}
            if (not game.over and not pending
                    and game.controllers[game.current] == "ai"):
                if ai_plan is None:
                    if game.ball_in_hand:
                        ais[game.current].place_cue(sim, game.legal_colours(sim))
                    ai_plan = ais[game.current].choose(sim, game.legal_colours(sim))
                    ai_wait = 45 if not smoke else 2
                elif ai_wait > 0:
                    ai_wait -= 1
                else:
                    if ai_plan is not None:
                        sim.strike(ai_plan["aim"], ai_plan["power"],
                                   side=ai_plan.get("side", 0.0),
                                   follow=ai_plan.get("follow", 0.0))
                        pending = True
                    ai_plan = None

        # Aim point in world metres; smoke aims just off the pack apex
        if smoke:
            objs = sim.object_positions()
            if objs:
                apex = min(objs, key=lambda p: p[0])
                aim_pos = (apex[0], apex[1] + 0.006)
            else:
                aim_pos = (x1, y0)
        else:
            _c = sim.cue()
            if _c is not None:
                _dx, _dy = rotate_vector(1.0, 0.0, aim_angle)
                aim_pos = (_c.position.x + _dx, _c.position.y + _dy)
            else:
                aim_pos = (x1, y0)

        # ---- table: cushion_path.py's own layered render (R6.1) — the
        # tangent-true table art built in the geometry module, matching the
        # physics one-to-one: wooden rail + cushion slope, baize, nose
        # highlight, throat wraps (fabric into the drop) and depth-shaded
        # pockets. Driven at this table's 7ft dims + corner/middle mouths;
        # mm -> screen via w2s so art and physics share one geometry.
        cushion_geo.configure(
            play_w=CFG["PLAY_W_M"] * 1000.0, play_h=CFG["PLAY_H_M"] * 1000.0,
            corner_mouth=CFG["POCKET_MOUTH_M"] * 1000.0,
            middle_mouth=CFG["POCKET_MIDDLE_MOUTH_M"] * 1000.0)
        screen.fill(cushion_geo.COL_BG)
        _Tmm  = lambda p: w2s((p[0] / 1000.0, p[1] / 1000.0))
        _Spxm = lambda mm: max(1, int((mm / 1000.0) * S))
        cushion_geo.draw_table(screen, _Tmm, _Spxm)
        # Baulk line and pyramid spot (our functional markings, kept subtle)
        bx = x0 + (x1 - x0) * CFG["BAULK_FRAC"]
        pygame.draw.line(screen, (150, 195, 160), w2s((bx, y0)), w2s((bx, y1)), max(1, round(RSF)))
        pygame.draw.circle(screen, (185, 215, 190), w2s((x0 + (x1 - x0) * 0.75, (y0 + y1) / 2)), max(1, int(2 * RSF)))

        cue = sim.cue()
        aim_txt = ""
        human_turn = (mode == 0 or (game is not None and not game.over
                      and game.controllers[game.current] == "human"))
        # AI shot preview while it 'considers'
        if game is not None and ai_plan is not None and sim.all_at_rest():
            cp = w2s(cue.position) if cue is not None else None
            if cp is not None:
                gp = w2s(ai_plan["ghost"])
                pygame.draw.aaline(screen, COL["line"], cp, gp)
                if ai_plan["pocket"] is not None:
                    pygame.draw.aaline(screen, COL["objline"],
                                       w2s(ai_plan["target"]), w2s(ai_plan["pocket"]))
        if show_overlay and human_turn and cue is not None and sim.all_at_rest():
            aim = (aim_pos[0] - cue.position.x, aim_pos[1] - cue.position.y)
            dxy = vnorm(*aim)
            if dxy != (0.0, 0.0):
                r = ball_r()
                rc = CFG["CUE_R_M"]
                gb = ghost_ball(tuple(cue.position), aim, sim.object_positions(), rc, r)
                if gb:
                    gx, gy = gb["ghost"]
                    pa = pot_assessment(gb)
                    prob = pa["prob"] if pa else 0.0
                    tint = pot_chance_colour(prob)

                    # r14: everything below is drawn onto ONE SRCALPHA overlay
                    # surface, then blitted. pygame.draw with an RGBA colour
                    # writes flat, NON-composited pixels straight onto an opaque
                    # surface -- it does not alpha-blend -- so real translucency
                    # needs a separate surface. Same discipline as the vignette
                    # and colour-grade passes.
                    ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA)

                    def glow_line(a, b, col, core_w, glow_w, alpha):
                        """Layered line: a wide, faint glow beneath a crisp core.
                        This layering IS the difference between a 1980s vector
                        hairline and something that reads as modern."""
                        for w, al in ((glow_w, alpha // 5),
                                      (max(1, glow_w // 2), alpha // 3),
                                      (core_w, alpha)):
                            pygame.draw.line(ov, (*col, al), a, b, max(1, int(w)))

                    cs = w2s(cue.position)
                    gs = w2s((gx, gy))
                    # Cue -> ghost, tapered: segment alpha falls with distance,
                    # because certainty does.
                    SEGS = 14
                    for i in range(SEGS):
                        a = (cs[0] + (gs[0] - cs[0]) * i / SEGS,
                             cs[1] + (gs[1] - cs[1]) * i / SEGS)
                        b = (cs[0] + (gs[0] - cs[0]) * (i + 1) / SEGS,
                             cs[1] + (gs[1] - cs[1]) * (i + 1) / SEGS)
                        glow_line(a, b, tint, max(1, int(2 * RSF)),
                                  max(2, int(7 * RSF)), aim_taper_alpha(i, SEGS))

                    # Target pocket glow -- only when the pot is actually on, so
                    # it means something rather than always being lit.
                    if pa and prob > 0.12:
                        pp = w2s(pa["pocket"])
                        for k, rad in enumerate((int(20 * RSF), int(13 * RSF),
                                                 int(7 * RSF))):
                            pygame.draw.circle(ov, (*tint, int(26 + 34 * k * prob)),
                                               pp, max(1, rad))

                    # Object-ball line to the pocket, in the same pot-chance tint.
                    tx, ty = gb["target"]
                    path = one_bounce_path((tx, ty), gb["obj_dir"], r)
                    for a, b in zip(path, path[1:]):
                        glow_line(w2s(a), w2s(b), tint, max(1, int(2 * RSF)),
                                  max(2, int(6 * RSF)), 150)

                    # Tangent / cue departure line -- cool white, so it reads as
                    # a different quantity from the pot line.
                    if gb["cue_dir"] != (0.0, 0.0):
                        cpath = one_bounce_path((gx, gy), gb["cue_dir"], rc, tail=0.25)
                        for a, b in zip(cpath, cpath[1:]):
                            glow_line(w2s(a), w2s(b), (150, 200, 255),
                                      max(1, int(1 * RSF)), max(2, int(4 * RSF)), 90)

                    # Ghost ball: a translucent SHADED ball, not a wire circle.
                    # Reusing ball_sprite means it's lit exactly like a real ball.
                    gr = max(2, int(rc * S))
                    spr = ball_sprite("cue", gr).copy()
                    spr.set_alpha(105)
                    ov.blit(spr, (gs[0] - spr.get_width() // 2,
                                  gs[1] - spr.get_height() // 2))
                    pygame.draw.circle(ov, (*tint, 220), gs, gr, max(1, int(2 * RSF)))

                    # r14: predicted CUE REST -- spin-aware, so this moves live as
                    # you change follow/draw/side on the SpinPad. estimate_leave
                    # already models it; it was simply never shown.
                    if pa:
                        est = pot_estimate(tuple(cue.position), (tx, ty),
                                           pa["pocket"], 0.05, rc, r, 0.0)
                        if est:
                            lv = estimate_leave(est, power, follow=spin_follow,
                                                side=spin_side)
                            rs = w2s(lv["rest"])
                            rest_spr = ball_sprite("cue", gr).copy()
                            rest_spr.set_alpha(52)
                            ov.blit(rest_spr, (rs[0] - rest_spr.get_width() // 2,
                                               rs[1] - rest_spr.get_height() // 2))
                            pygame.draw.circle(ov, (150, 200, 255, 120), rs, gr,
                                               max(1, int(RSF)))

                    screen.blit(ov, (0, 0))
                    aim_txt = (f"pot {prob*100:3.0f}%  cut {pa['angle_deg']:4.1f}deg"
                               if pa else
                               f"contact {gb['fullness']*100:3.0f}% full")
                else:
                    cpath = one_bounce_path(tuple(cue.position), dxy, ball_r())
                    for a, b in zip(cpath, cpath[1:]):
                        pygame.draw.aaline(screen, COL["line"], w2s(a), w2s(b))

        # ---- Increment 4a: spectator motion trails. HUD-only-state
        # doctrine doesn't apply here (this is scene content, not a shot
        # param) but the byte-identical HEADLESS doctrine does: trails are
        # real per-frame visual state, so -- same lesson as the R6.5
        # near-miss -- this whole block is gated behind `not smoke`, never
        # touching what --snap/--smoke render.
        if not smoke:
            trail_history = {bid: h for bid, h in trail_history.items() if bid in sim.balls}
            for bid, (body, shape) in sim.balls.items():
                if body.velocity.length > CFG["STOP_SPEED"]:
                    hist = trail_history.setdefault(bid, [])
                    hist.append(tuple(body.position))
                    del hist[:-CFG["TRAIL_LEN"]]
                else:
                    trail_history.pop(bid, None)
            for bid, hist in trail_history.items():
                n = len(hist)
                if n < 2:
                    continue
                _, shape = sim.balls[bid]
                kind = sim.colours.get(bid, "red")
                _, light = ball_shades.get(kind, ball_shades["red"])
                r_px = max(2, int(shape.radius * S))
                prev = None
                for i, pos in enumerate(hist):          # oldest (i=0) .. newest
                    age_idx = (n - 1) - i                # 0 = newest, n-1 = oldest
                    frac_r, fade_t = trail_dot_style(age_idx, n)
                    col = lerp3(light, COL["baize"], fade_t)
                    p = w2s(pos)
                    if prev is not None:
                        pygame.draw.line(screen, col, prev, p,
                                          max(1, int(r_px * frac_r * 0.5)))
                    pygame.draw.circle(screen, col, p, max(1, int(r_px * frac_r * 0.6)))
                    prev = p

        # ---- Increment 4b: pot swallow animation + cup-glow. Same
        # byte-identical-headless doctrine as 4a: this whole block (both the
        # animation state AND its draw) is gated behind `not smoke`, so
        # --snap/--smoke are provably untouched. Physics/rules are NOT
        # gated by this -- a captured ball is genuinely gone from
        # sim.balls/potted_log the instant it's captured, whether or not
        # anyone is watching; this block only decides how the last few
        # frames of that ball's ON-SCREEN life look, driven by
        # sim.last_pot_events (a pure event report, never read by
        # physics/rules/AI).
        if not smoke:
            for kind, strength in sim.last_hit_events:
                # arbiter.total_impulse is a physics impulse (kg*m/s in
                # these real WEPF units), not a 0..1 fraction. r8: the raw
                # impulse now drives BOTH loudness and timbre -- play_impact
                # picks a brighter/shorter pre-rendered tier for harder hits
                # (impact_hardness -> impact_tier) and sets the volume from
                # the same number (scale_ball_hit_volume).
                play_impact(strength)
            for bid, kind, pos, radius in sim.last_pot_events:
                play_sound("pot", 1.0)
            pockets_m = [((p["centre"][0] / 1000.0, p["centre"][1] / 1000.0),
                          p["r"] / 1000.0) for p in cushion_geo.pocket_geometry()]
            for bid, kind, pos, radius in sim.last_pot_events:
                target, cup_r_m = min(pockets_m, key=lambda pc: math.dist(pc[0], pos))
                pot_anims.append({"kind": kind, "start": pos, "target": target,
                                   "cup_r_m": cup_r_m, "r_m": radius,
                                   "start_frame": frames})
                if kind == "black":
                    last_black_cup = target
            pot_anims[:] = [a for a in pot_anims
                            if frames - a["start_frame"] < CFG["SWALLOW_FRAMES"]]
            for a in pot_anims:
                t = swallow_progress(frames - a["start_frame"], CFG["SWALLOW_FRAMES"])
                sx, sy = a["start"]
                tx, ty = a["target"]
                pos_now = (sx + (tx - sx) * t, sy + (ty - sy) * t)
                glow_t = 1.0 - t
                if glow_t > 0.0:
                    gcol = lerp3(cushion_geo.COL_HOLE, (255, 225, 160), glow_t)
                    grad_r = max(2, int(a["cup_r_m"] * S))
                    pygame.draw.circle(screen, gcol, w2s(a["target"]), grad_r)
                if t < 1.0:
                    kind = a["kind"]
                    _, light = ball_shades.get(kind, ball_shades["red"])
                    col = lerp3(light, cushion_geo.COL_HOLE, t)
                    r = max(1, int(a["r_m"] * S * (1.0 - t)))
                    pygame.draw.circle(screen, col, w2s(pos_now), r)

        # ---- Increment 4c: slow-mo black finale. Fires once, when a
        # black-pot win/loss RESOLVES (game.over's False->True transition
        # is detected up in the game-logic block, which sets `finale`). A
        # pure cosmetic overlay on top of an already-settled table (on_rest
        # only runs once sim.all_at_rest(), so there's no real motion left
        # to slow -- a held, faded pause reads as dramatic without risking
        # any interaction with 4b's own frame-counted swallow timer).
        # Painted LAST, over everything this frame including the HUD icon
        # further up, so the fade genuinely covers the whole scene; the
        # black's own cup is excluded from the darkening so it stays lit
        # throughout, per the sign-off. Same `not smoke` doctrine as
        # 4a/4b -- --snap/--smoke never see this.
        if not smoke and finale is not None:
            age = frames - finale["start_frame"]
            fade = finale_fade(age, CFG["FINALE_FRAMES"])
            if fade > 0.0:
                darken = pygame.Surface((W, H))
                darken.fill((0, 0, 0))
                darken.set_alpha(int(200 * fade))
                screen.blit(darken, (0, 0))
                cup = finale["cup"]
                if cup is not None:
                    glow_r = max(3, int(0.05 * S * (1.0 + fade)))
                    gcol = lerp3((40, 40, 44), (255, 235, 190), fade)
                    pygame.draw.circle(screen, gcol, w2s(cup), glow_r)
            elif age >= CFG["FINALE_FRAMES"]:
                finale = None

        for bid, (body, shape) in sim.balls.items():
            draw_ball(sim.colours.get(bid, "red"), w2s(body.position),
                      max(2, int(shape.radius * S)))

        # ---- Colour-grade. Always-on like the vignette, user-switchable
        # (Table tab TabStrip: Warm/Cool/Contrast, no "off" state) rather
        # than a fixed choice. Same `not smoke` doctrine and same render-
        # only-overlay pattern as 4a-4d -- R6.1's --snap baseline is
        # untouched, this never touches cushion_path.py's actual table
        # art. Drawn BEFORE 4d's vignette (this grades the base image;
        # vignette then darkens the already-graded frame on top of it).
        if not smoke:
            label, gcol, blend, strength = grade_params(grade_idx)
            key = (label, W, H)
            gsurf = grade_surface_cache.get(key)
            if gsurf is None:
                grade_surface_cache.clear()
                gsurf = pygame.Surface((W, H))
                gsurf.fill(gcol)
                if blend == "normal":
                    gsurf.set_alpha(strength)
                grade_surface_cache[key] = gsurf
            if blend == "mult":
                screen.blit(gsurf, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            else:
                screen.blit(gsurf, (0, 0))

        # ---- Increment 4d: vignette. Always-on ambient darkening toward
        # the frame edges -- unlike 4a/4b/4c this has no trigger and no
        # per-frame state at all, just a static radial darken redrawn every
        # frame. Same `not smoke` doctrine: a pure render-only overlay, so
        # --snap/--smoke keep showing the flat, ungraded R6.1 baize exactly
        # as before -- the R6.1 byte-identical baseline is deliberately
        # left untouched (per the brief, this does NOT touch
        # cushion_path.py's actual table art). Drawn after the balls but
        # BEFORE 4c's finale layer, so a black-pot finale still fully
        # dominates over an already-vignetted table, and before the HUD
        # text below so the bottom readout stays legible.
        if not smoke:
            vig = vignette_surface_cache.get((W, H))
            if vig is None:
                vig = pygame.Surface((W, H), pygame.SRCALPHA)
                cx, cy = W / 2.0, H / 2.0
                maxd = math.hypot(cx, cy)
                step = max(1, int(min(W, H) / 120))
                for yy in range(0, int(H), step):
                    for xx in range(0, int(W), step):
                        d = math.hypot(xx - cx, yy - cy) / maxd
                        a = vignette_alpha(d)
                        if a > 0:
                            pygame.draw.rect(vig, (0, 0, 0, a),
                                              (xx, yy, step, step))
                vignette_surface_cache.clear()
                vignette_surface_cache[(W, H)] = vig
            screen.blit(vig, (0, 0))

        # r11: the physics/game readout that used to sit at the BOTTOM OF THE
        # TABLE now lives in the persistent panel strip (see draw of
        # STATUS_STRIP_H below). It is NOT drawn over the baize any more --
        # which is why the --snap baseline changed with this pass, deliberately
        # and with sign-off. Only the aim icon remains on the frame.
        cue_lbl = "1-7/8\" 94g" if CFG["CUE_R_M"] < 0.025 else "2\" 116g"
        status_fields = [
            f"power {power:4.2f} m/s",
            f"cushion e {CFG['CUSHION_ELASTICITY']:.2f}",
            f"roll {CFG['ROLL_DECEL']:.3f} m/s2",
            f"ball {CFG['BALL_R_M']*2000:.1f}mm",
            f"cue {cue_lbl}",
            f"spin s{spin_side:+.2f} f{spin_follow:+.2f}",
        ]
        if game is not None:
            def ptxt(i):
                col = game.colours.get(i)
                left = f" {sim.remaining(col)} left" if col else ""
                mark = ">" if (game.current == i and not game.over) else " "
                return f"{mark}{game.names[i]}[{(col or 'open').upper()}{left}]"
            status_lines2 = [MODES[mode], f"{ptxt(0)} vs {ptxt(1)}",
                             game.last_event]
            if game.ball_in_hand:
                status_lines2.append("BALL IN HAND — drag cue in baulk")
            if game.over:
                status_lines2.append("T = new game")
        else:
            status_lines2 = [
                f"balls {len(sim.balls)}  potted {len(sim.potted_log)}"
                f" [{','.join(sim.potted_colours()) or '-'}]"
            ]
            if aim_txt:
                status_lines2.append(aim_txt)
        # r12: the spin-position icon is GONE from the frame (Maker's call --
        # spin already has the SpinPad and the numeric readout in the panel, so
        # a third copy of it painted on the woodwork was pure duplication).
        # hud_icon_x() and its selftest are kept: the helper is pure and correct,
        # it simply has no caller now.
        #
        # The freed strip becomes the POTTED-BALL CHAMBER: on a real table the
        # potted balls run down into a glass-fronted chamber, and you can read
        # off exactly what went down and in what ORDER. That's what this shows.
        # No animation, by request -- it's a static readout of potted_log, which
        # is already ordered.
        #
        # Render-only, gated `not smoke`: this follows the standing overlay
        # doctrine and keeps --snap byte-identical to the r11 baseline. It also
        # avoids a subtler trap -- what's in the chamber depends on how the AI's
        # break happened to run, so drawing it in --snap could make the baseline
        # itself non-deterministic.
        if not smoke:
            # r13: transient baulk highlight, shown ONLY while a human actually
            # has ball in hand -- it is not a permanent table marking (Maker
            # asked for the baize to be left as it is), and being `not smoke`
            # gated it never touches the --snap baseline. Without it the player
            # has no way to see where placement is legal.
            if (game is not None and game.ball_in_hand
                    and game.controllers[game.current] == "you"
                    and sim.all_at_rest()):
                bx0, by0, bx1, by1 = baulk_rect()
                tl = w2s((bx0, by0))
                br = w2s((bx1, by1))
                zone = pygame.Surface((abs(br[0] - tl[0]), abs(br[1] - tl[1])),
                                      pygame.SRCALPHA)
                zone.fill((255, 255, 255, 26))
                screen.blit(zone, (min(tl[0], br[0]), min(tl[1], br[1])))

            # r22: potted_colours_ALL (game-scoped), not potted_colours
            # (shot-scoped, wiped by strike()). Reading the shot-scoped list was
            # the "chamber only shows one ball then it disappears" bug -- it was
            # never accumulating.
            potted = [c for c in sim.potted_colours_all() if c != "cue"]
            # The cue is deliberately excluded: a scratched cue ball is returned
            # to play, it does not stay in the chamber. Same as a real table.
            ch_h = int(30 * RSF)
            ch_y = int(H - 40 * RSF)
            ch_x = M
            ch_w = (W - M) - M
            # the glass front: a dark recess with a faint highlight along the top
            glass = pygame.Surface((ch_w, ch_h), pygame.SRCALPHA)
            glass.fill((14, 14, 16, 165))
            pygame.draw.line(glass, (150, 158, 170, 60), (0, 0), (ch_w - 1, 0), 1)
            screen.blit(glass, (ch_x, ch_y))
            if potted:
                pad = int(6 * RSF)
                d, xs = chamber_slots(len(potted), ch_w - 2 * pad,
                                      ch_h - 2 * pad, max(2, int(3 * RSF)))
                r_px = max(1, int(d / 2))
                cy = ch_y + ch_h // 2
                for colour, cx in zip(potted, xs):
                    spr = ball_sprite(colour, r_px)   # same sprite as on the table
                    screen.blit(spr, (int(ch_x + pad + cx) - spr.get_width() // 2,
                                      cy - spr.get_height() // 2))

        shown = present(screen)          # always the same surface now GL is gone
        if smoke:
            # Headless guard: bare scene, R6.1 framing, no panel, no fit.
            display.blit(shown, (0, 0))
        else:
            # Increment 3a/3b: fitted scene centred in the region left of the
            # right-hand panel, which now carries the real hand-rolled tabbed
            # controls (Shot / Table / Game) wired into this rect.
            display.fill((26, 28, 32))
            avail_w = win_w - PANEL_W
            scene_x = max(0, (avail_w - fit_W1) // 2)
            scene_y = max(0, (win_h - fit_H1) // 2)
            display.blit(shown, (scene_x, scene_y))
            panel_rect = pygame.Rect(win_w - PANEL_W, 0, PANEL_W, win_h)
            pygame.draw.rect(display, (42, 45, 51), panel_rect)
            pygame.draw.line(display, (68, 72, 80),
                              (win_w - PANEL_W, 0), (win_w - PANEL_W, win_h), 1)
            panel_widgets["tabstrip"].draw(display, panel_font)
            # r11: the persistent status strip -- drawn on EVERY tab, above the
            # tabstrip. wrap_fields packs it by ACTUAL pixel width (font.size),
            # not character count, so it can't silently overflow the 260px
            # column when a value gets wider (a long game_event, say). Lines
            # beyond the reserved budget are clipped rather than spilling over
            # the tabs below.
            sx = win_w - PANEL_W + 10
            sw = PANEL_W - 20
            measure = lambda s: panel_font.size(s)[0]
            strip_lines = (wrap_fields(status_fields, sw, measure)
                           + wrap_fields(status_lines2, sw, measure))
            line_h = panel_font.get_height() + 1
            sy = 6
            for ln in strip_lines:
                if sy + line_h > STATUS_STRIP_H:
                    break                      # clip; never spill onto the tabs
                display.blit(panel_font.render(ln, True, COL["hud"]), (sx, sy))
                sy += line_h
            pygame.draw.line(display, (68, 72, 80),
                              (win_w - PANEL_W, STATUS_STRIP_H - 3),
                              (win_w - 1, STATUS_STRIP_H - 3), 1)
            for w in panel_widgets[TAB_LABELS[panel_tab]]:
                w.draw(display, panel_font)
        pygame.display.flip()
        last_shown = shown
        clock.tick(CFG["FPS"])
        frames += 1
        if smoke and frames >= smoke_frames:
            running = False

    if snap_path:
        pygame.image.save(last_shown, snap_path)  # save the presented frame
        print(f"snap: saved {snap_path}")
    pygame.quit()
    return frames


# ----------------------------------------------------------------------------
# Pot drill (decision 4A) — calibration gate shared by selftest
# ----------------------------------------------------------------------------
def pot_drill(verbose=False):
    """18 straight pots (decision 4A gate): all six pockets, approached along
    each pocket's throat axis (the 45-degree diagonal for corners — blackball
    corners are designed to reject shallow rail-line approaches), with the
    object line deviating {0, +1, -1} degrees off the pocket centreline from
    0.6 m out at 1.5 m/s. Full-ball contact throughout, so this measures
    pocket acceptance angle, not cut-error amplification. Gate: >= 90%."""
    x0, y0, x1, y1 = play_rect()
    s2 = math.sqrt(2.0) / 2.0
    mx = (x0 + x1) / 2.0
    # (capture point, unit axis INTO the pocket)
    axes = [
        (capture_points()[0][0], (-s2, -s2)), (capture_points()[1][0], (s2, -s2)),
        (capture_points()[2][0], (-s2, s2)), (capture_points()[3][0], (s2, s2)),
        (capture_points()[4][0], (0.0, -1.0)), (capture_points()[5][0], (0.0, 1.0)),
    ]
    results = []
    for (pc, din) in axes:
        base = math.atan2(din[1], din[0])
        for dev_deg in (0.0, 1.0, -1.0):
            ang = base + math.radians(dev_deg)
            dvec = (math.cos(ang), math.sin(ang))
            obj = (pc[0] - dvec[0] * 0.6, pc[1] - dvec[1] * 0.6)
            cue0 = (pc[0] - dvec[0] * 0.9, pc[1] - dvec[1] * 0.9)
            sim = Sim(layout="empty")
            sim._add_ball(sim.CUE_ID, cue0, "cue")
            oid = sim._add_ball(sim.alloc_id(), obj, "red")
            c = sim.cue()
            sim.strike((obj[0] - c.position.x, obj[1] - c.position.y), 1.5)
            sim.run_to_rest(timeout_s=25.0)
            ok = oid in sim.potted_log
            results.append(ok)
            if verbose:
                print(f"  pocket {pc[0]:.2f},{pc[1]:.2f} dev {dev_deg:+.0f} deg: "
                      f"{'POT' if ok else 'miss'}")
    return sum(results), len(results)


# ----------------------------------------------------------------------------
# Break analyser (decision 2A)
# ----------------------------------------------------------------------------
def cue_centre_dist(sim):
    """Cue-ball control metric (R5, decision C2): distance of the cue ball
    from the table centre at rest, or None if the break scratched."""
    cue = sim.cue()
    if cue is None or "cue" in sim.potted_colours():
        return None
    x0, y0, x1, y1 = play_rect()
    return math.dist(tuple(cue.position), ((x0 + x1) / 2, (y0 + y1) / 2))


def _one_break(power, aim_off, side, follow, rng=None):
    """Fresh rack, parameterised break, run to rest. Returns the sim."""
    sim = Sim(layout="empty")
    x0, y0, x1, y1 = play_rect()
    sim._add_ball(sim.CUE_ID,
                  (x0 + (x1 - x0) * CFG["BAULK_FRAC"], (y0 + y1) / 2), "cue")
    sim.rack()
    p_jit = rng.gauss(1.0, 0.02) if rng else 1.0
    a_jit = rng.gauss(0.0, 0.0015) if rng else 0.0
    sim.break_shot(power=power * p_jit, aim_off=aim_off + a_jit,
                   side=side, follow=follow)
    sim.run_to_rest()
    return sim


def break_analysis(trials_per_config=8, seed=1234):
    """Two-phase sweep with seeded human-error jitter (R5, decision C2).
    Phase 1 — the R3 aim-offset x power grid, unchanged for comparability
    with the §6.4 finding, now also reporting cue-ball control (ctl = mean
    cue distance from table centre; a scratch counts as 1.0 m).
    Phase 2 — spin sweep at 7 m/s over the smash (0 mm) and folk-wisdom
    (one ball radius) aims: follow/draw x side, same metrics. This is the
    sweep that can adjudicate whether cutting the second ball buys cue-ball
    control rather than pots. Fair break (blackball): pot a ball OR >= 2
    object balls cross halfway (approximated by final position — noted,
    not hidden)."""
    r = ball_r()
    rng = random.Random(seed)
    x0, y0, x1, y1 = play_rect()
    half_x = (x0 + x1) / 2
    n = trials_per_config

    def run_config(power, aim_off, side, follow):
        pots_total, scratches, blacks, fairs = 0, 0, 0, 0
        spreads, ctls = [], []
        for _ in range(n):
            sim = _one_break(power, aim_off, side, follow, rng)
            potted = sim.potted_colours()
            obj_pots = sum(1 for c in potted if c in ("red", "yellow"))
            pots_total += obj_pots
            if "cue" in potted:
                scratches += 1
            if "black" in potted:
                blacks += 1
            cd = cue_centre_dist(sim)
            ctls.append(cd if cd is not None else 1.0)   # scratch penalty
            pos = sim.object_positions()
            crossed = sum(1 for p in pos if p[0] < half_x)
            if obj_pots > 0 or crossed >= 2:
                fairs += 1
            if pos:
                cx = sum(p[0] for p in pos) / len(pos)
                cy = sum(p[1] for p in pos) / len(pos)
                spreads.append(sum(math.dist(p, (cx, cy)) for p in pos) / len(pos))
        return {"pots": pots_total / n, "scr": scratches / n,
                "blk": blacks / n, "fair": fairs / n,
                "spread": sum(spreads) / max(1, len(spreads)),
                "ctl": sum(ctls) / max(1, len(ctls))}

    print(f"HUSTLER break analyser — {n} trials/config, seed {seed}")
    print(f"  jitter: aim sigma 1.5 mm at pack, power sigma 2%")
    print(f"\n  Phase 1 — aim offset x power (no spin), R3-comparable grid")
    header = (f"  {'off(mm)':>8} {'pow':>5} | {'pots':>5} {'scr%':>5} "
              f"{'blk%':>5} {'fair%':>6} {'spread':>7} {'ctl(m)':>7}")
    print(header)
    print("  " + "-" * (len(header) - 2))
    best = None
    for aim_off in [0.0, 0.5 * r, 1.0 * r]:
        for power in [4.0, 5.5, 7.0]:
            s = run_config(power, aim_off, 0.0, 0.0)
            print(f"  {aim_off*1000:8.1f} {power:5.1f} | {s['pots']:5.2f} "
                  f"{100*s['scr']:5.0f} {100*s['blk']:5.0f} "
                  f"{100*s['fair']:6.0f} {s['spread']:6.3f}m {s['ctl']:6.3f}m")
            score = s["pots"] - 0.5 * s["scr"] - 0.5 * s["blk"]
            if best is None or score > best[0]:
                best = (score, aim_off, power, s["pots"], s["fair"])
    print(f"  best pots: aim offset {best[1]*1000:.1f} mm, power {best[2]:.1f} m/s "
          f"({best[3]:.2f} pots/break, {best[4]*100:.0f}% fair)")

    print(f"\n  Phase 2 — spin sweep at 7.0 m/s (follow +ve / draw -ve)")
    header2 = (f"  {'off(mm)':>8} {'flw':>5} {'side':>5} | {'pots':>5} "
               f"{'scr%':>5} {'fair%':>6} {'ctl(m)':>7}")
    print(header2)
    print("  " + "-" * (len(header2) - 2))
    best_ctl = None
    for aim_off in [0.0, 1.0 * r]:
        for follow in [-0.7, 0.0, 0.7]:
            for side in [0.0, 0.5]:
                s = run_config(7.0, aim_off, side, follow)
                print(f"  {aim_off*1000:8.1f} {follow:5.1f} {side:5.1f} | "
                      f"{s['pots']:5.2f} {100*s['scr']:5.0f} "
                      f"{100*s['fair']:6.0f} {s['ctl']:6.3f}m")
                if best_ctl is None or s["ctl"] < best_ctl[0]:
                    best_ctl = (s["ctl"], aim_off, follow, side, s["pots"])
    print(f"  best control: aim offset {best_ctl[1]*1000:.1f} mm, "
          f"follow {best_ctl[2]:+.1f}, side {best_ctl[3]:.1f} "
          f"(ctl {best_ctl[0]:.3f} m, {best_ctl[4]:.2f} pots/break)")
    return True


# ----------------------------------------------------------------------------
# Validation — selftest (one assertion block per feature) and batch
# ----------------------------------------------------------------------------
def selftest():
    print("HUSTLER selftest (R5 — positional leave + spin break sweep)")
    failures = 0

    def check(name, cond, detail=""):
        nonlocal failures
        status = "PASS" if cond else "FAIL"
        if not cond:
            failures += 1
        print(f"  [{status}] {name}" + (f"  ({detail})" if detail else ""))

    # 1. Geometry: straight ghost ball (unit-agnostic pure maths)
    gb = ghost_ball((0, 0), (1, 0), [(100, 0)], 10, 10)
    check("ghost ball — straight pot geometry",
          gb is not None and abs(gb["ghost"][0] - 80.0) < 1e-6
          and abs(gb["obj_dir"][0] - 1.0) < 1e-6 and gb["fullness"] > 0.999)

    # 2. Geometry: angled cut on line of centres, tangent perpendicular
    gb = ghost_ball((0, 0), (1, 0), [(100, 12)], 10, 10)
    ok = gb is not None
    if ok:
        gx, gy = gb["ghost"]
        lx, ly = vnorm(100 - gx, 12 - gy)
        ok = (abs(lx - gb["obj_dir"][0]) < 1e-9 and abs(ly - gb["obj_dir"][1]) < 1e-9
              and 0.0 < gb["fullness"] < 1.0
              and abs(gb["cue_dir"][0] * lx + gb["cue_dir"][1] * ly) < 1e-9)
    check("ghost ball — angled cut: object on line of centres, cue on tangent", ok)

    # 3. Cloth: constant deceleration — 1 m/s stops in ~v/a seconds
    sim = Sim(layout="empty")
    x0, y0, x1, y1 = play_rect()
    sim._add_ball(sim.CUE_ID, ((x0 + x1) / 2 - 0.5, (y0 + y1) / 2), "cue")
    sim.cue().velocity = (1.0, 0.0)
    t = sim.run_to_rest(timeout_s=15.0)
    expect_t = 1.0 / CFG["ROLL_DECEL"]
    check("cloth — constant-deceleration roll, stop time near v/a",
          sim.all_at_rest() and abs(t - expect_t) < 1.5,
          f"stopped in {t:.1f}s, v/a predicts {expect_t:.1f}s")

    # 4. Cushion: rebound with plausible effective restitution
    sim = Sim(layout="empty")
    sim._add_ball(sim.CUE_ID, (x0 + (x1 - x0) * 0.30, (y0 + y1) / 2), "cue")
    cue = sim.cue()
    v0 = 1.5
    cue.velocity = (0.0, -v0)
    e_eff = None
    for _ in range(600):
        sim.step(1 / 120.0)
        if cue.velocity.y > 0:
            e_eff = cue.velocity.length / v0
            break
    check("cushion — rebound within measured rail range (0.6-0.9 less roll)",
          e_eff is not None and 0.5 < e_eff < 0.95, f"effective e={e_eff}")

    # 5. Collision: WEPF light cue transfers most speed, slight rebound
    sim = Sim(layout="empty")
    sim._add_ball(sim.CUE_ID, ((x0 + x1) / 2 - 0.25, (y0 + y1) / 2), "cue")
    oid = sim._add_ball(sim.alloc_id(), ((x0 + x1) / 2 + 0.15, (y0 + y1) / 2), "red")
    obj = sim.balls[oid][0]
    sim.strike((1.0, 0.0), 2.0)
    for _ in range(240):
        sim.step(1 / 120.0)
        if obj.velocity.length > 0.01:
            break
    check("collision — 94g cue on 116g ball: high transfer",
          obj.velocity.length > 0.6 * 2.0
          and abs(sim.cue().velocity.length) < 0.4 * obj.velocity.length,
          f"obj {obj.velocity.length:.2f} m/s, cue {sim.cue().velocity.length:.2f} m/s")

    # 6. Pocket capture at a corner (cue respotted to baulk)
    sim = Sim(layout="empty")
    (pc0, cr0) = capture_points()[0]
    sim._add_ball(sim.CUE_ID, (pc0[0] + 0.3, pc0[1] + 0.3), "cue")
    d = vnorm(pc0[0] - sim.cue().position.x, pc0[1] - sim.cue().position.y)
    sim.cue().velocity = (d[0] * 1.5, d[1] * 1.5)
    sim.run_to_rest(timeout_s=15.0)
    check("pocket — corner throat captures (cue respotted)",
          Sim.CUE_ID in sim.potted_log, f"potted {sim.potted_colours()}")

    # 7. Containment across random max-power strikes
    rng = random.Random(42)
    escapes = 0
    for _ in range(10):
        sim = Sim()
        for _n in range(3):
            sim.add_random_ball(rng)
        ang = rng.uniform(0, 2 * math.pi)
        sim.strike((math.cos(ang), math.sin(ang)), rng.uniform(3.0, CFG["POWER_MAX"]))
        sim.run_to_rest()
        if not sim.in_bounds():
            escapes += 1
    check("containment — 10 random max-power strikes, zero escapes",
          escapes == 0, f"escapes={escapes}")

    # 8. Spin: side spin alters cushion rebound
    def cushion_rebound_vx(side):
        s = Sim(layout="empty")
        s._add_ball(s.CUE_ID, (x0 + (x1 - x0) * 0.30, (y0 + y1) / 2), "cue")
        s.strike((0.0, -1.0), 1.5, side=side)
        c = s.cue()
        for _ in range(600):
            s.step(1 / 120.0)
            if c.velocity.y > 0:
                return c.velocity.x
        return None
    vx_no, vx_side = cushion_rebound_vx(0.0), cushion_rebound_vx(1.0)
    check("spin — side spin alters cushion rebound angle",
          vx_no is not None and vx_side is not None and abs(vx_side - vx_no) > 0.15,
          f"rebound vx: no spin {vx_no:.2f}, full side {vx_side:.2f} m/s")

    # 9. Spin: draw reverses, follow carries through (measured just after contact)
    def head_on_cue_vx(follow):
        s = Sim(layout="empty")
        s._add_ball(s.CUE_ID, ((x0 + x1) / 2 - 0.25, (y0 + y1) / 2), "cue")
        oid2 = s.alloc_id()
        s._add_ball(oid2, ((x0 + x1) / 2 + 0.15, (y0 + y1) / 2), "red")
        ob = s.balls[oid2][0]
        s.strike((1.0, 0.0), 2.0, follow=follow)
        for _ in range(240):
            s.step(1 / 120.0)
            if ob.velocity.length > 0.01:
                for _ in range(15):
                    s.step(1 / 120.0)
                return s.cue().velocity.x
        return 0.0
    vx_draw, vx_follow = head_on_cue_vx(-1.0), head_on_cue_vx(1.0)
    check("spin — draw reverses the cue ball, follow carries it through",
          vx_draw < -0.1 and vx_follow > 0.1,
          f"draw {vx_draw:.2f}, follow {vx_follow:.2f} m/s")

    # 10. Jaws: grazing shot across the middle mouth stays up
    sim = Sim(layout="empty")
    r = ball_r()
    sim._add_ball(sim.CUE_ID, ((x0 + x1) / 2 - 0.5, y0 + r + 0.015), "cue")
    sim.cue().velocity = (1.0, 0.0)
    for _ in range(110):
        sim.step(1 / 120.0)
    crossed = sim.cue().position.x > (x0 + x1) / 2 + 0.05
    check("jaws — grazing shot across the middle pocket mouth stays up",
          crossed and Sim.CUE_ID in sim.balls and Sim.CUE_ID not in sim.potted_log,
          f"crossed={crossed}, potted {sim.potted_colours()}")

    # 11. Cue mass: WEPF light cue rebounds; casual equal cue barely does
    def rebound_after_headon():
        s = Sim(layout="empty")
        s._add_ball(s.CUE_ID, ((x0 + x1) / 2 - 0.25, (y0 + y1) / 2), "cue")
        oid3 = s.alloc_id()
        s._add_ball(oid3, ((x0 + x1) / 2 + 0.15, (y0 + y1) / 2), "red")
        ob = s.balls[oid3][0]
        s.strike((1.0, 0.0), 2.0)
        for _ in range(240):
            s.step(1 / 120.0)
            if ob.velocity.length > 0.01:
                for _ in range(10):
                    s.step(1 / 120.0)
                return s.cue().velocity.x
        return None
    rb_light = rebound_after_headon()
    # flip to casual full-size cue and repeat
    CFG["CUE_R_M"], CFG["CUE_MASS_KG"] = CFG["CUE_CASUAL_R_M"], CFG["CUE_CASUAL_MASS_KG"]
    rb_equal = rebound_after_headon()
    CFG["CUE_R_M"], CFG["CUE_MASS_KG"] = 0.0238, 0.094
    check("cue mass — 94g cue rebounds off 116g ball; equal masses do not",
          rb_light is not None and rb_equal is not None
          and rb_light < -0.02 and rb_equal > rb_light + 0.02,
          f"light {rb_light:.3f}, equal {rb_equal:.3f} m/s")

    # 12. Assessor geometry: aligned pot high, 30 degrees off near zero
    (pcA, _crA) = capture_points()[0]
    tgt = (pcA[0] + 0.5, pcA[1] + 0.5)
    d_perfect = vnorm(pcA[0] - tgt[0], pcA[1] - tgt[1])
    a = math.atan2(d_perfect[1], d_perfect[0]) + math.radians(30)
    pa_p = pot_assessment({"target": tgt, "obj_dir": d_perfect, "fullness": 0.9, "t": 0.3})
    pa_o = pot_assessment({"target": tgt, "obj_dir": (math.cos(a), math.sin(a)),
                           "fullness": 0.9, "t": 0.3})
    check("assessor — aligned pot scores high, 30 deg off scores near zero",
          pa_p and pa_o and pa_p["prob"] > 0.5 and pa_o["prob"] < 0.1
          and pa_p["angle_deg"] < 0.5,
          f"aligned {pa_p['prob']:.2f}, off {pa_o['prob']:.2f}")

    # 13. Rack: 15 balls, correct colours, no overlaps, black on the spot
    sim = Sim(layout="empty")
    sim._add_ball(sim.CUE_ID, (0.3, 0.455), "cue")
    ids = sim.rack()
    cols = [sim.colours[i] for i in ids]
    pos = [tuple(sim.balls[i][0].position) for i in ids]
    min_gap = min(math.dist(a, b) for i, a in enumerate(pos) for b in pos[i + 1:])
    bp = tuple(sim.balls[sim.black_id][0].position)
    spot = (x0 + (x1 - x0) * 0.75, (y0 + y1) / 2)
    check("rack — 7 red, 7 yellow, black on the spot, no overlaps",
          len(ids) == 15 and cols.count("red") == 7 and cols.count("yellow") == 7
          and cols.count("black") == 1 and min_gap > 2 * ball_r() * 0.999
          and math.dist(bp, spot) < 0.001,
          f"min gap {min_gap*1000:.1f}mm, black at {bp[0]:.3f},{bp[1]:.3f}")

    # 14. Break: scripted 6 m/s break scatters the pack and is 'fair'
    sim = Sim(layout="empty")
    sim._add_ball(sim.CUE_ID, (0.3, 0.455), "cue")
    sim.rack()
    pre = sim.object_positions()
    pre_c = (sum(p[0] for p in pre) / len(pre), sum(p[1] for p in pre) / len(pre))
    pre_spread = sum(math.dist(p, pre_c) for p in pre) / len(pre)
    sim.break_shot(power=6.0)
    sim.run_to_rest()
    pos = sim.object_positions()
    c = (sum(p[0] for p in pos) / len(pos), sum(p[1] for p in pos) / len(pos))
    spread = sum(math.dist(p, c) for p in pos) / len(pos)
    obj_pots = sum(1 for cc in sim.potted_colours() if cc in ("red", "yellow"))
    crossed = sum(1 for p in pos if p[0] < (x0 + x1) / 2)
    check("break — 6 m/s break scatters pack and satisfies fair-break",
          spread > pre_spread * 2.0 and (obj_pots > 0 or crossed >= 2)
          and sim.in_bounds(),
          f"spread {pre_spread:.3f}->{spread:.3f}m, pots {obj_pots}, crossed {crossed}")

    # 15. Pot drill gate (decision 4A): >= 90% of 18 straight pots drop
    got, total = pot_drill()
    check("drill — straight pots from 0.6m succeed at >= 90% (jaw calibration)",
          got / total >= 0.90, f"{got}/{total} potted")

    # 16. Reflection geometry for one-bounce prediction
    path = one_bounce_path((0.5, 0.5), (0.0, -1.0), 0.0254, tail=0.2)
    ok = (len(path) == 3 and abs(path[1][1] - 0.0254) < 1e-9
          and abs(path[2][1] - (0.0254 + 0.2)) < 1e-9 and abs(path[2][0] - 0.5) < 1e-9)
    check("prediction — one-bounce reflection off the top cushion", ok,
          f"path {[(round(p[0],3), round(p[1],3)) for p in path]}")

    # 17. Rules: open-table assignment and visit continuation
    simg, g = new_game()
    simg.potted_log = [next(b for b in simg.balls
                            if simg.colours.get(b) == "red")]
    simg.balls.pop(simg.potted_log[0])
    g.on_rest(simg)
    ok = (g.colours.get(0) == "red" and g.colours.get(1) == "yellow"
          and g.current == 0 and not g.over)
    simg.potted_log = []
    g.on_rest(simg)     # dry visit: turn must pass
    ok = ok and g.current == 1
    check("rules — first pot assigns colours; striker continues; dry visit passes",
          ok, f"colours {g.colours}, now player {g.current}")

    # 18. Rules: black early = loss; black after clearance = win
    def black_game(clear_own_first):
        s = Sim(layout="empty")
        s._respot_cue()
        (pc, _cr) = capture_points()[3]           # a far corner
        din = (math.sqrt(2) / 2, math.sqrt(2) / 2)
        bpos = (pc[0] - din[0] * 0.5, pc[1] - din[1] * 0.5)
        bid = s._add_ball(s.alloc_id(), bpos, "black")
        gg = Game()
        gg.colours = {0: "red", 1: "yellow"}
        if not clear_own_first:
            s._add_ball(s.alloc_id(), (0.5, 0.2), "red")   # own ball remains
        c = s.cue()
        c.position = (bpos[0] - din[0] * 0.3, bpos[1] - din[1] * 0.3)
        s.strike((bpos[0] - c.position.x, bpos[1] - c.position.y), 1.6)
        s.run_to_rest(timeout_s=25.0)
        gg.on_rest(s)
        return gg
    g_win = black_game(clear_own_first=True)
    g_loss = black_game(clear_own_first=False)
    check("rules — black after clearance wins; black early loses",
          g_win.over and g_win.winner == 0
          and g_loss.over and g_loss.winner == 1,
          f"clean: {g_win.reason} -> P{g_win.winner}; early: {g_loss.reason} -> P{g_loss.winner}")

    # 19. AI: sees and selects the obvious pot
    s = Sim(layout="empty")
    s._respot_cue()
    (pcA2, _c) = capture_points()[0]
    din = (-math.sqrt(2) / 2, -math.sqrt(2) / 2)
    tpos = (pcA2[0] - din[0] * 0.35, pcA2[1] - din[1] * 0.35)
    s._add_ball(s.alloc_id(), tpos, "red")
    s.cue().position = (pcA2[0] - din[0] * 0.75, pcA2[1] - din[1] * 0.75)
    ai = PoolAI("TEST", aim_jitter=0.0, threshold=0.05, rng=random.Random(7))
    shot = ai.choose(s, ["red"])
    ok = (shot is not None and shot["type"] == "pot" and shot["p"] > 0.5
          and shot["pocket"] == pcA2)
    check("AI — selects the aligned corner pot with high confidence",
          ok, f"type {shot['type'] if shot else None}, p {shot['p'] if shot else 0:.2f}")

    # 20. AI: the chosen shot actually pots the ball (zero jitter)
    s.strike(shot["aim"], shot["power"])
    s.run_to_rest(timeout_s=25.0)
    check("AI — executes the chosen pot successfully",
          "red" in s.potted_colours() and "cue" not in s.potted_colours(),
          f"potted {s.potted_colours()}")

    # 21. AI vs AI: a full seeded game reaches a legitimate result
    rec = play_ai_game(seed=99)
    check("AI vs AI — full headless game completes with a winner",
          rec["over"] and rec["winner"] in (0, 1) and rec["shots"] < 300,
          f"{rec['winner_name']} in {rec['shots']} shots / {rec['visits']} visits "
          f"({rec['reason']}), {rec['safeties']} safeties, {rec['fouls']} fouls")

    # 22. AI leave term (R5, A3): greed flips a near-equal choice toward the
    # pot with the better estimated leave; greed=0 reproduces pot-chance-only.
    # Frozen position: P2 is the marginally surer pot, P1 leaves far better.
    # r16: re-frozen closer to the cue with a realistic (SHARK-level) jitter --
    # the original positions/jitter=0.02 were implicitly tuned against the
    # pre-r16 pot_estimate and both read as ~0% under the corrected lever-arm
    # model, leaving greed nothing to trade off. Same intent, new numbers.
    s = Sim(layout="empty")
    s._add_ball(s.CUE_ID, (0.91, 0.455), "cue")
    P1, P2 = (0.56, 0.29), (0.84, 0.67)
    TEST_JITTER = 0.008
    s._add_ball(s.alloc_id(), P1, "red")
    s._add_ball(s.alloc_id(), P2, "red")
    def picks(greed):
        ai = PoolAI("T", aim_jitter=TEST_JITTER, threshold=0.05, greed=greed,
                    rng=random.Random(1))
        sh = ai.choose(s, ["red"])
        near = P1 if math.dist(sh["target"], P1) < math.dist(sh["target"], P2) else P2
        return near, sh
    n0, sh0 = picks(0.0)
    n9, sh9 = picks(0.9)
    est_probe = pot_estimate((0.91, 0.455), P1, capture_points()[0][0],
                             capture_points()[0][1], CFG["CUE_R_M"], ball_r(),
                             TEST_JITTER)
    lv_probe = estimate_leave(est_probe, 2.5) if est_probe else None
    in_bounds = (lv_probe is not None
                 and x0 <= lv_probe["rest"][0] <= x1
                 and y0 <= lv_probe["rest"][1] <= y1)
    check("AI leave — greed trades pot certainty for position (R5)",
          n0 == P2 and n9 == P1 and sh9["leave"] > 0.8 and in_bounds,
          f"greed 0 -> P2 (p {sh0['p']:.2f}), greed 0.9 -> P1 "
          f"(p {sh9['p']:.2f}, leave {sh9['leave']:.2f})")

    # 23. Break sweep (R5, C2): draw on the break measurably moves the cue
    # leave, and the control metric reports it. Deterministic (no jitter).
    sA = _one_break(7.0, 0.0, 0.0, 0.0)
    sB = _one_break(7.0, 0.0, 0.0, -0.8)
    dA, dB = cue_centre_dist(sA), cue_centre_dist(sB)
    pa = tuple(sA.cue().position)
    pb = tuple(sB.cue().position)
    moved = math.dist(pa, pb)
    check("break sweep — draw on the break measurably changes the cue leave",
          moved > 0.03 and (dA is None or 0.0 <= dA <= 1.2)
          and (dB is None or 0.0 <= dB <= 1.2),
          f"rest positions {moved*1000:.0f}mm apart, "
          f"ctl {('scratch' if dA is None else f'{dA:.3f}m')} vs "
          f"{('scratch' if dB is None else f'{dB:.3f}m')}")

    # 24. R6 Fork C: the adopted tangent-true cushion loop, driven at this
    # 7ft table and the WEPF 1.6x mouth, is a closed 36-primitive loop that
    # nowhere protrudes into the play area (the zero-escape geometry), and its
    # corner tangent foot coincides with the legacy corner mouth setback
    # (pr*sqrt2) — so the mouths land exactly on the WEPF spec and only the
    # near-pocket wall SHAPE changes (knuckle arcs + jaws vs straight facings).
    MM = 1000.0
    cushion_geo.configure(
        play_w=CFG["PLAY_W_M"] * MM, play_h=CFG["PLAY_H_M"] * MM,
        corner_mouth=CFG["POCKET_MOUTH_M"] * MM,
        middle_mouth=CFG["POCKET_MIDDLE_MOUTH_M"] * MM)
    tpath = cushion_geo.build_cushion_path()
    ok25 = (len(tpath) == 36)
    for _i in range(len(tpath)):
        _, _end = cushion_geo.prim_endpoints(tpath[_i])
        _ns, _ = cushion_geo.prim_endpoints(tpath[(_i + 1) % len(tpath)])
        ok25 = ok25 and cushion_geo._near(_end, _ns)
    Wmm, Hmm, worst_in = CFG["PLAY_W_M"] * MM, CFG["PLAY_H_M"] * MM, 0.0
    for prim in tpath:
        if prim[0] == "line":
            (ax, ay), (bx, by) = prim[1], prim[2]
            samples = [(ax + (bx - ax) * t / 32.0, ay + (by - ay) * t / 32.0)
                       for t in range(33)]
        else:
            _, c, r, a0, a1 = prim
            samples = [cushion_geo.arc_point(c, r, a0 + (a1 - a0) * t / 32.0)
                       for t in range(33)]
        for (sx, sy) in samples:
            if 1e-6 < sx < Wmm - 1e-6 and 1e-6 < sy < Hmm - 1e-6:
                worst_in = max(worst_in, min(sx, Wmm - sx, sy, Hmm - sy))
    ok25 = ok25 and worst_in == 0.0
    pr_mm = (CFG["POCKET_MOUTH_M"] / 2.0) * MM
    foot_err = abs(cushion_geo.S - pr_mm * math.sqrt(2.0))
    ok25 = ok25 and foot_err < 1e-6
    # C1: the widened middle throat (jaw-to-jaw = mouth - 2R) admits the ball
    ball_dia_mm = 2 * ball_r() * MM
    mid_gap = CFG["POCKET_MIDDLE_MOUTH_M"] * MM - 2 * cushion_geo.KNUCKLE_R
    ok25 = ok25 and (mid_gap > ball_dia_mm)
    check("cushions — R6 tangent-true loop adopted (7ft/WEPF): closed, "
          "contained, corner on spec, middle throat clears the ball",
          ok25, f"36 prims, max intrusion {worst_in:.3f}mm, corner-foot "
          f"{foot_err:.1e}mm, mid throat {mid_gap:.1f}>{ball_dia_mm:.1f}mm")

    # 25. Fit-to-region (Graphics Pass 3, Increment 3a) -- dependency-free pure
    #     maths: the largest uniform scale into (window - panel) x window must
    #     preserve the frame's exact aspect (same scale on both axes, so
    #     nothing distorts), must genuinely fit within the reserved region
    #     across several window sizes, and reserves the panel. A floor clamp
    #     (FIT_MIN_SCALE) is allowed to overflow at absurdly small windows
    #     rather than shrink the table to nothing.
    _bw, _bh, _pw = 1000.0, 500.0, 260.0
    _ar = _bw / _bh
    ok26, _bits = True, []
    for (_ww, _wh) in [(1600, 900), (1260, 500), (2400, 1300), (900, 600), (5000, 3000)]:
        _fs, _fw, _fh = fit_to_region(_ww, _wh, _bw, _bh, _pw)
        _aw, _ah = _ww - _pw, _wh
        _raw = min(_aw / _bw, _ah / _bh)
        _exp = max(CFG["FIT_MIN_SCALE"], min(CFG["FIT_MAX_SCALE"], _raw))
        _aspect_ok = abs((_fw / _fh) - _ar) < 1e-6 * _ar
        _fits_ok = (_fw <= _aw + 1 and _fh <= _ah + 1) or _fs > _raw + 1e-9
        ok26 = ok26 and _aspect_ok and _fits_ok and abs(_fs - _exp) < 1e-9
        _bits.append(f"{_ww}x{_wh}->S{_fs:.3f}")
    _fs_tiny, _, _ = fit_to_region(400, 300, _bw, _bh, _pw)
    ok26 = ok26 and _fs_tiny == CFG["FIT_MIN_SCALE"]
    check("fit-to-region — uniform scale preserves aspect, fits the region, "
          "reserves the panel, floor-clamps gracefully (Graphics Pass 3 I3a)",
          ok26, ", ".join(_bits) + f", 400x300->S{_fs_tiny:.2f}(floor)")

    # 26. Slider value<->fraction round-trip (Graphics Pass 3, Increment 3b).
    #     Pure maths shared by every panel slider (power, cue angle, cushion
    #     e, roll decel, ball radius): value -> frac -> value must return the
    #     original (mid-range and at both clamped ends), and out-of-range
    #     inputs clamp to the nearest end rather than extrapolating.
    ok27 = True
    for lo, hi, v in [(0.5, 7.0, 2.0), (-15.0, 15.0, -7.5), (0.05, 1.0, 0.05), (0.05, 1.0, 1.0)]:
        f = slider_frac(v, lo, hi)
        ok27 = ok27 and abs(slider_value(f, lo, hi) - v) < 1e-9
    ok27 = ok27 and slider_frac(999, 0.0, 1.0) == 1.0 and slider_frac(-999, 0.0, 1.0) == 0.0
    check("slider — value<->fraction round-trips, clamps out-of-range "
          "(Graphics Pass 3 I3b)", ok27)

    # 27. Spin pad contact->(follow, side) mapping (Increment 3b). Straight
    #     up/down/left/right must give pure follow/side with no cross-talk;
    #     a diagonal drag past the pad radius must clamp to the UNIT CIRCLE
    #     (magnitude exactly 1), not the square (which would let a corner
    #     drag exceed the physical spin budget).
    f_up, s_up = spin_pad_map(0, -50, 50)      # drag straight up -> full follow
    f_dn, s_dn = spin_pad_map(0, 50, 50)       # drag straight down -> full draw
    f_r, s_r = spin_pad_map(50, 0, 50)         # drag right -> full side, no follow
    f_d, s_d = spin_pad_map(80, 80, 50)        # past the circle, diagonal
    ok28 = (abs(f_up - 1.0) < 1e-9 and abs(s_up) < 1e-9
            and abs(f_dn + 1.0) < 1e-9
            and abs(s_r - 1.0) < 1e-9 and abs(f_r) < 1e-9
            and abs(math.hypot(f_d, s_d) - 1.0) < 1e-9)
    check("spin pad — contact maps to (follow, side), clamped to the unit "
          "circle (Graphics Pass 3 I3b)", ok28,
          f"up=({f_up:.2f},{s_up:.2f}) right=({f_r:.2f},{s_r:.2f}) "
          f"diag-clamped mag={math.hypot(f_d, s_d):.3f}")

    # 28. Shoot-enabled guard (Increment 3b) is a pure mirror of the SPACE
    #     condition (cue present, table at rest, player's turn) -- every
    #     combination must match a direct AND of the three booleans.
    ok29 = all(shoot_enabled(c, r, t) == bool(c and r and t)
               for c in (True, False) for r in (True, False) for t in (True, False))
    check("Shoot button — enabled guard is a pure mirror of the SPACE "
          "condition (Graphics Pass 3 I3b)", ok29)

    # 29. HUD icon anchor (Increment 3b HUD-crowding fix). With plenty of
    #     room the icon stays at its usual right-anchored spot; once the
    #     text's actual width would reach it, the icon is pushed further
    #     right (never left, never smaller) to stay clear, and is clamped
    #     inside the frame rather than running off the edge.
    _default_x, _icon_r, _gap = 780, 18, 10
    _roomy = hud_icon_x(_default_x, 300, _gap, _icon_r, 800)      # short text: unaffected
    _crowded = hud_icon_x(_default_x, 770, _gap, _icon_r, 2000)   # long text, room to move: pushed clear
    _clamped = hud_icon_x(_default_x, 1990, _gap, _icon_r, 2000)  # text reaches the frame edge itself
    ok30 = (_roomy == _default_x
            and abs(_crowded - (770 + _gap + _icon_r)) < 1e-9
            and _clamped == 2000 - _icon_r)
    check("HUD icon anchor — stays put with room, pushed clear of the "
          "text's actual width, clamped inside the frame "
          "(Graphics Pass 3 I3b)", ok30,
          f"roomy->{_roomy}, crowded->{_crowded}, clamped->{_clamped}")

    # 30. rotate_vector (cue-angle dial): a rotate-then-un-rotate round-trips,
    #     and a 90 deg rotation swaps/negates the axes in the expected
    #     screen-convention direction.
    _rdx, _rdy = rotate_vector(*rotate_vector(3.0, 4.0, 37.0), -37.0)
    _rx90, _ry90 = rotate_vector(1.0, 0.0, 90.0)
    ok31 = (abs(_rdx - 3.0) < 1e-9 and abs(_rdy - 4.0) < 1e-9
            and abs(_rx90) < 1e-9 and abs(_ry90 - 1.0) < 1e-9)
    check("rotate_vector — round-trips, 90 deg rotates as expected "
          "(Graphics Pass 3 I3b)", ok31)

    # 30b. dial_angle (bug-report follow-up, R6.6): the rotating cue-angle
    #      knob's absolute-angle mapping is the true inverse of
    #      rotate_vector(1, 0, angle) at several angles including the wrap
    #      point at 0/360, and (0,0) (centre, no drag yet) defaults sanely
    #      to 0 deg rather than raising.
    ok31b = all(
        abs(dial_angle(*rotate_vector(1.0, 0.0, a)) - (a % 360.0)) < 1e-6
        for a in (0.0, 37.0, 90.0, 179.9, 271.0, 359.5)
    )
    ok31b = ok31b and dial_angle(0.0, 0.0) == 0.0
    check("dial_angle — true inverse of rotate_vector at the wrap point "
          "and elsewhere, safe at the centre (bug-report follow-up R6.6)",
          ok31b)

    # 31b. trail_dot_style (Increment 4a, spectator motion trails): newest
    #      sample is full size / unfaded, oldest shrinks to the floor and
    #      fades fully, and it's monotonic in between so a trail visibly
    #      tapers rather than jumping. A single-sample trail doesn't fade.
    _r0, _f0 = trail_dot_style(0, 10)
    _r9, _f9 = trail_dot_style(9, 10)
    _rmid, _fmid = trail_dot_style(5, 10)
    ok31c = (_r0 == 1.0 and _f0 == 0.0
             and _r9 == 0.25 and _f9 == 1.0
             and _r0 > _rmid > _r9 and _f0 < _fmid < _f9
             and trail_dot_style(0, 1) == (1.0, 0.0))
    check("trail_dot_style — newest sample full-size/unfaded, oldest at the "
          "floor, monotonic tapering in between (Increment 4a)", ok31c)

    # 31d. swallow_progress (Increment 4b, pot swallow animation): t=0 right
    #      at capture, t=1 once the duration has fully elapsed (and stays 1
    #      past it, doesn't overshoot), monotonic in between, and genuinely
    #      eased -- ease-in means the midpoint is BELOW the linear halfway
    #      point (still lingering near the mouth, not already halfway to the
    #      cup). duration<=0 drops instantly rather than dividing by zero.
    _s0 = swallow_progress(0, 14)
    _s14 = swallow_progress(14, 14)
    _s20 = swallow_progress(20, 14)
    _smid = swallow_progress(7, 14)
    ok31d = (_s0 == 0.0 and _s14 == 1.0 and _s20 == 1.0
             and _s0 < _smid < _s14 and _smid < 0.5
             and swallow_progress(5, 0) == 1.0)
    check("swallow_progress — eased 0->1 over the duration, clamped past "
          "it, ease-in lags the linear midpoint (Increment 4b)", ok31d)

    # 31e. finale_fade (Increment 4c, slow-mo black finale): 0 right at the
    #      trigger and 0 once the window's over -- the fade genuinely
    #      returns to nothing, doesn't hang -- peaking at 1 exactly at the
    #      midpoint, symmetric ramp in and out, and monotonic on each half
    #      (rises then falls, doesn't wobble). duration<=0 is always 0.
    _e0 = finale_fade(0, 70)
    _e70 = finale_fade(70, 70)
    _emid = finale_fade(35, 70)
    _eq1 = finale_fade(17, 70)   # quarter-way: still rising
    _eq3 = finale_fade(53, 70)   # three-quarter: falling, symmetric partner
    ok31e = (abs(_e0) < 1e-9 and abs(_e70) < 1e-9 and abs(_emid - 1.0) < 1e-9
             and _e0 < _eq1 < _emid and _emid > _eq3 > _e70
             and abs(_eq1 - _eq3) < 1e-6
             and finale_fade(-1, 70) == 0.0 and finale_fade(71, 70) == 0.0
             and finale_fade(10, 0) == 0.0)
    check("finale_fade — 0 at both ends, peaks at the midpoint, symmetric "
          "ramp in/out, clamps outside the window (Increment 4c)", ok31e)

    # 31f. grade_params (colour-grade Table-tab TabStrip): the three
    #      entries come back in TabStrip order with distinct labels, and an
    #      out-of-range index clamps to a valid entry rather than raising
    #      (the render loop must never crash on this, even though the UI
    #      that drives it can't actually produce an out-of-range index).
    _g0 = grade_params(0)
    _g1 = grade_params(1)
    _g2 = grade_params(2)
    ok31f = (_g0[0] == "Warm" and _g1[0] == "Cool" and _g2[0] == "Contrast"
             and len({_g0[0], _g1[0], _g2[0]}) == 3
             and grade_params(-1) == _g0 and grade_params(99) == _g2)
    check("grade_params — Warm/Cool/Contrast in TabStrip order, "
          "out-of-range index clamps rather than raising", ok31f)

    # 31g. synth_tone_samples (sound effects): correct length, every sample
    #      stays within int16 range, deterministic given the same seed
    #      (rebuild it and get byte-identical output -- essential since
    #      it's cached and reused across many play() calls per Sound), and
    #      the decay envelope genuinely decays (a later window's peak
    #      amplitude is smaller than an earlier window's, not flat or
    #      growing).
    _sa = synth_tone_samples(900.0, 0.06, 22050, 35.0, 0.25, seed=7)
    _sb = synth_tone_samples(900.0, 0.06, 22050, 35.0, 0.25, seed=7)
    _early_peak = max(abs(v) for v in _sa[:200])
    _late_peak = max(abs(v) for v in _sa[-200:])
    ok31g = (len(_sa) == round(0.06 * 22050) and _sa == _sb
             and all(-32768 <= v <= 32767 for v in _sa)
             and _late_peak < _early_peak)
    check("synth_tone_samples — correct length, in-range, deterministic "
          "given the same seed, decay envelope genuinely decays", ok31g)

    # 31h. scale_ball_hit_volume: 0 at/below zero impulse, linear up to the
    #      reference impulse, clamped at 1.0 beyond it (a break-shot
    #      pile-up shouldn't try to exceed "full volume").
    ok31h = (scale_ball_hit_volume(0.0) == 0.0
             and scale_ball_hit_volume(-1.0) == 0.0
             and abs(scale_ball_hit_volume(HIT_IMPULSE_REF) - 1.0) < 1e-9
             and abs(scale_ball_hit_volume(HIT_IMPULSE_REF / 2.0) - 0.5) < 1e-9
             and scale_ball_hit_volume(HIT_IMPULSE_REF * 5.0) == 1.0)
    check("scale_ball_hit_volume — 0 at zero, linear to the reference "
          "impulse, clamped at 1.0 beyond it", ok31h)

    # 31i. r8 ball-hit impact model (pure core): the impulse -> timbre mapping
    #      must be monotonic in the physically right direction (harder hits
    #      BRIGHTER, SHORTER, noisier -- that's the whole point of the rework),
    #      hardness/tier must clamp at both ends, and the synthesised buffer
    #      must be int16-safe, deterministic, genuinely decaying, AND ramp UP
    #      from ~0 across the attack rather than starting at full amplitude
    #      (a step at sample 0 is itself an audible click).
    _soft = impact_params(0.0)
    _hard = impact_params(1.0)
    _mid = impact_params(0.5)
    ok31i_map = (_hard["partial_hz"] > _soft["partial_hz"]        # brighter
                 and _hard["decay"] > _soft["decay"]              # shorter
                 and _hard["noise_mix"] > _soft["noise_mix"]      # sharper crack
                 and _hard["lp_hz"] > _soft["lp_hz"]              # opens up
                 and _soft["partial_hz"] < _mid["partial_hz"] < _hard["partial_hz"]
                 and impact_params(-5.0) == impact_params(0.0)    # clamps low
                 and impact_params(9.9) == impact_params(1.0))    # clamps high
    # r8.2: the properties that separate a POLYMER KNOCK from a GLASS PLINK.
    # These are the actual bug this rework fixes, so they get asserted, not
    # just described in a comment.
    ok31i_polymer = (
        # noise is the BODY of the sound, not a garnish on a tone
        _soft["noise_mix"] > 0.6 and _hard["noise_mix"] > 0.6
        # modal content sits well below the glassy 2-2.5kHz region
        and _hard["partial_hz"] < 1500.0
        # decay is fast enough that the sound is DEAD within ~20ms
        and _soft["decay"] > 150.0
        and math.exp(-_soft["decay"] * 0.020) < 0.05
        # and there are several INHARMONIC partials -- not one pitch
        and len(IMPACT_PARTIAL_RATIOS) >= 3
        and not any(abs(r - round(r)) < 1e-6 for r in IMPACT_PARTIAL_RATIOS[1:]))
    # the lowpass must actually attenuate high frequencies (it's what kills hiss)
    _hf = [(1 if i % 2 == 0 else -1) for i in range(400)]   # Nyquist-rate square
    _lp = one_pole_lowpass(_hf, 2000.0, 44100)
    ok31i_lp = (max(abs(v) for v in _lp[50:]) < 0.5
                and one_pole_lowpass([], 2000.0, 44100) == [])
    ok31i_hard = (impact_hardness(0.0) == 0.0 and impact_hardness(-1.0) == 0.0
                  and abs(impact_hardness(HIT_IMPULSE_REF) - 1.0) < 1e-9
                  and impact_hardness(HIT_IMPULSE_REF * 4.0) == 1.0)
    ok31i_tier = (impact_tier(0.0) == 0
                  and impact_tier(1.0) == IMPACT_TIERS - 1
                  and impact_tier(2.0) == IMPACT_TIERS - 1   # clamps, no IndexError
                  and 0 <= impact_tier(0.5) < IMPACT_TIERS)
    _ia = synth_impact_samples(0.8, 44100, seed=3)
    _ib = synth_impact_samples(0.8, 44100, seed=3)
    _attack_n = max(1, int(IMPACT_ATTACK_S * 44100))
    _peak_body = max(abs(v) for v in _ia[_attack_n:_attack_n + 400])
    _peak_tail = max(abs(v) for v in _ia[-400:])
    ok31i_synth = (len(_ia) == round(IMPACT_DURATION_S * 44100)
                   and _ia == _ib                                  # deterministic
                   and all(-32768 <= v <= 32767 for v in _ia)      # int16-safe
                   and abs(_ia[0]) < 500                           # ramps up, no click
                   and _peak_tail < _peak_body)                    # genuinely decays
    check("impact model (r8 ball-hit) — harder hits map brighter/shorter/"
          "noisier, hardness+tier clamp at both ends, AD buffer is "
          "deterministic, int16-safe, click-free at onset, and decays",
          ok31i_map and ok31i_hard and ok31i_tier and ok31i_synth)

    # 31j. write_wav (r8.1): the samples we synthesise must be exactly the
    #      samples that land on disk -- mono, 16-bit, at the rate we asked
    #      for, byte-for-byte identical on read-back. This is the probe path
    #      that exists specifically so a sound can be checked independently
    #      of pygame's mixer, so it can't be the thing that lies to us.
    import tempfile, wave as _wave, array as _arr
    _wsamples = synth_impact_samples(0.5, 44100, seed=11)
    with tempfile.TemporaryDirectory() as _td:
        _wpath = os.path.join(_td, "t.wav")
        _n = write_wav(_wpath, _wsamples, 44100)
        with _wave.open(_wpath, "rb") as _w:
            _rt = _arr.array("h")
            _rt.frombytes(_w.readframes(_w.getnframes()))
            ok31j = (_w.getnchannels() == 1 and _w.getsampwidth() == 2
                     and _w.getframerate() == 44100
                     and _n == len(_wsamples)
                     and list(_rt) == list(_wsamples))
    check("write_wav — mono/16-bit/correct rate, and samples round-trip "
          "byte-identical (the probe path can't lie about what we synthesised)",
          ok31j)

    # 32. r9 phase 1 — FOULS. assess_foul() is the pure core of the rules
    #     rework, so it gets tested directly rather than through a live table.
    #     A fake sim carries only the two facts the rules actually read.
    class _FakeSim:
        def __init__(self, first_contact, cushion):
            self.first_contact = first_contact
            self.cushion_after_contact = cushion

    class _FakeSimFull(_FakeSim):
        """Test double for on_rest(): carries the full surface the rules read,
        so the turn/penalty state machine can be exercised without a table."""
        def __init__(self, first_contact, cushion, potted, remaining=3):
            super().__init__(first_contact, cushion)
            self._potted = list(potted)
            self._remaining = remaining

        def potted_colours(self):
            return list(self._potted)

        def remaining(self, colour):
            return self._remaining

    g32 = Game()
    g32.colours = {0: "red", 1: "yellow"}
    g32.current = 0
    legal32 = ["red"]
    ok32 = (
        # legal: hit own colour first, potted something
        g32.assess_foul(_FakeSim("red", False), legal32, ["red"], False) is None
        # legal: hit own colour first, nothing potted BUT a cushion was reached
        and g32.assess_foul(_FakeSim("red", True), legal32, [], False) is None
        # foul: cue potted
        and g32.assess_foul(_FakeSim("red", True), legal32, ["cue"], True) == "scratch"
        # foul: cue ball hit nothing at all
        and g32.assess_foul(_FakeSim(None, False), legal32, [], False) == "no contact"
        # foul: WRONG BALL FIRST -- the whole point of phase 1, and completely
        # undetectable before, since nothing was potted here at all
        and g32.assess_foul(_FakeSim("yellow", True), legal32, [], False
                            ).startswith("wrong ball first")
        # foul: legal contact, but nothing potted and no cushion reached
        and g32.assess_foul(_FakeSim("red", False), legal32, [], False
                            ) == "no cushion, no pot"
    )
    check("r9 fouls — scratch / no-contact / wrong-ball-first / no-cushion-no-pot "
          "all detected, and a legal contact reaching a cushion is NOT a foul",
          ok32)

    # 33. r9 phase 3 — FREE SHOT + TWO VISITS. The penalty state machine:
    #     fouling hands the table over WITH a free shot and two visits; a free
    #     shot suppresses wrong-ball-first (and only that); a miss on two
    #     visits keeps you at the table exactly once.
    g33 = Game()
    g33.colours = {0: "red", 1: "yellow"}
    g33.current = 0
    ok33_free_suppresses = (
        g33.assess_foul(_FakeSim("yellow", True), ["red"], [], False) is not None)
    g33.free_shot = True
    ok33_free_suppresses = ok33_free_suppresses and (
        # same shot, but on a free shot: no longer a foul
        g33.assess_foul(_FakeSim("yellow", True), ["red"], [], False) is None
        # ...but a free shot does NOT excuse a scratch
        and g33.assess_foul(_FakeSim("yellow", True), ["red"], ["cue"], True)
            == "scratch")
    # foul hands over free shot + two visits
    g33b = Game()
    g33b.colours = {0: "red", 1: "yellow"}
    g33b.current = 0
    g33b.on_rest(_FakeSimFull(first_contact="yellow", cushion=True, potted=[]))
    ok33_handover = (g33b.current == 1 and g33b.free_shot is True
                     and g33b.visits_left == 2 and g33b.fouls == 1)
    # the incoming player misses legally -> keeps the table for visit 2
    g33b.on_rest(_FakeSimFull(first_contact="yellow", cushion=True, potted=[]))
    ok33_second = (g33b.current == 1 and g33b.visits_left == 1
                   and g33b.free_shot is False)
    # misses again -> now the table finally passes back
    g33b.on_rest(_FakeSimFull(first_contact="yellow", cushion=True, potted=[]))
    ok33_pass = (g33b.current == 0 and g33b.visits_left == 1)
    check("r9 free shot + two visits — a foul hands over a free shot and two "
          "visits; the free shot suppresses wrong-ball-first but never a "
          "scratch; a legal miss uses the second visit, the next one passes",
          ok33_free_suppresses and ok33_handover and ok33_second and ok33_pass)

    # 34. r9 phase 2 — AI SPIN + SAFETY + FOUL RISK. The pure scoring cores:
    #     spin must actually change the predicted leave (otherwise the 3x3 grid
    #     is decorative), scratch_risk must be high at a pocket and ~0 in open
    #     space, and safety_quality must reward leaving the opponent nothing.
    s34 = Sim(layout="empty")
    s34._respot_cue()
    ai34 = PoolAI("T", aim_jitter=0.0, threshold=0.05, greed=0.5, caution=0.5,
                  rng=random.Random(3))
    # Find a genuinely potable (cue, target, pocket) triple rather than assuming
    # one -- pot_estimate legitimately rejects impossible geometry, and a test
    # that hardcodes the wrong pocket tests nothing.
    est34 = None
    for (_pc34, _cr34) in capture_points():
        est34 = pot_estimate((0.6, 0.6), (1.0, 0.9), _pc34, _cr34,
                             CFG["CUE_R_M"], ball_r(), 0.0)
        if est34 is not None:
            break
    lv_none = estimate_leave(est34, 2.0, follow=0.0)
    lv_foll = estimate_leave(est34, 2.0, follow=0.9)
    lv_draw = estimate_leave(est34, 2.0, follow=-0.9)
    ok34_spin = (math.dist(lv_none["rest"], lv_foll["rest"]) > 1e-4
                 and math.dist(lv_none["rest"], lv_draw["rest"]) > 1e-4
                 and math.dist(lv_foll["rest"], lv_draw["rest"]) > 1e-4)
    pocket34 = capture_points()[0][0]
    # NB the table centre sits level with the middle pockets, so a SMALL
    # non-zero risk there is correct, not a bug -- assert the property that
    # actually matters (a pocket is drastically riskier than open play), not an
    # arbitrarily tight magic number.
    risk_pocket = scratch_risk(pocket34, 0.0)
    risk_open = scratch_risk((0.9, 0.45), 0.0)     # genuinely open baize
    ok34_risk = (risk_pocket > 0.7
                 and risk_open < 0.05
                 and risk_pocket > 10.0 * max(risk_open, 1e-6)
                 and 0.0 <= scratch_risk(pocket34, 5.0) <= 1.0
                 # a fast cue is less likely to drop than one dying in the jaws
                 and scratch_risk(pocket34, 5.0) < risk_pocket)
    # safety_quality: leaving the opponent nothing on beats leaving them a sitter
    rc34, ro34 = CFG["CUE_R_M"], ball_r()
    q_nothing = safety_quality((0.1, 0.1), [], [], rc34, ro34, 0.0)
    ok34_safety = (abs(q_nothing - 1.0) < 1e-9      # no opponent balls = perfect
                   and 0.0 <= safety_quality((1.0, 0.9), [(1.2, 0.9)], [],
                                             rc34, ro34, 0.01) <= 1.0)
    check("r9 AI spin/safety/foul-risk — follow, draw and no-spin give three "
          "different predicted leaves; scratch_risk is high in a pocket and "
          "~0 in open play; safety_quality is bounded and rewards a dead leave",
          ok34_spin and ok34_risk and ok34_safety)

    # 35. r10 HUD fine adjustment -- nudge_spin must obey the SAME unit-circle
    #     spin budget as a pad drag, or the 0.01 buttons could walk the contact
    #     point outside the circle one step at a time and reach a spin the pad
    #     itself cannot express.
    f35, s35 = nudge_spin(0.0, 0.0, 0.01, 0.0)
    ok35_step = abs(f35 - 0.01) < 1e-9 and abs(s35) < 1e-9
    # walk hard against the rim: must clamp TO the circle, never past it
    f, s = 0.0, 0.0
    for _ in range(400):
        f, s = nudge_spin(f, s, 0.01, 0.01)
    ok35_clamp = math.hypot(f, s) <= 1.0 + 1e-9
    # and starting outside, it must pull back onto the circle, not stay out
    f36, s36 = nudge_spin(0.9, 0.9, 0.0, 0.0)
    ok35_pull = math.hypot(f36, s36) <= 1.0 + 1e-9
    check("r10 spin nudge — 0.01 steps apply exactly, and repeated nudges clamp "
          "to the unit circle rather than escaping the pad's physical budget",
          ok35_step and ok35_clamp and ok35_pull)

    # 36. r10 custom mode -- placement legality. A ball may not be dropped in a
    #     rail, inside a pocket's capture radius (it would just vanish the
    #     instant physics resumed), or overlapping another ball.
    rr = ball_r()
    x0r, y0r, x1r, y1r = play_rect()
    centre36 = ((x0r + x1r) / 2.0, (y0r + y1r) / 2.0)
    ok36_open = can_place_ball(centre36, [], rr, [])
    ok36_overlap = not can_place_ball(centre36, [(centre36, rr)], rr, [rr])
    ok36_pocket = not can_place_ball(capture_points()[0][0], [], rr, [])
    ok36_rail = not can_place_ball((x0r - 0.05, centre36[1]), [], rr, [])
    # just clear of an existing ball IS legal -- the rule must not be so strict
    # that a legitimate tight cluster becomes unplaceable
    near36 = (centre36[0] + 2 * rr + 0.002, centre36[1])
    ok36_near = can_place_ball(near36, [(centre36, rr)], rr, [rr])
    check("r10 ball placement — open baize OK; rail, pocket and overlap all "
          "rejected; a legitimately tight (but clear) neighbour still allowed",
          ok36_open and ok36_overlap and ok36_pocket and ok36_rail and ok36_near)

    # 37. r10 layout save/load -- must round-trip exactly, in METRES (a layout
    #     saved at one window size has to load identically at another), and must
    #     survive a corrupt/hand-edited file by dropping bad entries, not raising.
    balls37 = [("cue", (0.5, 0.4)), ("red", (1.0, 0.9)), ("black", (1.4, 0.5))]
    round37 = deserialise_layout(serialise_layout(balls37))
    ok37_round = (len(round37) == 3
                  and round37[0][0] == "cue"
                  and abs(round37[1][1][0] - 1.0) < 1e-9
                  and round37 == balls37)
    ok37_json = deserialise_layout(json.loads(json.dumps(
        serialise_layout(balls37)))) == balls37          # survives a real JSON trip
    ok37_bad = (deserialise_layout({"balls": [
                    {"kind": "purple", "x": 1.0, "y": 1.0},   # unknown kind
                    {"kind": "red", "x": "nope", "y": 1.0},   # unparseable
                    {"kind": "red"},                          # missing keys
                    {"kind": "red", "x": 1.0, "y": 0.5},      # the one good one
                ]}) == [("red", (1.0, 0.5))]
                and deserialise_layout({}) == []
                and deserialise_layout(None) == [])
    check("r10 layout persistence — round-trips exactly through JSON in metres, "
          "and a corrupt file drops bad entries instead of raising",
          ok37_round and ok37_json and ok37_bad)

    # 38. r11 persistent status strip -- wrap_fields is what makes a 6-field
    #     readout fit a 260px column at all, so it gets tested directly: it must
    #     pack greedily, never exceed the width, never DROP a field, and never
    #     hang on a field too wide to fit (which must still get its own line --
    #     a clipped readout beats a silently missing one).
    f38 = ["aaa", "bbb", "ccc", "ddd"]
    packed = wrap_fields(f38, 8)                     # "aaa  bbb" == 8 chars
    ok38_pack = packed == ["aaa  bbb", "ccc  ddd"]
    ok38_nodrop = all(any(f in ln for ln in wrap_fields(f38, 8)) for f in f38)
    ok38_width = all(len(ln) <= 8 for ln in wrap_fields(f38, 8))
    # a single over-wide field: kept, on its own line, no infinite loop
    ok38_toobig = wrap_fields(["short", "averyverylongfield"], 8) \
                  == ["short", "averyverylongfield"]
    ok38_empty = (wrap_fields([], 10) == [] and wrap_fields(["", "a"], 10) == ["a"])
    # and it must pack by the MEASURE given, not by len -- the renderer passes
    # pixel widths, and a proportional font makes those two very different
    ok38_measure = wrap_fields(["ab", "cd"], 10, measure=lambda s: len(s) * 4) \
                   == ["ab", "cd"]          # "ab  cd" would measure 24 > 10
    check("r11 status strip — wrap_fields packs greedily within the width, drops "
          "nothing, honours a custom measure (pixels, not characters), and keeps "
          "an over-wide field on its own line instead of hanging",
          ok38_pack and ok38_nodrop and ok38_width and ok38_toobig
          and ok38_empty and ok38_measure)

    # 39. r12 potted-ball chamber -- chamber_slots must fit a FULL rack (15
    #     object balls) inside the strip by shrinking the balls, never by
    #     overflowing, and must keep them in potted ORDER (which is the entire
    #     point of a real table's glass chamber).
    d39, xs39 = chamber_slots(3, 300, 20, 4)
    ok39_small = (abs(d39 - 20) < 1e-9 and len(xs39) == 3
                  and xs39 == sorted(xs39))          # order preserved, L->R
    # a full blackball rack must still fit -- balls shrink rather than spill
    d39f, xs39f = chamber_slots(15, 300, 20, 4)
    span = (xs39f[-1] + d39f / 2) - (xs39f[0] - d39f / 2)
    ok39_full = (d39f < 20 and len(xs39f) == 15 and span <= 300 + 1e-9
                 and xs39f == sorted(xs39f))
    # never bigger than d_max even with acres of room; degenerate inputs safe
    d39w, _ = chamber_slots(1, 5000, 20, 4)
    ok39_cap = abs(d39w - 20) < 1e-9
    ok39_edge = (chamber_slots(0, 300, 20, 4) == (0, [])
                 and chamber_slots(5, 0, 20, 4) == (0, []))
    check("r12 potted chamber — balls sit in potted order, a full 15-ball rack "
          "fits by shrinking rather than overflowing, size is capped at d_max, "
          "and empty/zero-width cases are safe",
          ok39_small and ok39_full and ok39_cap and ok39_edge)

    # 40. r13 ball in hand -- the legal region is the BAULK RECTANGLE (not the
    #     'D': modern UK pool dropped the D, and blackball gives ball-in-hand
    #     anywhere in baulk, which is what r9's ruleset implements).
    bx0, by0, bx1, by1 = baulk_rect()
    px0, py0, px1, py1 = play_rect()
    rc40 = CFG["CUE_R_M"]
    ok40_geom = (abs(bx0 - px0) < 1e-9 and abs(by0 - py0) < 1e-9
                 and abs(by1 - py1) < 1e-9
                 and abs(bx1 - (px0 + (px1 - px0) * CFG["BAULK_FRAC"])) < 1e-9
                 and bx1 < px1)                      # baulk is a strip, not the table
    deep = ((bx0 + bx1) / 2.0, (by0 + by1) / 2.0)    # middle of baulk
    beyond = ((bx1 + px1) / 2.0, (by0 + by1) / 2.0)  # past the baulk line
    ok40_in = in_baulk(deep, rc40) and not in_baulk(beyond, rc40)
    # a ball STRADDLING the baulk line is not in baulk -- it must be fully behind
    ok40_straddle = not in_baulk((bx1, (by0 + by1) / 2.0), rc40)
    ok40_place = (can_place_cue(deep, [], rc40)
                  and not can_place_cue(beyond, [], rc40)           # outside baulk
                  and not can_place_cue(deep, [(deep, ball_r())], rc40))  # occupied
    # every AI candidate must actually lie in baulk -- a grid that generates
    # illegal candidates would silently shrink the AI's real choice
    ok40_cands = (len(baulk_candidates()) > 0
                  and all(in_baulk(c, rc40) for c in baulk_candidates()))
    check("r13 ball in hand — baulk is the rectangle behind the baulk line (not "
          "a D), a cue straddling the line isn't in it, placement rejects "
          "outside-baulk and occupied spots, and every AI candidate is legal",
          ok40_geom and ok40_in and ok40_straddle and ok40_place and ok40_cands)

    # 41. r14 aim overlay -- the pure cores. pot_chance_colour must run RED at a
    #     dead shot through AMBER at a coin-flip to GREEN at a certainty (that
    #     ramp IS the overlay's main signal, so it gets asserted, not eyeballed),
    #     and aim_taper_alpha must fade with distance rather than sit flat -- a
    #     uniform hairline is precisely what reads as a 1980s vector overlay.
    c_dead, c_half, c_on = (pot_chance_colour(0.0), pot_chance_colour(0.5),
                            pot_chance_colour(1.0))
    ok41_ends = (c_dead[0] > c_dead[1] and c_dead[0] > c_dead[2]      # red-dominant
                 and c_on[1] > c_on[0] and c_on[1] > c_on[2])         # green-dominant
    # green channel must rise monotonically with pot chance, red must fall
    ramp41 = [pot_chance_colour(i / 10.0) for i in range(11)]
    ok41_mono = ([c[1] for c in ramp41] == sorted(c[1] for c in ramp41)
                 and [c[0] for c in ramp41] == sorted((c[0] for c in ramp41),
                                                      reverse=True))
    ok41_clamp = (pot_chance_colour(-3.0) == c_dead
                  and pot_chance_colour(9.0) == c_on)
    ok41_amber = c_half[0] > 200 and c_half[1] > 120 and c_half[2] < 100
    # taper: brightest at the cue ball, dimmest at the far end, monotonic
    taps = [aim_taper_alpha(i, 12) for i in range(12)]
    ok41_taper = (taps[0] > taps[-1]
                  and taps == sorted(taps, reverse=True)
                  and aim_taper_alpha(0, 1) == 210
                  and all(0 <= a <= 255 for a in taps))
    check("r14 aim overlay — pot chance ramps red->amber->green monotonically "
          "and clamps; the aim line tapers with distance instead of sitting flat",
          ok41_ends and ok41_mono and ok41_clamp and ok41_amber and ok41_taper)

    # 42. r15 study output -- the per-shot record must round-trip through real
    #     JSON (a record carrying a numpy float or a tuple would serialise fine
    #     and then blow up a study run 400 games in), and must preserve the two
    #     fields the whole analysis hangs on: p_pred and potted.
    plan42 = {"type": "pot", "p": 0.812345, "u": 0.5, "risk": 0.1,
              "power": 2.5, "follow": 0.7, "side": -0.7}
    rec42 = make_shot_record(3, 0, "SHARK", "red", plan42, ["red"], "red",
                             True, None, "potted — continue", False, False,
                             (0.2, 0.45))
    back42 = json.loads(json.dumps(rec42))       # must survive a REAL json trip
    ok42_round = (back42 == rec42
                  and abs(back42["p_pred"] - 0.8123) < 1e-9
                  and back42["potted"] == ["red"]
                  and back42["cue_placed"] == [0.2, 0.45]
                  and back42["type"] == "pot")
    ok42_null = (make_shot_record(1, 1, "STEADY", None, {"type": "safety"},
                                  [], None, False, "no contact", "foul", True,
                                  True, None)["cue_placed"] is None)
    check("r15 study record — a shot serialises to real JSON and back "
          "unchanged, keeping p_pred and potted (the two fields calibration "
          "depends on), and copes with an open table / no cue placement",
          ok42_round and ok42_null)

    # 43. r15 study stats -- the Wilson interval is what stops a 12-game result
    #     being reported as if it meant something, and the calibration binner is
    #     what tells us whether pot_estimate is honest.
    lo_s, hi_s = wilson_interval(5, 12)          # the actual r9 study result
    ok43_noise = lo_s < 0.5 < hi_s               # MUST be inconclusive
    lo_b, hi_b = wilson_interval(300, 500)       # a real 60% edge at n=500
    ok43_sig = lo_b > 0.5                        # MUST be significant
    ok43_bounds = (wilson_interval(0, 10)[0] >= 0.0      # sane at the extremes
                   and wilson_interval(10, 10)[1] <= 1.0
                   and wilson_interval(0, 0) == (0.0, 1.0))
    ok43_narrows = ((wilson_interval(50, 100)[1] - wilson_interval(50, 100)[0])
                    > (wilson_interval(500, 1000)[1]
                       - wilson_interval(500, 1000)[0]))   # more n -> tighter
    # calibration: a perfectly honest model must read back as honest
    cal_shots = ([{"type": "pot", "p_pred": 0.9, "colour": "red",
                   "potted": ["red"]}] * 9
                 + [{"type": "pot", "p_pred": 0.9, "colour": "red",
                     "potted": []}]
                 + [{"type": "safety", "p_pred": 0.0, "colour": "red",
                     "potted": []}] * 5)        # safeties must be EXCLUDED
    cal = pot_calibration(cal_shots)
    ok43_cal = (len(cal) == 1 and cal[0][2] == 10          # 10 pots, no safeties
                and abs(cal[0][3] - 0.9) < 1e-9            # predicted 90%
                and abs(cal[0][4] - 0.9) < 1e-9)           # actual 90% -> honest
    # potting the OPPONENT's colour is a foul, not a made pot -- it must not count
    ok43_opp = (pot_calibration([{"type": "pot", "p_pred": 0.9, "colour": "red",
                                  "potted": ["yellow"]}])[0][4] == 0.0)
    check("r15 study stats — Wilson calls 5/12 inconclusive but 300/500 "
          "significant and tightens with n; calibration bins pots only "
          "(not safeties) and won't count an opponent's ball as a made pot",
          ok43_noise and ok43_sig and ok43_bounds and ok43_narrows
          and ok43_cal and ok43_opp)

    # 44. r16 pot_estimate calibration fix -- the lever-arm term must shrink
    # the pot chance as cue-throw distance grows, for an OTHERWISE IDENTICAL
    # straight-on shot (same object ball, same pocket, same fullness=1, same
    # jitter). Pre-r16 the formula was blind to t_cue entirely (bar a weak,
    # unrelated decay term), which is the root cause of the 91.5%-predicted/
    # 18.3%-actual calibration gap the r15 study surfaced.
    t44, pc44, cap44 = (0.45, 0.455), (1.6, 0.455), 0.032512
    od44 = vnorm(pc44[0] - t44[0], pc44[1] - t44[1])
    G44 = (t44[0] - od44[0] * (CFG["CUE_R_M"] + ball_r()),
           t44[1] - od44[1] * (CFG["CUE_R_M"] + ball_r()))
    def cp_at(dist):     # place the cue dist behind the ghost ball, dead straight
        return (G44[0] - od44[0] * dist, G44[1] - od44[1] * dist)
    est_near = pot_estimate(cp_at(0.05), t44, pc44, cap44,
                             CFG["CUE_R_M"], ball_r(), 0.011)
    est_far = pot_estimate(cp_at(1.50), t44, pc44, cap44,
                            CFG["CUE_R_M"], ball_r(), 0.011)
    ok44 = (est_near is not None and est_far is not None
            and abs(est_near["fullness"] - 1.0) < 1e-6
            and abs(est_far["fullness"] - 1.0) < 1e-6
            and est_far["p"] < est_near["p"] - 0.3)   # far shot meaningfully harder
    check("r16 pot_estimate — cue-throw distance narrows the pot chance for "
          "an otherwise-identical straight shot (the missing lever arm behind "
          "the r15 calibration gap)",
          ok44, f"near(t_cue=0.05+contact) p={est_near['p']:.3f}, "
                f"far(t_cue=1.50+contact) p={est_far['p']:.3f}"
                if est_near and est_far else "estimate returned None")

    # 45. r17 pocket sensors (perf item 3) -- pocket capture moved from a Python
    # per-substep distance poll into pymunk sensor shapes. The whole point is
    # that it is an EXACT substitute, not a lenient one: a plain cap_r sensor
    # would fire on CIRCLE overlap (distance < cap_r + ball_radius), silently
    # widening the pocket. Shrinking each sensor by the ball's own radius means
    # the drop threshold stays exactly "centre within cap_r" -- so a ball just
    # INSIDE cap_r must drop and one just OUTSIDE must not. This is the pot/
    # no-pot decision itself, so it gets pinned down rather than assumed.
    pc45, cap45 = capture_points()[0]
    def _drops45(frac):
        s45 = Sim(layout="empty")
        d45 = cap45 * frac
        a45 = math.atan2(pc45[1], pc45[0])      # out along the pocket axis
        s45._add_ball(s45.alloc_id(),
                      (pc45[0] + math.cos(a45) * d45,
                       pc45[1] + math.sin(a45) * d45), "red")
        bid45 = max(s45.balls) if s45.balls else None
        s45.step(1.0 / 60.0)
        return bid45 not in s45.balls
    ok45_in = _drops45(0.50) and _drops45(0.99)     # inside cap_r -> must drop
    ok45_out = not _drops45(1.01) and not _drops45(2.0)  # outside -> must NOT
    # the sensor radius maths itself: sensor + ball == the old cap_r threshold
    ok45_r = all(abs(((cap - CFG["CUE_R_M"]) + CFG["CUE_R_M"]) - cap) < 1e-12
                 and abs(((cap - ball_r()) + ball_r()) - cap) < 1e-12
                 for _, cap in capture_points())
    check("r17 pocket sensors — capture still fires at exactly 'centre within "
          "cap_r' (a ball just inside drops, just outside does not), so moving "
          "the test into pymunk's C broad-phase didn't widen the pockets",
          ok45_in and ok45_out and ok45_r,
          f"0.99*cap_r drops={_drops45(0.99)}, 1.01*cap_r drops={_drops45(1.01)}")

    # 46. r18 personalities -- the study's two players must differ ONLY on
    # STRATEGY (threshold/greed/caution), never on SKILL (aim_jitter). A jitter
    # gap silently turns every AI-vs-AI study into a measure of who aims
    # straighter rather than whose strategy is better: measured, swapping the
    # jitter alone (leaving SHARK's whole aggressive playbook intact) moved it
    # from 90% to 45%. This assertion is what stops that confound creeping back
    # in the next time someone "makes SHARK a bit sharper".
    ais46 = default_ais(random.Random(3))
    jit46 = {a.aim_jitter for a in ais46}
    ok46_skill = len(jit46) == 1                      # SAME skill, always
    ok46_strat = (len({a.threshold for a in ais46}) == 2   # different strategy
                  and len({a.greed for a in ais46}) == 2
                  and len({a.caution for a in ais46}) == 2)
    # and the shared value is the one named constant, not a copy-pasted literal
    ok46_const = jit46 == {STUDY_JITTER}
    check("r18 personalities — SHARK and STEADY are skill-MATCHED (identical "
          "aim_jitter) and differ only on strategy, so a study measures "
          "strategy rather than who aims straighter",
          ok46_skill and ok46_strat and ok46_const,
          f"jitter {sorted(jit46)}, thresholds "
          f"{sorted(a.threshold for a in ais46)}, "
          f"greeds {sorted(a.greed for a in ais46)}")

    # 47. r19 study geometry -- the shot record must carry the POT GEOMETRY
    # (cut_deg / t_cue / d_tp), not just p_pred. Without these the calibration
    # residual is undiagnosable: "are thin cuts over-rated, or long pots?"
    # cannot be answered, and total distance has to be reverse-engineered out
    # of the power formula. They must also be None (not 0.0, not a crash) on a
    # safety, which has no ghost-ball est at all -- 0.0 would silently read as
    # "a dead-straight shot" in any analysis.
    est47 = pot_estimate((0.60, 0.60), (0.40, 0.30), capture_points()[0][0],
                         capture_points()[0][1], CFG["CUE_R_M"], ball_r(),
                         STUDY_JITTER)
    plan47 = {"type": "pot", "p": est47["p"], "power": 2.0, "est": est47}
    rec47 = make_shot_record(1, 0, "SHARK", "red", plan47, [], "red", True,
                             None, "", False, False, None)
    # round-trips as real JSON, and the geometry agrees with the estimate
    r47 = json.loads(json.dumps(rec47))
    ok47_geo = (abs(r47["t_cue"] - est47["t_cue"]) < 1e-3
                and abs(r47["d_tp"] - est47["d_tp"]) < 1e-3
                and abs(r47["cut_deg"]
                        - math.degrees(math.acos(est47["fullness"]))) < 0.05)
    safety47 = make_shot_record(2, 1, "STEADY", None, {"type": "safety"}, [],
                                None, True, None, "", False, False, None)
    ok47_safe = (safety47["cut_deg"] is None and safety47["t_cue"] is None
                 and safety47["d_tp"] is None)
    check("r19 study geometry — the shot record logs cut_deg/t_cue/d_tp so the "
          "calibration residual can be diagnosed directly instead of inferred, "
          "and leaves them None on a safety rather than a misleading 0.0",
          ok47_geo and ok47_safe and STUDY_SCHEMA >= 2,
          f"cut {rec47['cut_deg']}deg, t_cue {rec47['t_cue']}m, "
          f"d_tp {rec47['d_tp']}m, schema {STUDY_SCHEMA}")

    # 48. r20 corridor clearance -- the AI was running into balls it had itself
    # cleared: ~10% of ALL pot attempts struck the wrong ball first (flat across
    # every confidence bin, so not bad luck on thin cuts), and those attempts
    # potted at 1.4% while being rated 56%. Two compounding bugs, both pinned
    # here: (a) the clearance passed was SMALLER than the distance at which two
    # balls actually graze (a 2mm shave on the cue path, 6mm on the object
    # path), so a ball inside a real collision was reported clear; and (b) the
    # check ran on the IDEAL line, which _execute() then perturbs by aim_jitter,
    # so the AI validated a line it was never going to shoot.
    rc48, ro48 = CFG["CUE_R_M"], ball_r()
    graze_cue, graze_obj = rc48 + ro48, 2.0 * ro48
    # (a) never narrower than a real graze, even with zero jitter / zero throw
    ok48_graze = (cue_corridor(rc48, ro48, 0.0, 0.0) >= graze_cue - 1e-12
                  and object_corridor(ro48, 0.0, 0.0) >= graze_obj - 1e-12)
    # (b) widens with BOTH jitter and throw distance -- the drift is jitter*t_cue
    ok48_jit = (cue_corridor(rc48, ro48, 0.02, 0.5)
                > cue_corridor(rc48, ro48, 0.005, 0.5))
    ok48_len = (cue_corridor(rc48, ro48, 0.011, 1.2)
                > cue_corridor(rc48, ro48, 0.011, 0.2))
    # and the allowance is really CORRIDOR_SIGMA_K sigma of the lateral drift
    ok48_k = abs((cue_corridor(rc48, ro48, 0.011, 0.9) - graze_cue)
                 - CORRIDOR_SIGMA_K * 0.011 * 0.9) < 1e-12
    # a ball sitting exactly at the graze distance must NOT be called clear
    ok48_rej = not corridor_clear((0.0, 0.455), (0.9, 0.455),
                                  cue_corridor(rc48, ro48, 0.011, 0.9),
                                  [(0.45, 0.455 + graze_cue)])
    check("r20 corridor clearance — the corridor is never narrower than a real "
          "ball-to-ball graze, and widens with aim jitter and throw distance, "
          "so the AI stops clearing lines it isn't going to shoot",
          ok48_graze and ok48_jit and ok48_len and ok48_k and ok48_rej,
          f"cue graze {graze_cue*1000:.1f}mm -> corridor at 0.9m/0.011rad "
          f"{cue_corridor(rc48, ro48, 0.011, 0.9)*1000:.1f}mm")

    # 49. r21 calibration population -- a calibration table is only meaningful
    # over COMPARABLE attempts. On a free shot (r9) any ball may legally be
    # struck first, so the AI will happily cannon into an opponent's ball if
    # that's the best line -- it is using the rule, not misplaying. Scoring
    # pot_estimate against those shots silently drags 'actual' down and makes
    # the model look worse than it is. This pins the exclusion so a later
    # refactor can't quietly readmit them.
    free49 = [{"type": "pot", "p_pred": 0.9, "colour": "red", "potted": [],
               "free_shot": True} for _ in range(20)]      # all MISSED
    norm49 = [{"type": "pot", "p_pred": 0.9, "colour": "red", "potted": ["red"],
               "free_shot": False} for _ in range(10)]     # all POTTED
    cal49 = pot_calibration(free49 + norm49)
    top49 = [row for row in cal49 if row[0] >= 0.8]
    # with free shots excluded the top bin sees ONLY the 10 normal shots -> 100%
    ok49 = (len(top49) == 1 and top49[0][2] == 10
            and abs(top49[0][4] - 1.0) < 1e-9)
    # and the free shots really would have wrecked it if left in
    contaminated = sum(1 for s in free49 + norm49 if s["type"] == "pot")
    check("r21 calibration population — free shots are excluded from the "
          "calibration table (any ball may legally be struck first on one), so "
          "pot_estimate is scored only over comparable pot attempts",
          ok49 and contaminated == 30,
          f"top bin n={top49[0][2] if top49 else 0} of {contaminated} records, "
          f"actual={top49[0][4]*100 if top49 else 0:.0f}%")

    # 50. r22 chamber history -- the potted-ball chamber must show the WHOLE
    # game in pot order. It read potted_log, which strike() deliberately wipes
    # every shot (r9, so the rules can judge THIS shot's fouls), so it only ever
    # showed the last shot's pots -- "one ball, then it disappears". potted_all
    # is game-scoped and survives strike(); potted_log KEEPS its old meaning,
    # because the rules engine depends on it being shot-scoped.
    s50 = Sim(layout="empty")
    s50._add_ball(s50.CUE_ID, (0.30, 0.455), "cue")
    pot50 = capture_points()[0][0]
    order50 = ["red", "yellow", "red"]
    for i, col in enumerate(order50):
        bid = s50.alloc_id()
        s50._add_ball(bid, (0.60 + 0.10 * i, 0.30), col)
        s50.strike((1.0, 0.0), 1.0)        # wipes potted_log every time
        s50.balls[bid][0].position = pot50  # drop it straight in the pocket
        s50.step(1.0 / 60.0)
    ok50_all = s50.potted_colours_all() == order50      # full history, in order
    ok50_shot = len(s50.potted_colours()) <= 1          # still shot-scoped
    check("r22 chamber history — the chamber's list is GAME-scoped and keeps "
          "every potted ball in order, while the rules' shot-scoped potted_log "
          "still resets on each strike",
          ok50_all and ok50_shot,
          f"game {s50.potted_colours_all()}, shot {s50.potted_colours()}")

    # 51. r22 placement invariants -- a REGRESSION GUARD, written after an
    # attempted "let balls sit on the jaws" fix (a circular pocket-mouth
    # exemption from the rail rule) turned out to leak ALONG the cushions: the
    # middle pockets' mouth circles reach out over the bottom/top rails, so a
    # ball centre 15mm from a rail -- which must be impossible for a 25.4mm
    # ball -- became legal. That fix was reverted. These two invariants are what
    # any future attempt must not break:
    #   (a) a ball can never be placed where the pocket would instantly eat it
    #   (b) a ball can never be embedded in a rail
    # NOTE (known limitation, deliberately left): because play_rect() is a plain
    # rectangle that knows nothing about pockets, the jaws area is still
    # unreachable in custom mode. Fixing that properly means testing containment
    # against cushion_path.py's real cushion-nose polyline rather than a
    # rectangle -- see the handoff. Do not reach for another margin fudge.
    r51 = ball_r()
    pc51, cap51 = capture_points()[0]
    ang51 = math.atan2(0.455 - pc51[1], 0.91 - pc51[0])
    in_pocket51 = can_place_ball(
        (pc51[0] + math.cos(ang51) * cap51 * 0.5,
         pc51[1] + math.sin(ang51) * cap51 * 0.5), [], r51, [])
    # mid-table, against the bottom rail: centre 15mm out is INSIDE the cushion
    embedded51 = can_place_ball((0.91, 0.015), [], r51, [])
    clear51 = can_place_ball((0.91, 0.455), [], r51, [])      # open table: fine
    check("r22 placement invariants — a ball can never be placed inside a "
          "pocket's capture zone, nor embedded in a rail (the mouth-exemption "
          "attempt broke the latter and was reverted)",
          (not in_pocket51) and (not embedded51) and clear51,
          f"in-pocket={in_pocket51}, embedded-in-rail={embedded51}, "
          f"open-table={clear51}")

    print(f"selftest: {'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'}")
    return failures == 0

    print(f"selftest: {'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'}")
    return failures == 0


def batch(n):
    print(f"HUSTLER batch — {n} random strikes (headless, real units)")
    rng = random.Random()
    pots = 0
    cue_scratches = 0
    rest_times = []
    escapes = 0
    for _ in range(n):
        sim = Sim()
        for _ in range(rng.randint(2, 6)):
            sim.add_random_ball(rng)
        ang = rng.uniform(0, 2 * math.pi)
        sim.strike((math.cos(ang), math.sin(ang)),
                   rng.uniform(CFG["POWER_MIN"], CFG["POWER_MAX"]),
                   side=rng.uniform(-1, 1), follow=rng.uniform(-1, 1))
        t = sim.run_to_rest()
        rest_times.append(t)
        potted = sim.potted_colours()
        pots += sum(1 for c in potted if c != "cue")
        cue_scratches += sum(1 for c in potted if c == "cue")
        if not sim.in_bounds():
            escapes += 1
    avg = sum(rest_times) / max(1, len(rest_times))
    print(f"  strikes            : {n}")
    print(f"  object balls potted: {pots}")
    print(f"  cue scratches      : {cue_scratches}")
    print(f"  avg time to rest   : {avg:.1f}s (sim)")
    print(f"  max time to rest   : {max(rest_times):.1f}s (sim)")
    print(f"  containment escapes: {escapes}")
    return escapes == 0


def main():
    ap = argparse.ArgumentParser(description="HUSTLER — UK pool physics sandbox (R6)")
    ap.add_argument("--selftest", action="store_true", help="run headless assertions")
    ap.add_argument("--batch", type=int, metavar="N", help="run N random strikes headless")
    ap.add_argument("--breaks", type=int, metavar="N", help="break analyser, N trials per config")
    ap.add_argument("--aigame", type=int, metavar="N", help="run N headless AI vs AI games")
    ap.add_argument("--jsonl", metavar="FILE",
                    help="with --aigame: write a per-shot study log, one game "
                         "per line, for external analysis")
    ap.add_argument("--seed", type=int, default=1000, metavar="S",
                    help="base RNG seed for --aigame (game i uses S+i), so a "
                         "study is reproducible")
    ap.add_argument("--smoke", action="store_true", help="GUI smoke on dummy video driver")
    ap.add_argument("--snap", metavar="FILE", help="headless smoke run, save screenshot PNG")
    ap.add_argument("--sound-probe", nargs="?", const=".", metavar="DIR",
                    help="write every sound voice to WAV (no mixer, no game) "
                         "so they can be auditioned directly")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if args.sound_probe:
        sound_probe(args.sound_probe)
        sys.exit(0)
    if args.batch:
        sys.exit(0 if batch(args.batch) else 1)
    if args.breaks:
        sys.exit(0 if break_analysis(args.breaks) else 1)
    if args.aigame:
        sys.exit(0 if aigame_batch(args.aigame, jsonl=args.jsonl,
                                   seed=args.seed) else 1)
    if args.snap:
        frames = run_gui(smoke=True, smoke_frames=90, snap_path=args.snap)
        print(f"smoke: rendered {frames} frames OK")
        sys.exit(0)
    if args.smoke:
        frames = run_gui(smoke=True)
        print(f"smoke: rendered {frames} frames OK")
        sys.exit(0)
    run_gui()


if __name__ == "__main__":
    main()
