#!/usr/bin/env python3
"""
HUSTLER — UK Pool Physics Sandbox (R5)
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
  Mouse         aim (cue ball -> pointer)
  SPACE         strike (only when all balls are at rest and it is a human turn)
  UP / DOWN     power +/- 0.25 m/s (0.5 .. 7.0)
  W / S         follow / draw, top spin / backspin (+/- 0.25, clamp +/-1.0)
  A / D         side spin, left / right english (+/- 0.25, clamp +/-1.0)
  X             reset spin to centre-ball
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

Command line:
  (none)        interactive classic window
  --gl          interactive window through the GL pipeline (2x SSAA + bloom)
  --classic     force the classic renderer (overrides --gl)
  --selftest    headless assertion suite
  --batch N     N random strikes, containment report
  --breaks N    break analyser, N trials per config
  --aigame N    N headless AI-vs-AI games
  --smoke       GUI smoke on the dummy video driver (classic)
  --smoke-gl    headless GL render gate (passthrough + SSAA + bloom probes)
  --snap FILE   headless render, save a screenshot PNG (add --smoke-gl for GL)
"""

import argparse
import math
import os
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


def capture_points():
    """
    Pocket capture points: (centre, radius) per pocket, inside the throat.
    A ball must genuinely enter the mouth to drop. Shared by simulation,
    assessor and drill so there is a single source of truth.
    """
    x0, y0, x1, y1 = play_rect()
    pr = pocket_half_mouth()
    mx = (x0 + x1) / 2.0
    s2 = math.sqrt(2.0) / 2.0
    pts = []
    for (c, o) in [((x0, y0), (-s2, -s2)), ((x1, y0), (s2, -s2)),
                   ((x0, y1), (-s2, s2)), ((x1, y1), (s2, s2))]:
        pts.append(((c[0] + o[0] * pr * 0.5, c[1] + o[1] * pr * 0.5), pr * 0.8))
    prm = pocket_middle_half_mouth()
    pts.append(((mx, y0 - prm * 0.6), prm * 0.7))
    pts.append(((mx, y1 + prm * 0.6), prm * 0.7))
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


def corridor_clear(a, b, clearance, obstacles):
    """True if no obstacle centre lies within `clearance` of segment ab.
    Used by the AI to check the cue path and the object-ball path."""
    return all(seg_point_dist(a, b, ob) >= clearance for ob in obstacles)


def pot_estimate(cp, t, pc, cap_r, r_cue, r_obj, jitter):
    """Analytic pot-chance estimate for a cue ball at cp potting the ball at
    t into pocket capture point pc: ghost-ball aim, pocket acceptance angle
    narrowed by cut thinness, distance decay. Single source of truth shared
    by the AI's shot choice and its leave-quality assessment (R5).
    Returns None if the shot is degenerate or the cut too thin."""
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
    allowed = tol * max(fullness, 0.15)   # thin cuts amplify error
    p = math.exp(-0.5 * (jitter / max(allowed, 1e-5)) ** 2)
    p *= math.exp(-t_cue / 10.0)
    return {"p": p, "aim": aim, "ghost": G, "ad": ad, "od": od,
            "fullness": fullness, "t_cue": t_cue, "d_tp": d_tp}


def estimate_leave(est, power):
    """Analytic cue-ball leave (R5, decision A3): estimated rest position of
    the cue ball after the pot described by `est` (a pot_estimate dict),
    struck at `power` m/s. Model: constant-decel approach to contact,
    tangent-line deflection scaled by cut thinness, a small carry along the
    aim line on full hits (negative — the 94 g cue rebounds), constant-decel
    travel with at most one cushion reflection at reduced energy. Pure
    geometry, no simulation. An estimate, not a promise."""
    a = CFG["ROLL_DECEL"]
    v2 = max(0.0, power * power - 2.0 * a * est["t_cue"])
    v_c = math.sqrt(v2)
    f = est["fullness"]
    ad, od = est["ad"], est["od"]
    tvx, tvy = ad[0] - f * od[0], ad[1] - f * od[1]
    tn = math.hypot(tvx, tvy)
    v_tan = v_c * math.sqrt(max(0.0, 1.0 - f * f)) * CFG["LEAVE_TANGENT_KEEP"]
    v_fwd = v_c * f * f * CFG["LEAVE_CUE_CARRY"]
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
        rest = (hit[0] + d2[0] * rem, hit[1] + d2[1] * rem)
        x0, y0, x1, y1 = play_rect()
        rest = (min(max(rest[0], x0 + r), x1 - r),
                min(max(rest[1], y0 + r), y1 - r))   # clamp beyond one bounce
    return {"rest": rest, "speed": s}


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
            if not corridor_clear(rest, est["ghost"], r_cue + r_obj - 0.002, obs):
                continue
            if not corridor_clear(t, pc, 2 * r_obj - 0.006, obs):
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
        self._live_side = 0.0
        self._live_follow = 0.0
        self._cue_prev = (0.0, 0.0)
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
        self._build_cushions()
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

    def step(self, dt):
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
        pots = []
        for bid, (body, _) in list(self.balls.items()):
            for (pc, cap_r) in capture_points():
                if math.dist(body.position, pc) < cap_r:
                    pots.append(bid)
                    break
        for bid in pots:
            body, shape = self.balls.pop(bid)
            self.space.remove(body, shape)
            self.potted_log.append(bid)
            if bid == self.CUE_ID:
                # Sandbox/rules-lite behaviour: respot behind baulk, nudged
                self._live_side = 0.0
                self._live_follow = 0.0
                self._respot_cue()

    # -- spin callbacks (pymunk post_solve) -----------------------------------
    def _cue_ball_contact(self, arbiter, space, data):
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

    def _cue_cushion_contact(self, arbiter, space, data):
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
        return [self.colours.get(b, "?") for b in self.potted_log]


# ----------------------------------------------------------------------------
# Rules-lite blackball (decision 1B)
# ----------------------------------------------------------------------------
class Game:
    """Rules-lite blackball state machine.

    Covered: turn order; colour assignment on first potted colour (open
    table); pot-your-colour-to-continue; scratch = foul, cue respotted
    behind baulk, turn passes; black legal only once your colour is cleared
    BEFORE the shot; potting the black early (or with a scratch) loses.
    Deliberately not covered (rules-lite): free shots, two-visit penalties,
    wrong-ball-first fouls, re-racks. Logged for a future full-rules pass.
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

    def own_colour(self, i=None):
        return self.colours.get(self.current if i is None else i)

    def legal_colours(self, sim):
        """Colours the current striker may target."""
        own = self.own_colour()
        if own is None:
            return ["red", "yellow"]
        if sim.remaining(own) == 0:
            return ["black"]
        return [own]

    def on_rest(self, sim):
        """Apply rules-lite to the shot just completed (sim.potted_log)."""
        if self.over:
            return
        self.shots += 1
        striker = self.current
        potted = sim.potted_colours()
        scratch = "cue" in potted
        obj = [c for c in potted if c in ("red", "yellow")]
        own = self.colours.get(striker)

        if "black" in potted:
            # Legal only if own colour was cleared BEFORE this shot and no
            # scratch accompanied it.
            legal = (own is not None and sim.remaining(own) == 0
                     and not any(c == own for c in obj) and not scratch)
            self.over = True
            self.winner = striker if legal else 1 - striker
            self.reason = ("black potted cleanly" if legal
                           else "black potted illegally")
            self.last_event = f"{self.names[self.winner]} wins: {self.reason}"
            return

        if not self.colours and obj:
            first = obj[0]
            other = "yellow" if first == "red" else "red"
            self.colours = {striker: first, 1 - striker: other}
            own = first
            self.last_event = f"{self.names[striker]} is {first.upper()}S"

        if scratch:
            self.fouls += 1
            self.last_event = "scratch — cue respotted"

        keep_going = (not scratch) and own is not None and any(c == own for c in obj)
        if obj and not scratch and not keep_going:
            self.last_event = "potted opponent's colour"
        if not keep_going:
            self.current = 1 - striker
            self.visits += 1


# ----------------------------------------------------------------------------
# Geometric utility AI (decision 2A) — judgement from scores, never scripted
# ----------------------------------------------------------------------------
class PoolAI:
    """Evaluates every legal (ball, pocket) pot via ghost-ball geometry,
    corridor clearance and an analytic success estimate. Candidates that
    beat the confidence threshold are ranked by utility
        u = p_pot x ((1 - greed) + greed x leave_quality)
    where leave_quality is the best analytic next-shot chance from the
    estimated cue-ball rest position (R5). greed=0 reproduces the R4
    pot-chance-only behaviour exactly. If nothing beats the threshold,
    a soft safety is played on the nearest legal ball. Aim jitter is
    applied at execution so hard shots genuinely miss more often.
    Personality comes only from the numbers."""

    def __init__(self, name, aim_jitter=0.010, threshold=0.15, greed=0.0,
                 rng=None):
        self.name = name
        self.aim_jitter = aim_jitter     # radians (sigma)
        self.threshold = threshold       # minimum estimated pot chance
        self.greed = greed               # 0 = pure pot chance, 1 = position-led
        self.rng = rng or random.Random()

    def choose(self, sim, legal_colours):
        cue = sim.cue()
        if cue is None:
            return None
        cp = (cue.position.x, cue.position.y)
        rc, ro = CFG["CUE_R_M"], ball_r()
        targets = [(bid, tuple(b.position)) for bid, (b, _) in sim.balls.items()
                   if bid != Sim.CUE_ID and sim.colours.get(bid) in legal_colours]
        if not targets:
            return None
        all_pos = {bid: tuple(b.position) for bid, (b, _) in sim.balls.items()}
        best = None
        for (bid, t) in targets:
            others = [p for k, p in all_pos.items()
                      if k not in (bid, Sim.CUE_ID)]
            for (pc, cap_r) in capture_points():
                est = pot_estimate(cp, t, pc, cap_r, rc, ro, self.aim_jitter)
                if est is None:
                    continue
                if not corridor_clear(cp, est["ghost"], rc + ro - 0.002, others):
                    continue      # cue path blocked
                if not corridor_clear(t, pc, 2 * ro - 0.006, others):
                    continue      # object path blocked
                p = est["p"]
                if p < self.threshold:
                    continue      # not confident enough to attempt
                d = est["t_cue"] + est["d_tp"]
                leave = 0.5       # neutral when position is not evaluated
                if self.greed > 0.0:
                    rem = [q for (qid, q) in targets if qid != bid]
                    if rem:
                        lv = estimate_leave(est, min(3.5, 1.0 + 1.1 * d))
                        leave = leave_quality(lv["rest"], rem, others,
                                              rc, ro, self.aim_jitter)
                u = p * ((1.0 - self.greed) + self.greed * leave)
                if best is None or u > best["u"]:
                    best = {"type": "pot", "aim": est["aim"], "p": p, "u": u,
                            "leave": leave, "target": t, "ghost": est["ghost"],
                            "pocket": pc, "d": d}
        if best is not None:
            power = min(3.5, 1.0 + 1.1 * best["d"])
            return self._execute(best, power)
        # Safety: soft roll onto the nearest legal ball
        (bid, t) = min(targets, key=lambda kv: math.dist(cp, kv[1]))
        aim = (t[0] - cp[0], t[1] - cp[1])
        return self._execute({"type": "safety", "aim": aim, "p": 0.0,
                              "u": 0.0, "leave": 0.0,
                              "target": t, "ghost": t, "pocket": None,
                              "d": math.hypot(*aim)}, 1.0)

    def _execute(self, shot, power):
        ang = math.atan2(shot["aim"][1], shot["aim"][0])
        ang += self.rng.gauss(0.0, self.aim_jitter)
        shot["aim"] = (math.cos(ang), math.sin(ang))
        shot["power"] = max(CFG["POWER_MIN"],
                            power * (1.0 + self.rng.gauss(0.0, 0.02)))
        return shot


def new_game(controllers=("ai", "ai"), names=("SHARK", "STEADY")):
    """Fresh racked game: returns (sim, game)."""
    sim = Sim(layout="empty")
    sim._respot_cue()
    sim.rack()
    return sim, Game(names=names, controllers=controllers)


def default_ais(rng=None):
    """Two distinguishable players from parameters alone: SHARK aims truer,
    attempts more and plays for position (greed 0.55); STEADY jitters more,
    demands a better chance and takes the surest pot (greed 0.25)."""
    rng = rng or random.Random()
    return [PoolAI("SHARK", aim_jitter=0.008, threshold=0.10, greed=0.55, rng=rng),
            PoolAI("STEADY", aim_jitter=0.014, threshold=0.18, greed=0.25, rng=rng)]


def play_ai_game(seed=0, max_shots=300, verbose=False):
    """Headless AI-vs-AI game. Returns a result record."""
    rng = random.Random(seed)
    sim, game = new_game()
    ais = default_ais(rng)
    # Player 0 breaks
    sim.break_shot(power=6.0 * rng.gauss(1.0, 0.02),
                   aim_off=rng.gauss(0.0, 0.0015))
    sim.run_to_rest()
    game.on_rest(sim)
    safeties = 0
    while not game.over and game.shots < max_shots:
        ai = ais[game.current]
        shot = ai.choose(sim, game.legal_colours(sim))
        if shot is None:
            break
        if shot["type"] == "safety":
            safeties += 1
        if verbose:
            print(f"    shot {game.shots:3d}: {ai.name:6s} {shot['type']:6s} "
                  f"p={shot['p']:.2f} pow={shot['power']:.2f}")
        sim.strike(shot["aim"], shot["power"])
        sim.run_to_rest()
        game.on_rest(sim)
    return {"over": game.over, "winner": game.winner,
            "winner_name": game.names[game.winner] if game.winner is not None else "-",
            "reason": game.reason, "shots": game.shots, "visits": game.visits,
            "fouls": game.fouls, "safeties": safeties}


def aigame_batch(n):
    print(f"HUSTLER AI vs AI — {n} headless game(s)")
    wins = {"SHARK": 0, "STEADY": 0}
    incomplete = 0
    for i in range(n):
        rec = play_ai_game(seed=1000 + i)
        if rec["over"]:
            wins[rec["winner_name"]] += 1
        else:
            incomplete += 1
        print(f"  game {i+1:2d}: {'winner ' + rec['winner_name'] if rec['over'] else 'NO RESULT':18s}"
              f"  ({rec['reason'] or 'shot cap reached'})  shots {rec['shots']:3d}"
              f"  visits {rec['visits']:3d}  fouls {rec['fouls']}  safeties {rec['safeties']}")
    print(f"  totals: SHARK {wins['SHARK']} — {wins['STEADY']} STEADY"
          f"{'' if not incomplete else f'  ({incomplete} incomplete)'}")
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
# GL post-processing (Graphics Pass 3 — decision 1C + 2A, Increment 1)
# ----------------------------------------------------------------------------
# An offscreen OpenGL post-process pipeline that consumes a finished pygame
# frame (the SAME surface the classic backend draws) and returns a processed
# pygame frame. Increment 1 ships the plumbing only: a passthrough shader, so
# the upload -> sample -> read-back round-trip is proven inside the real app
# before any bloom/grade/vignette passes are added (each future effect is an
# extra pass with its own pixel-probe, per finding 6.10).
#
# Feasibility (headless EGL probe, banked): a standalone EGL context on
# llvmpipe gives GL 4.5 Core / GLSL 4.50, half-float FBOs, and a pixel-exact
# RGBA round-trip with NO vertical flip. Two hard-won facts baked in here:
#   * glcontext defaults to X11/GLX and dies headless — backend='egl' is
#     forced explicitly (this is what makes the CI --smoke-gl gate possible).
#   * pygame is top-row-first and GL texel row 0 is bottom, but tostring ->
#     texture.write -> fbo.read -> fromstring cancels the flip: passthrough is
#     upright and identical. The --smoke-gl gate asserts exactly this.
#
# moderngl is imported LAZILY, only when a GL backend is actually constructed,
# so the core chain (py_compile/--selftest/--batch/--smoke) keeps zero new
# dependencies and the container gate is unaffected unless --smoke-gl is run.

_GL_PASSTHROUGH_VS = """
#version 330
in vec2 in_pos;
out vec2 uv;
void main() {
    uv = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

_GL_PASSTHROUGH_FS = """
#version 330
uniform sampler2D src;
in vec2 uv;
out vec4 frag;
// The scene frame is an opaque presentation surface; its alpha slot is the
// unused X-byte of the window's XRGB format and is meaningless. Force opaque
// so the pipeline is alpha-defined (matters once bloom/grade passes read a).
void main() { frag = vec4(texture(src, uv).rgb, 1.0); }
"""

# Bright-pass: keep only pixels whose luminance clears the threshold, with a
# soft knee so the bloom fades in rather than hard-clipping. Below threshold
# -> black, so a dark frame produces no glow (bloom never manufactures light).
_GL_BRIGHT_FS = """
#version 330
uniform sampler2D src;
uniform float threshold;
uniform float knee;
in vec2 uv;
out vec4 frag;
void main() {
    vec3 c = texture(src, uv).rgb;
    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
    float k = smoothstep(threshold, threshold + knee, l);
    frag = vec4(c * k, 1.0);
}
"""

# Separable Gaussian (9-tap). Run once horizontal, once vertical; `dir` is the
# per-sample texel step for the axis being blurred.
_GL_BLUR_FS = """
#version 330
uniform sampler2D src;
uniform vec2 dir;
in vec2 uv;
out vec4 frag;
const float w0 = 0.227027;
const float w1 = 0.1945946;
const float w2 = 0.1216216;
const float w3 = 0.054054;
const float w4 = 0.016216;
void main() {
    vec3 c = texture(src, uv).rgb * w0;
    c += texture(src, uv + dir * 1.0).rgb * w1;
    c += texture(src, uv - dir * 1.0).rgb * w1;
    c += texture(src, uv + dir * 2.0).rgb * w2;
    c += texture(src, uv - dir * 2.0).rgb * w2;
    c += texture(src, uv + dir * 3.0).rgb * w3;
    c += texture(src, uv - dir * 3.0).rgb * w3;
    c += texture(src, uv + dir * 4.0).rgb * w4;
    c += texture(src, uv - dir * 4.0).rgb * w4;
    frag = vec4(c, 1.0);
}
"""

# Composite: scene + intensity * bloom, opaque. Bloom is sampled from a
# half-res texture (linear-upscaled), which widens the glow for free.
_GL_COMPOSITE_FS = """
#version 330
uniform sampler2D scene;
uniform sampler2D bloom;
uniform float intensity;
in vec2 uv;
out vec4 frag;
void main() {
    vec3 s = texture(scene, uv).rgb;
    vec3 b = texture(bloom, uv).rgb;
    frag = vec4(s + intensity * b, 1.0);
}
"""

# Bloom presets (Increment 2 default = BALANCED). Live-tunable later.
BLOOM_SUBTLE   = {"threshold": 0.85, "knee": 0.10, "intensity": 0.35}
BLOOM_BALANCED = {"threshold": 0.78, "knee": 0.12, "intensity": 0.60}
BLOOM_ARCADE   = {"threshold": 0.68, "knee": 0.16, "intensity": 0.95}
# intensity 0 with an out-of-range threshold = resolve only (no bloom added);
# used to pixel-probe the SSAA downsample in isolation.
BLOOM_RESOLVE_ONLY = {"threshold": 2.0, "knee": 0.10, "intensity": 0.0}


class GLPostProcessor:
    """Offscreen GL post-processor: pygame Surface in, pygame Surface out.

    Two modes, chosen by the constructor:
      * passthrough (bloom=None, in==out): the Increment 1 round-trip, kept for
        the pixel-exactness gate.
      * pipeline (bloom set, in usually 2x out): SSAA resolve (2x->1x box via
        linear downsample) -> bright-pass -> separable Gaussian (half-res) ->
        additive composite. This is the Increment 2 spectacle path.

    Constructing this triggers the lazy moderngl import and an EGL standalone
    context; GLUnavailable is raised (readably) if that can't be created, so
    callers SKIP rather than crash. All post-process passes output opaque
    alpha (the frame is an opaque presentation surface; see finding on the
    XRGB alpha slot).
    """

    def __init__(self, in_w, in_h, out_w=None, out_h=None, bloom=None):
        self.in_w, self.in_h = in_w, in_h
        self.out_w = out_w or in_w
        self.out_h = out_h or in_h
        self.bloom = bloom
        try:
            import moderngl  # lazy — only when GL is actually requested
        except Exception as e:  # pragma: no cover - env dependent
            raise GLUnavailable(f"moderngl import failed: {e}")
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
        self._mgl = moderngl
        ctx = None
        last = None
        for kw in ({"backend": "egl"}, {"backend": "egl", "device_index": 0}):
            try:
                ctx = moderngl.create_standalone_context(require=330, **kw)
                break
            except Exception as e:
                last = e
        if ctx is None:
            raise GLUnavailable(f"EGL standalone context unavailable: {last}")
        self.ctx = ctx
        self.renderer = ctx.info.get("GL_RENDERER", "?")
        import numpy as np
        verts = np.array([-1, -1, 3, -1, -1, 3], dtype="f4")
        self.vbo = ctx.buffer(verts.tobytes())
        self._vaos = []
        self._objs = [self.vbo]

        LIN = (moderngl.LINEAR, moderngl.LINEAR)
        NEAR = (moderngl.NEAREST, moderngl.NEAREST)

        def prog(fs):
            p = ctx.program(vertex_shader=_GL_PASSTHROUGH_VS, fragment_shader=fs)
            self._objs.append(p)
            return p

        def vao(p):
            v = ctx.vertex_array(p, [(self.vbo, "2f", "in_pos")])
            self._vaos.append(v)
            self._objs.append(v)
            return v

        def tex(size, comp=4, dt="f1", filt=LIN):
            t = ctx.texture(size, comp, dtype=dt)
            t.filter = filt
            self._objs.append(t)
            return t

        def fbo(t):
            f = ctx.framebuffer(color_attachments=[t])
            self._objs.append(f)
            return f

        if bloom is None:
            # Passthrough: NEAREST input so an in==out round-trip is bit-exact.
            self.tex_in = tex((in_w, in_h), filt=NEAR)
            self.tex_out = tex((self.out_w, self.out_h))
            self.fbo_out = fbo(self.tex_out)
            self.prog_pass = prog(_GL_PASSTHROUGH_FS)
            self.vao_pass = vao(self.prog_pass)
            return

        # Pipeline. LINEAR input so the resolve downsample box-averages.
        ow, oh = self.out_w, self.out_h
        hw, hh = max(1, ow // 2), max(1, oh // 2)
        self.hw, self.hh = hw, hh
        self.tex_in = tex((in_w, in_h), filt=LIN)
        self.tex_scene = tex((ow, oh), dt="f2")          # HDR scene (resolved)
        self.tex_bright = tex((hw, hh), dt="f2")
        self.tex_blur1 = tex((hw, hh), dt="f2")
        self.tex_blur2 = tex((hw, hh), dt="f2")
        self.tex_out = tex((ow, oh))                     # 8-bit for display
        self.fbo_scene = fbo(self.tex_scene)
        self.fbo_bright = fbo(self.tex_bright)
        self.fbo_blur1 = fbo(self.tex_blur1)
        self.fbo_blur2 = fbo(self.tex_blur2)
        self.fbo_out = fbo(self.tex_out)
        self.prog_resolve = prog(_GL_PASSTHROUGH_FS)
        self.prog_bright = prog(_GL_BRIGHT_FS)
        self.prog_blur = prog(_GL_BLUR_FS)
        self.prog_comp = prog(_GL_COMPOSITE_FS)
        self.vao_resolve = vao(self.prog_resolve)
        self.vao_bright = vao(self.prog_bright)
        self.vao_blur = vao(self.prog_blur)
        self.vao_comp = vao(self.prog_comp)

    def process(self, surface):
        """Run the pipeline on a pygame Surface, return a new pygame Surface."""
        import pygame
        mgl = self._mgl
        data = pygame.image.tostring(surface, "RGBA", False)  # top-row first
        self.tex_in.write(data)

        if self.bloom is None:
            self.fbo_out.use()
            self.ctx.clear(0.0, 0.0, 0.0, 1.0)
            self.tex_in.use(0)
            self.prog_pass["src"].value = 0
            self.vao_pass.render(mgl.TRIANGLES)
            out = self.fbo_out.read(components=4, dtype="f1")
            return pygame.image.fromstring(out, (self.out_w, self.out_h),
                                           "RGBA", False)

        b = self.bloom
        # 1. Resolve 2x -> 1x (linear downsample = box average over the 2x2).
        self.fbo_scene.use()
        self.ctx.clear()
        self.tex_in.use(0)
        self.prog_resolve["src"].value = 0
        self.vao_resolve.render(mgl.TRIANGLES)
        # 2. Bright-pass (half-res).
        self.fbo_bright.use()
        self.ctx.clear()
        self.tex_scene.use(0)
        self.prog_bright["src"].value = 0
        self.prog_bright["threshold"].value = float(b["threshold"])
        self.prog_bright["knee"].value = float(b["knee"])
        self.vao_bright.render(mgl.TRIANGLES)
        # 3. Separable Gaussian: horizontal then vertical.
        self.fbo_blur1.use()
        self.ctx.clear()
        self.tex_bright.use(0)
        self.prog_blur["src"].value = 0
        self.prog_blur["dir"].value = (1.0 / self.hw, 0.0)
        self.vao_blur.render(mgl.TRIANGLES)
        self.fbo_blur2.use()
        self.ctx.clear()
        self.tex_blur1.use(0)
        self.prog_blur["dir"].value = (0.0, 1.0 / self.hh)
        self.vao_blur.render(mgl.TRIANGLES)
        # 4. Composite scene + intensity * bloom.
        self.fbo_out.use()
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)
        self.tex_scene.use(0)
        self.tex_blur2.use(1)
        self.prog_comp["scene"].value = 0
        self.prog_comp["bloom"].value = 1
        self.prog_comp["intensity"].value = float(b["intensity"])
        self.vao_comp.render(mgl.TRIANGLES)
        out = self.fbo_out.read(components=4, dtype="f1")
        return pygame.image.fromstring(out, (self.out_w, self.out_h),
                                       "RGBA", False)

    def release(self):
        for o in reversed(self._objs):
            try:
                o.release()
            except Exception:
                pass
        try:
            self.ctx.release()
        except Exception:
            pass


class GLUnavailable(RuntimeError):
    """Raised when an offscreen GL context cannot be created in this env."""


def gl_passthrough_check():
    """Pixel-probe the GL passthrough round-trip (finding 6.10 doctrine).

    Builds a deterministic synthetic frame, runs it through GLPostProcessor,
    and asserts the result is bit-identical to the input. Returns
    (ok, detail, available) so callers can PASS/FAIL when GL is present and
    SKIP when it is not.
    """
    try:
        import pygame
        import numpy as np
    except Exception as e:
        return (False, f"pygame/numpy missing: {e}", False)
    try:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()
        w, h = 96, 64
        # Deterministic content: gradients + a fixed noise block + hard edges,
        # so a vertical flip or channel swap would be caught, not averaged out.
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        xr = (np.linspace(0, 255, w)).astype(np.uint8)
        yr = (np.linspace(0, 255, h)).astype(np.uint8)
        arr[:, :, 0] = xr[None, :]
        arr[:, :, 1] = yr[:, None]
        arr[:, :, 2] = 64
        arr[:, :, 3] = 255
        rng = np.random.default_rng(6102)
        arr[8:24, 8:24, :3] = rng.integers(0, 256, (16, 16, 3), dtype=np.uint8)
        arr[0, :, :3] = (255, 0, 0)      # top row marker (catches a flip)
        arr[h - 1, :, :3] = (0, 0, 255)  # bottom row marker
        surf = pygame.image.frombytes(arr.tobytes(), (w, h), "RGBA")
    except Exception as e:
        return (False, f"synthetic frame build failed: {e}", True)
    try:
        gl = GLPostProcessor(w, h)
    except GLUnavailable as e:
        return (False, str(e), False)
    except Exception as e:
        return (False, f"GL init error: {e}", False)
    try:
        out = gl.process(surf)
        back = np.frombuffer(pygame.image.tostring(out, "RGBA", False),
                             dtype=np.uint8).reshape(h, w, 4)
        exact = np.array_equal(back, arr)
        maxerr = int(np.abs(back.astype(int) - arr.astype(int)).max())
        top_ok = tuple(back[0, w // 2, :3]) == (255, 0, 0)
        detail = (f"{gl.renderer}; max abs err {maxerr}, "
                  f"orientation {'upright' if top_ok else 'FLIPPED'}")
        return (exact and top_ok, detail, True)
    except Exception as e:
        return (False, f"process/compare error: {e}", True)
    finally:
        gl.release()


def _luma(arr):
    import numpy as np
    return (arr[..., :3].astype(float) *
            np.array([0.2126, 0.7152, 0.0722])).sum(-1)


def gl_ssaa_check():
    """Pixel-probe the 2x->1x SSAA resolve in isolation (bloom off).

    Builds a 2x frame where each 2x2 block averages a known target T, but its
    four subpixels are T+/-64 — so a broken resolve (nearest, or a wrong
    filter) lands on T+/-64, not T. Passing means the downsample truly box-
    averages. Returns (ok, detail, available).
    """
    try:
        import pygame
        import numpy as np
    except Exception as e:
        return (False, f"pygame/numpy missing: {e}", False)
    try:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()
        ow, oh = 6, 5
        iw, ih = ow * 2, oh * 2
        T = np.zeros((oh, ow), dtype=float)
        for Y in range(oh):
            for X in range(ow):
                T[Y, X] = 80 + 15 * X + 10 * Y      # in [80,155], +/-64 safe
        arr = np.zeros((ih, iw, 4), dtype=np.uint8)
        arr[:, :, 3] = 255
        for Y in range(oh):
            for X in range(ow):
                blk = np.array([[T[Y, X] + 64, T[Y, X] - 64],
                                [T[Y, X] + 64, T[Y, X] - 64]])
                blk = np.clip(blk, 0, 255).astype(np.uint8)
                for c in range(3):
                    arr[2 * Y:2 * Y + 2, 2 * X:2 * X + 2, c] = blk
        surf = pygame.image.frombytes(arr.tobytes(), (iw, ih), "RGBA")
    except Exception as e:
        return (False, f"synthetic frame build failed: {e}", True)
    try:
        gl = GLPostProcessor(iw, ih, ow, oh, bloom=BLOOM_RESOLVE_ONLY)
    except GLUnavailable as e:
        return (False, str(e), False)
    except Exception as e:
        return (False, f"GL init error: {e}", False)
    try:
        out = gl.process(surf)
        back = np.frombuffer(pygame.image.tostring(out, "RGBA", False),
                             dtype=np.uint8).reshape(oh, ow, 4)
        got = back[:, :, 0].astype(float)
        err = float(np.abs(got - T).max())
        return (err <= 3.0, f"{gl.renderer}; max resolve err {err:.1f} "
                f"(box-average target, tol 3)", True)
    except Exception as e:
        return (False, f"process/compare error: {e}", True)
    finally:
        gl.release()


def gl_bloom_check():
    """Pixel-probe the bloom pass: a bright core glows outward, a black frame
    stays black (no light from nothing), and the core survives. Returns
    (ok, detail, available)."""
    try:
        import pygame
        import numpy as np
    except Exception as e:
        return (False, f"pygame/numpy missing: {e}", False)
    try:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()
        ow, oh = 32, 24
        iw, ih = ow * 2, oh * 2
        cx, cy = iw // 2, ih // 2
        dot = np.zeros((ih, iw, 4), dtype=np.uint8)
        dot[:, :, 3] = 255
        dot[cy - 6:cy + 6, cx - 6:cx + 6, :3] = 255     # bright core on black
        black = np.zeros((ih, iw, 4), dtype=np.uint8)
        black[:, :, 3] = 255
        s_dot = pygame.image.frombytes(dot.tobytes(), (iw, ih), "RGBA")
        s_black = pygame.image.frombytes(black.tobytes(), (iw, ih), "RGBA")
    except Exception as e:
        return (False, f"synthetic frame build failed: {e}", True)
    try:
        gl = GLPostProcessor(iw, ih, ow, oh, bloom=BLOOM_BALANCED)
    except GLUnavailable as e:
        return (False, str(e), False)
    except Exception as e:
        return (False, f"GL init error: {e}", False)
    try:
        ob = np.frombuffer(pygame.image.tostring(gl.process(s_dot), "RGBA",
                           False), dtype=np.uint8).reshape(oh, ow, 4)
        okk = np.frombuffer(pygame.image.tostring(gl.process(s_black), "RGBA",
                            False), dtype=np.uint8).reshape(oh, ow, 4)
        lum = _luma(ob)
        ocx, ocy = ow // 2, oh // 2
        core = lum[ocy, ocx]
        # A ring well outside the core footprint (core ~ +/-3 px at 1x).
        ring = lum[ocy - 8:ocy - 6, ocx - 1:ocx + 1].mean()
        black_max = int(okk[:, :, :3].max())
        ok = core > 200 and ring > 4.0 and black_max == 0
        return (ok, f"{gl.renderer}; core {core:.0f}, glow-ring {ring:.1f} "
                f"(>4), black-frame max {black_max} (==0)", True)
    except Exception as e:
        return (False, f"process/compare error: {e}", True)
    finally:
        gl.release()


def run_gui(smoke=False, smoke_frames=90, snap_path=None, backend="classic"):
    if smoke:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.init()
    # Render scale (Graphics Pass 3, Increment 2): the GL backend draws the
    # scene at RS=2 (true supersampling) and the pipeline resolves 2x->1x with
    # a box filter before bloom. Classic stays RS=1, so every *RS below is a
    # no-op and the classic frame is byte-identical to R6.1. The window is
    # always 1x (W1,H1); only the offscreen frame is scaled.
    RS = 2 if backend == "gl" else 1
    PXM = CFG["PX_PER_M"]
    MG = CFG["MARGIN_PX"]
    x0, y0, x1, y1 = play_rect()
    W1 = int(x1 * PXM + 2 * MG)
    H1 = int(y1 * PXM + 2 * MG + 46)
    W, H = W1 * RS, H1 * RS          # exact 2:1 so the resolve is a clean box
    S = PXM * RS
    M = MG * RS
    display = pygame.display.set_mode((W1, H1))
    pygame.display.set_caption("HUSTLER — UK pool physics sandbox (R3)")
    # Renderer split (decision 2A): the scene always draws to an offscreen
    # frame surface — the single source both backends consume. Classic blits it
    # straight to the window; GL runs it through the post-process pipeline
    # (resolve -> bloom) first. The whole draw loop still targets `screen`.
    screen = pygame.Surface((W, H))
    glpp = None
    if backend == "gl":
        glpp = GLPostProcessor(W, H, W1, H1, bloom=BLOOM_BALANCED)

    def present(frame):
        return glpp.process(frame) if glpp is not None else frame

    try:
        font = pygame.font.SysFont("consolas,menlo,monospace", 14 * RS)
    except Exception:
        font = pygame.font.Font(None, 16 * RS)
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
    frames = 0
    running = True
    last_shown = screen
    def start_game(m):
        controllers = ("human", "ai") if m == 1 else ("ai", "ai")
        names = ("YOU", "SHARK") if m == 1 else ("SHARK", "STEADY")
        s, g = new_game(controllers=controllers, names=names)
        return s, g, default_ais()

    if smoke:
        mode = 2
        sim, game, ais = start_game(mode)
        sim.break_shot(power=6.0)
        pending = True
        spin_side, spin_follow = -0.5, 0.5

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                shift = ev.mod & pygame.KMOD_SHIFT
                if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif ev.key == pygame.K_UP:
                    power = min(CFG["POWER_MAX"], power + CFG["POWER_STEP"])
                elif ev.key == pygame.K_DOWN:
                    power = max(CFG["POWER_MIN"], power - CFG["POWER_STEP"])
                elif ev.key == pygame.K_SPACE:
                    cue = sim.cue()
                    my_turn = (mode == 0 or (game is not None and not game.over
                               and game.controllers[game.current] == "human"))
                    if cue is not None and sim.all_at_rest() and my_turn:
                        wx, wy = s2w(pygame.mouse.get_pos())
                        sim.strike((wx - cue.position.x, wy - cue.position.y), power,
                                   side=spin_side, follow=spin_follow)
                        if game is not None:
                            pending = True
                elif ev.key == pygame.K_m:
                    mode = (mode + 1) % len(MODES)
                    ai_plan, ai_wait, pending = None, 0, False
                    if mode == 0:
                        sim, game, ais = Sim(), None, None
                    else:
                        sim, game, ais = start_game(mode)
                        # In game modes the opening break is taken as a shot
                        if game.controllers[0] == "ai":
                            sim.break_shot(power=6.0)
                            pending = True
                        else:
                            game.last_event = "your break — aim at the pack"
                elif ev.key == pygame.K_w:
                    spin_follow = min(1.0, spin_follow + 0.25)
                elif ev.key == pygame.K_s:
                    spin_follow = max(-1.0, spin_follow - 0.25)
                elif ev.key == pygame.K_a:
                    spin_side = max(-1.0, spin_side - 0.25)
                elif ev.key == pygame.K_d:
                    spin_side = min(1.0, spin_side + 0.25)
                elif ev.key == pygame.K_x:
                    spin_side, spin_follow = 0.0, 0.0
                elif ev.key == pygame.K_k:
                    sim.toggle_cue_size()
                elif ev.key == pygame.K_t:
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
                elif ev.key == pygame.K_g:
                    show_overlay = not show_overlay

        sim.step(1.0 / CFG["FPS"])

        # ---- game logic (modes 1 and 2) ----
        if game is not None and sim.all_at_rest():
            if pending:
                game.on_rest(sim)
                pending = False
                ai_plan, ai_wait = None, 0
            if (not game.over and not pending
                    and game.controllers[game.current] == "ai"):
                if ai_plan is None:
                    ai_plan = ais[game.current].choose(sim, game.legal_colours(sim))
                    ai_wait = 45 if not smoke else 2
                elif ai_wait > 0:
                    ai_wait -= 1
                else:
                    if ai_plan is not None:
                        sim.strike(ai_plan["aim"], ai_plan["power"])
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
            aim_pos = s2w(pygame.mouse.get_pos())

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
        pygame.draw.line(screen, (150, 195, 160), w2s((bx, y0)), w2s((bx, y1)), RS)
        pygame.draw.circle(screen, (185, 215, 190), w2s((x0 + (x1 - x0) * 0.75, (y0 + y1) / 2)), 2 * RS)

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
                    pygame.draw.aaline(screen, COL["line"], w2s(cue.position), w2s((gx, gy)))
                    pygame.draw.circle(screen, COL["ghost"], w2s((gx, gy)), int(rc * S), 1)
                    tx, ty = gb["target"]
                    path = one_bounce_path((tx, ty), gb["obj_dir"], r)
                    for a, b in zip(path, path[1:]):
                        pygame.draw.aaline(screen, COL["objline"], w2s(a), w2s(b))
                    if gb["cue_dir"] != (0.0, 0.0):
                        cpath = one_bounce_path((gx, gy), gb["cue_dir"], rc, tail=0.25)
                        for a, b in zip(cpath, cpath[1:]):
                            pygame.draw.aaline(screen, COL["tanline"], w2s(a), w2s(b))
                    pa = pot_assessment(gb)
                    aim_txt = f"contact {gb['fullness']*100:3.0f}% full"
                    if pa:
                        pygame.draw.aaline(screen, (120, 140, 120),
                                           w2s((tx, ty)), w2s(pa["pocket"]))
                        aim_txt += (f"  |  pot est {pa['prob']*100:3.0f}%"
                                    f"  (off {pa['angle_deg']:4.1f} deg)")
                else:
                    cpath = one_bounce_path(tuple(cue.position), dxy, ball_r())
                    for a, b in zip(cpath, cpath[1:]):
                        pygame.draw.aaline(screen, COL["line"], w2s(a), w2s(b))

        for bid, (body, shape) in sim.balls.items():
            draw_ball(sim.colours.get(bid, "red"), w2s(body.position),
                      max(2, int(shape.radius * S)))

        cue_lbl = "1-7/8\" 94g" if CFG["CUE_R_M"] < 0.025 else "2\" 116g"
        hud1 = (f"power {power:4.2f} m/s  cushion e {CFG['CUSHION_ELASTICITY']:.2f}  "
                f"roll decel {CFG['ROLL_DECEL']:.3f} m/s2  "
                f"ball {CFG['BALL_R_M']*2000:.1f}mm  cue {cue_lbl}")
        if game is not None:
            def ptxt(i):
                col = game.colours.get(i)
                left = f" {sim.remaining(col)} left" if col else ""
                mark = ">" if (game.current == i and not game.over) else " "
                return f"{mark}{game.names[i]}[{(col or 'open').upper()}{left}]"
            hud2 = (f"{MODES[mode]}  {ptxt(0)} vs {ptxt(1)}  |  {game.last_event}"
                    + ("  |  T=new game" if game.over else ""))
        else:
            hud2 = (f"balls {len(sim.balls)}  potted {len(sim.potted_log)}"
                    f" [{','.join(sim.potted_colours()) or '-'}]  "
                    f"spin side {spin_side:+.2f} follow {spin_follow:+.2f}"
                    + (f"  |  {aim_txt}" if aim_txt else ""))
        screen.blit(font.render(hud1, True, COL["hud"]), (M, H - 44 * RS))
        screen.blit(font.render(hud2, True, COL["hud"]), (M, H - 24 * RS))
        icx, icy = W - M - 22 * RS, H - 30 * RS
        pygame.draw.circle(screen, (200, 200, 200), (icx, icy), 18 * RS, RS)
        pygame.draw.line(screen, (110, 110, 110), (icx - 18 * RS, icy), (icx + 18 * RS, icy), RS)
        pygame.draw.line(screen, (110, 110, 110), (icx, icy - 18 * RS), (icx, icy + 18 * RS), RS)
        pygame.draw.circle(screen, (255, 90, 90),
                           (int(icx + spin_side * 12 * RS), int(icy - spin_follow * 12 * RS)), 4 * RS)

        shown = present(screen)          # classic: same surface; gl: processed
        display.blit(shown, (0, 0))
        pygame.display.flip()
        last_shown = shown
        clock.tick(CFG["FPS"])
        frames += 1
        if smoke and frames >= smoke_frames:
            running = False

    if snap_path:
        pygame.image.save(last_shown, snap_path)  # save the presented frame
        print(f"snap: saved {snap_path}")
    if glpp is not None:
        glpp.release()
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
    s = Sim(layout="empty")
    s._add_ball(s.CUE_ID, (0.91, 0.455), "cue")
    P1, P2 = (0.45, 0.25), (0.33, 0.72)
    s._add_ball(s.alloc_id(), P1, "red")
    s._add_ball(s.alloc_id(), P2, "red")
    def picks(greed):
        ai = PoolAI("T", aim_jitter=0.02, threshold=0.05, greed=greed,
                    rng=random.Random(1))
        sh = ai.choose(s, ["red"])
        near = P1 if math.dist(sh["target"], P1) < math.dist(sh["target"], P2) else P2
        return near, sh
    n0, sh0 = picks(0.0)
    n9, sh9 = picks(0.9)
    est_probe = pot_estimate((0.91, 0.455), P1, capture_points()[0][0],
                             capture_points()[0][1], CFG["CUE_R_M"], ball_r(),
                             0.02)
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

    # 25. GL post-process passthrough (Graphics Pass 3, Increment 1). Pixel-
    #     probe per finding 6.10: a synthetic frame round-tripped through the
    #     offscreen GL pipeline must return bit-identical and upright. Made
    #     dependency-aware on purpose — SKIP (not FAIL) if moderngl/EGL is
    #     unavailable, so the core physics chain stays green on a stripped
    #     container. The full end-to-end render gate is --smoke-gl.
    gl_ok, gl_detail, gl_avail = gl_passthrough_check()
    if gl_avail:
        check("GL post-process — passthrough round-trip pixel-exact + upright "
              "(Graphics Pass 3 I1)", gl_ok, gl_detail)
        ss_ok, ss_detail, _ = gl_ssaa_check()
        check("GL SSAA — 2x->1x resolve box-averages (Graphics Pass 3 I2)",
              ss_ok, ss_detail)
        bl_ok, bl_detail, _ = gl_bloom_check()
        check("GL bloom — bright core glows, black stays black (Graphics "
              "Pass 3 I2)", bl_ok, bl_detail)
    else:
        print(f"  [SKIP] GL post-process — passthrough/SSAA/bloom "
              f"(moderngl/EGL unavailable: {gl_detail})")

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


def smoke_gl(frames=90, snap_path=None):
    """Headless GL render gate (Graphics Pass 3, 2A). Pixel-probes the GL
    passthrough, then runs the GUI smoke through the offscreen GL backend.
    Requires moderngl + an EGL context; returns False (not a crash) if the
    host can't provide one, so callers can route it to nix5."""
    ok, detail, avail = gl_passthrough_check()
    if not avail:
        print(f"smoke-gl: GL unavailable ({detail})")
        print("smoke-gl: needs moderngl + EGL — install moderngl, or run the "
              "GL gate on a GL host (nix5).")
        return False
    ss_ok, ss_detail, _ = gl_ssaa_check()
    bl_ok, bl_detail, _ = gl_bloom_check()
    print(f"smoke-gl: passthrough {'PASS' if ok else 'FAIL'} ({detail})")
    print(f"smoke-gl: SSAA resolve {'PASS' if ss_ok else 'FAIL'} ({ss_detail})")
    print(f"smoke-gl: bloom        {'PASS' if bl_ok else 'FAIL'} ({bl_detail})")
    if not (ok and ss_ok and bl_ok):
        return False
    try:
        n = run_gui(smoke=True, smoke_frames=frames, snap_path=snap_path,
                    backend="gl")
    except GLUnavailable as e:
        print(f"smoke-gl: GL context lost mid-run ({e})")
        return False
    print(f"smoke-gl: rendered {n} frames through the GL backend OK")
    return True


def main():
    ap = argparse.ArgumentParser(description="HUSTLER — UK pool physics sandbox (R5)")
    ap.add_argument("--selftest", action="store_true", help="run headless assertions")
    ap.add_argument("--batch", type=int, metavar="N", help="run N random strikes headless")
    ap.add_argument("--breaks", type=int, metavar="N", help="break analyser, N trials per config")
    ap.add_argument("--aigame", type=int, metavar="N", help="run N headless AI vs AI games")
    ap.add_argument("--smoke", action="store_true", help="GUI smoke on dummy video driver")
    ap.add_argument("--smoke-gl", action="store_true", dest="smoke_gl",
                    help="headless GL render gate (moderngl/EGL post-process)")
    ap.add_argument("--classic", action="store_true",
                    help="force the classic pygame renderer (default; reserved "
                         "for when interactive GL lands)")
    ap.add_argument("--gl", action="store_true",
                    help="run the interactive window through the GL pipeline "
                         "(SSAA + bloom)")
    ap.add_argument("--snap", metavar="FILE", help="headless smoke run, save screenshot PNG")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if args.batch:
        sys.exit(0 if batch(args.batch) else 1)
    if args.breaks:
        sys.exit(0 if break_analysis(args.breaks) else 1)
    if args.aigame:
        sys.exit(0 if aigame_batch(args.aigame) else 1)
    if args.smoke_gl:
        sys.exit(0 if smoke_gl(snap_path=args.snap) else 1)
    if args.snap:
        frames = run_gui(smoke=True, smoke_frames=90, snap_path=args.snap)
        print(f"smoke: rendered {frames} frames OK")
        sys.exit(0)
    if args.smoke:
        frames = run_gui(smoke=True)
        print(f"smoke: rendered {frames} frames OK")
        sys.exit(0)
    run_gui(backend="gl" if (args.gl and not args.classic) else "classic")


if __name__ == "__main__":
    main()
