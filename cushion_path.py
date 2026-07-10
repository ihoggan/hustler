"""
cushion_path.py — UK 6ft blackball cushion-nose collision path.  (r2)

Coordinate system: play-area top-left at (0, 0), y increases DOWNWARD (pygame).
All units mm. The path is a single closed clockwise loop of 36 primitives:
6 rail segments + per pocket (knuckle arc, jaw, pocket back, jaw, knuckle arc).

Tangency construction
---------------------
Each knuckle circle (R = 22) has its centre set back exactly R behind the nose
line, so the circle is tangent to the rail at the tangent foot and the rail
terminates precisely there. From the tangent foot the knuckle arc curves
INWARD toward the pocket centre — convex relative to the opening — sweeping
only until its tangent aligns with the pocket throat:
    corner pockets: 45 deg sweep  (rail -> 45-deg throat)
    middle pockets: 90 deg sweep  (rail -> perpendicular throat)
A straight jaw segment then continues tangentially down the throat, and a
flat pocket back (perpendicular to the throat) closes the opening, entirely
outside the playing area. Every rail<->arc and arc<->jaw junction is C1.

Spec constants: playing area 1778 x 889, nose inset 50mm from outer frame,
knuckle radius 22mm (corners and middles). Mouth widths and jaw depths were
not in the brief and are parameterised — tune to taste.
"""

import math

# ---------------------------------------------------------------- constants
PLAY_W       = 1778.0   # playing-area width  (nose to nose), mm
PLAY_H       = 889.0    # playing-area height (nose to nose), mm
FRAME_OFFSET = 50.0     # nose line inset 50mm from the outer table frame
KNUCKLE_R    = 22.0     # knuckle arc radius, corners AND middles, mm

CORNER_MOUTH = 89.0     # tangent foot to tangent foot across the 45deg corner opening
MIDDLE_MOUTH = 100.0    # tangent foot to tangent foot along the rail
CORNER_JAW   = 45.0     # straight jaw length down the corner throat, mm
MIDDLE_JAW   = 12.0     # straight jaw length down the middle throat, mm
                        # (r4c: near-zero shelf — hole front edge sits ~1mm
                        #  behind the nose line, matching real UK middles)

S  = CORNER_MOUTH / math.sqrt(2.0)   # rail setback: corner -> tangent foot, per axis
HM = MIDDLE_MOUTH / 2.0              # half middle-pocket mouth
Q  = KNUCKLE_R / math.sqrt(2.0)      # 45-deg component of knuckle radius
DC = CORNER_JAW / math.sqrt(2.0)     # per-axis component of corner jaw

FRAME_RECT = (-FRAME_OFFSET, -FRAME_OFFSET,
              PLAY_W + 2 * FRAME_OFFSET, PLAY_H + 2 * FRAME_OFFSET)


def configure(play_w=None, play_h=None, corner_mouth=None, middle_mouth=None,
              knuckle_r=None, corner_jaw=None, middle_jaw=None):
    """Drive the geometry from a host spec (all mm). Recomputes the derived
    setbacks so build_cushion_path / pocket_geometry pick up the new spec.

    Defaults are left untouched when an argument is None, so the standalone
    selftest (run with no configure call) keeps validating the reference
    6ft / 89-100 spec. HUSTLER calls this with its 7ft table and the WEPF
    1.6x-diameter mouth (Fork C) before building the cushions."""
    global PLAY_W, PLAY_H, CORNER_MOUTH, MIDDLE_MOUTH, KNUCKLE_R
    global CORNER_JAW, MIDDLE_JAW, S, HM, Q, DC, FRAME_RECT
    if play_w is not None:       PLAY_W = float(play_w)
    if play_h is not None:       PLAY_H = float(play_h)
    if corner_mouth is not None: CORNER_MOUTH = float(corner_mouth)
    if middle_mouth is not None: MIDDLE_MOUTH = float(middle_mouth)
    if knuckle_r is not None:    KNUCKLE_R = float(knuckle_r)
    if corner_jaw is not None:   CORNER_JAW = float(corner_jaw)
    if middle_jaw is not None:   MIDDLE_JAW = float(middle_jaw)
    S  = CORNER_MOUTH / math.sqrt(2.0)
    HM = MIDDLE_MOUTH / 2.0
    Q  = KNUCKLE_R / math.sqrt(2.0)
    DC = CORNER_JAW / math.sqrt(2.0)
    FRAME_RECT = (-FRAME_OFFSET, -FRAME_OFFSET,
                  PLAY_W + 2 * FRAME_OFFSET, PLAY_H + 2 * FRAME_OFFSET)

# ------------------------------------------------------------- rendering
HOLE_SCALE  = 1.5             # pocket hole radius = KNUCKLE_R * HOLE_SCALE
RAIL_WIDTH  = 40.0            # outer wooden surround beyond the cushion band, mm
WRAP_MARGIN = 6.0             # far-chord overshoot of the throat-wrap trapezoid, mm
RIM_MARGIN  = 4.0             # dark pocket-rim surround width, mm
GRID_COLS, GRID_ROWS = 4, 2   # master reference grid (1 cell = 444.5mm, exact 2:1)

COL_BG        = (18, 18, 22)
COL_WOOD_EDGE = (52, 32, 16)     # dark bevel around the frame
COL_WOOD      = (118, 74, 34)    # outer wooden rail face
COL_SLOPE     = (66, 40, 18)     # cushion slope band (frame -> nose)
COL_BAIZE     = (88, 150, 86)    # playing fabric
COL_NOSE_HI   = (120, 180, 110)  # refined subtle nose highlight (Maker r4b)
COL_HOLE      = (30, 30, 32)     # pocket base (gradient darkens it further)
COL_POCKET_RIM = (26, 20, 14)    # dark pocket plate/leather surround
COL_GRID      = (255, 255, 255, 110)


# ---------------------------------------------------------------- geometry
def arc_point(centre, r, deg):
    """Point on a circle. Screen convention: +deg rotates towards +y (down)."""
    a = math.radians(deg)
    return (centre[0] + r * math.cos(a), centre[1] + r * math.sin(a))


def build_cushion_path():
    """Closed clockwise cushion-nose loop.

    Primitives:
        ("line", (x0, y0), (x1, y1))
        ("arc",  (cx, cy), r, a0_deg, a1_deg)   # sampled linearly a0 -> a1
    """
    W, H, R = PLAY_W, PLAY_H, KNUCKLE_R
    X = W / 2.0
    P = []
    L  = lambda p0, p1: P.append(("line", p0, p1))
    A  = lambda c, a0, a1: P.append(("arc", c, R, a0, a1))
    AE = lambda c, deg: arc_point(c, R, deg)

    # ---- top rail, left half -------------------------------------------
    L((S, 0.0), (X - HM, 0.0))
    # ---- top middle pocket (throat straight up, (0,-1)) ------------------
    A((X - HM, -R), 90, 0)                                    # knuckle, 90deg
    L((X - HM + R, -R), (X - HM + R, -R - MIDDLE_JAW))        # jaw
    L((X - HM + R, -R - MIDDLE_JAW),
      (X + HM - R, -R - MIDDLE_JAW))                          # pocket back
    L((X + HM - R, -R - MIDDLE_JAW), (X + HM - R, -R))        # jaw
    A((X + HM, -R), 180, 90)                                  # knuckle
    # ---- top rail, right half --------------------------------------------
    L((X + HM, 0.0), (W - S, 0.0))
    # ---- top-right corner pocket (throat (1,-1)/sqrt2) ---------------------
    A((W - S, -R), 90, 45)                                    # knuckle, 45deg
    e1 = AE((W - S, -R), 45)          # (W-S+Q, -R+Q)
    e2 = AE((W + R, S), 225)          # (W+R-Q, S-Q)
    L(e1, (e1[0] + DC, e1[1] - DC))                           # jaw
    L((e1[0] + DC, e1[1] - DC), (e2[0] + DC, e2[1] - DC))     # pocket back
    L((e2[0] + DC, e2[1] - DC), e2)                           # jaw
    A((W + R, S), 225, 180)                                   # knuckle
    # ---- right rail ---------------------------------------------------------
    L((W, S), (W, H - S))
    # ---- bottom-right corner pocket (throat (1,1)/sqrt2) ---------------------
    A((W + R, H - S), 180, 135)
    e1 = AE((W + R, H - S), 135)      # (W+R-Q, H-S+Q)
    e2 = AE((W - S, H + R), 315)      # (W-S+Q, H+R-Q)
    L(e1, (e1[0] + DC, e1[1] + DC))
    L((e1[0] + DC, e1[1] + DC), (e2[0] + DC, e2[1] + DC))
    L((e2[0] + DC, e2[1] + DC), e2)
    A((W - S, H + R), 315, 270)
    # ---- bottom rail, right half -----------------------------------------------
    L((W - S, H), (X + HM, H))
    # ---- bottom middle pocket (throat straight down, (0,1)) -----------------------
    A((X + HM, H + R), 270, 180)
    L((X + HM - R, H + R), (X + HM - R, H + R + MIDDLE_JAW))
    L((X + HM - R, H + R + MIDDLE_JAW),
      (X - HM + R, H + R + MIDDLE_JAW))
    L((X - HM + R, H + R + MIDDLE_JAW), (X - HM + R, H + R))
    A((X - HM, H + R), 0, -90)
    # ---- bottom rail, left half ------------------------------------------------------
    L((X - HM, H), (S, H))
    # ---- bottom-left corner pocket (throat (-1,1)/sqrt2) --------------------------------
    A((S, H + R), 270, 225)
    e1 = AE((S, H + R), 225)          # (S-Q, H+R-Q)
    e2 = AE((-R, H - S), 45)          # (-R+Q, H-S+Q)
    L(e1, (e1[0] - DC, e1[1] + DC))
    L((e1[0] - DC, e1[1] + DC), (e2[0] - DC, e2[1] + DC))
    L((e2[0] - DC, e2[1] + DC), e2)
    A((-R, H - S), 45, 0)
    # ---- left rail ------------------------------------------------------------------------
    L((0.0, H - S), (0.0, S))
    # ---- top-left corner pocket (throat (-1,-1)/sqrt2) ---------------------------------------
    A((-R, S), 0, -45)
    e1 = AE((-R, S), -45)             # (-R+Q, S-Q)
    e2 = AE((S, -R), 135)             # (S-Q, -R+Q)
    L(e1, (e1[0] - DC, e1[1] - DC))
    L((e1[0] - DC, e1[1] - DC), (e2[0] - DC, e2[1] - DC))
    L((e2[0] - DC, e2[1] - DC), e2)
    A((S, -R), 135, 90)                                       # closes to (S, 0)
    return P


def prim_endpoints(prim):
    if prim[0] == "line":
        return prim[1], prim[2]
    _, c, r, a0, a1 = prim
    return arc_point(c, r, a0), arc_point(c, r, a1)


def flatten(path, max_seg_deg=5.0):
    """Closed loop -> vertex list (arcs tessellated, duplicates removed)."""
    pts = []
    for prim in path:
        if prim[0] == "line":
            seg = [prim[1], prim[2]]
        else:
            _, c, r, a0, a1 = prim
            n = max(2, int(math.ceil(abs(a1 - a0) / max_seg_deg)))
            seg = [arc_point(c, r, a0 + (a1 - a0) * i / n) for i in range(n + 1)]
        if pts and _near(pts[-1], seg[0]):
            pts.extend(seg[1:])
        else:
            pts.extend(seg)
    if len(pts) > 1 and _near(pts[0], pts[-1]):
        pts.pop()
    return pts


def build_pymunk_cushions(space, path=None, seg_radius=1.0,
                          elasticity=0.85, friction=0.2, max_seg_deg=3.0):
    """Add the nose loop to a pymunk Space as static Segments.
    NOTE: Segment radius fattens the nose towards the play area by seg_radius
    mm — keep it small or pre-inset the path for exact nose dimensions."""
    import pymunk
    pts = flatten(path or build_cushion_path(), max_seg_deg)
    segs = []
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        s = pymunk.Segment(space.static_body, a, b, seg_radius)
        s.elasticity, s.friction = elasticity, friction
        s.collision_type = 1
        segs.append(s)
    space.add(*segs)
    return segs


def pocket_geometry(scale=HOLE_SCALE):
    """Per-pocket render geometry, all derived from the collision constants.

    centre : pocket hole centre (pocket-back midpoint, on the throat axis)
    r      : hole radius = KNUCKLE_R * scale
    axis   : unit vector along the throat, pointing OUT of the table (deeper)
    e1, e2 : the two knuckle->jaw tangent points — the exact primitive nodes
             where the cushion nose arc hands over to the straight jaw
    """
    W, H, R = PLAY_W, PLAY_H, KNUCKLE_R
    X = W / 2.0
    r = R * scale
    g = DC - (S - R) / 2.0
    dm = R + MIDDLE_JAW
    k = 1.0 / math.sqrt(2.0)
    def P(c, u, e1, e2):
        return {"centre": c, "r": r, "axis": u, "e1": e1, "e2": e2}
    return [
        P((-g, -g),     (-k, -k), (-R + Q, S - Q),      (S - Q, -R + Q)),      # top-left
        P((X, -dm),     (0, -1),  (X - HM + R, -R),     (X + HM - R, -R)),     # top-middle
        P((W + g, -g),  (k, -k),  (W - S + Q, -R + Q),  (W + R - Q, S - Q)),   # top-right
        P((W + g, H + g), (k, k), (W + R - Q, H - S + Q), (W - S + Q, H + R - Q)),  # bottom-right
        P((X, H + dm),  (0, 1),   (X + HM - R, H + R),  (X - HM + R, H + R)),  # bottom-middle
        P((-g, H + g),  (-k, k),  (S - Q, H + R - Q),   (-R + Q, H - S + Q)),  # bottom-left
    ]


def pocket_holes(scale=HOLE_SCALE):
    """The six pocket holes as ((cx, cy), radius)."""
    return [(p["centre"], p["r"]) for p in pocket_geometry(scale)]


def throat_wraps(scale=HOLE_SCALE, margin=WRAP_MARGIN):
    """Baize 'fabric wrap' trapezoid per pocket.

    Bridges the cushion nose to the pocket hole: near edge is the chord
    e1 -> e2 between the knuckle->jaw tangent points; far edge is the
    parallel chord of the wrap ring (hole radius + margin) through the
    hole centre, perpendicular to the throat axis. Rendered in baize
    green beneath the hole so the fabric appears to roll into the drop.
    """
    quads = []
    for p in pocket_geometry(scale):
        (cx, cy), rw = p["centre"], p["r"] + margin
        e1, e2 = p["e1"], p["e2"]
        vx, vy = e2[0] - e1[0], e2[1] - e1[1]
        L = math.hypot(vx, vy)
        vx, vy = vx / L, vy / L
        quads.append([e1, e2, (cx + vx * rw, cy + vy * rw),
                              (cx - vx * rw, cy - vy * rw)])
    return quads


def rail_back_polygon():
    """Outer polygon: the back of the wood rail, FRAME_OFFSET (50mm) behind
    every nose line. The band between it and the nose is the cushion slope."""
    x0, y0 = -FRAME_OFFSET, -FRAME_OFFSET
    x1, y1 = PLAY_W + FRAME_OFFSET, PLAY_H + FRAME_OFFSET
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _draw_pocket(surf, T, Spx, p):
    """Pocket hole with radial depth simulation. (Maker r4b tuning)"""
    import pygame
    (cx, cy), r, u = T(p["centre"]), p["r"], p["axis"]
    rp = max(2, Spx(r))
    pygame.draw.circle(surf, COL_HOLE, (cx, cy), rp)

    # Depth simulation: concentric circles shrinking toward the throat axis
    d = rp + Spx(r)
    tmp = pygame.Surface((2 * d, 2 * d), pygame.SRCALPHA)
    for i in range(1, 6):
        rad = int(rp * (1.0 - 0.15 * i))
        if rad <= 0:
            break
        off = rp * 0.12 * i
        pygame.draw.circle(tmp, (0, 0, 0, 40 + 30 * i),
                           (int(d + u[0] * off), int(d + u[1] * off)), rad)
    surf.blit(tmp, (cx - d, cy - d))


def _draw_grid(surf, T):
    """4x2 master reference grid overlay (semi-transparent white)."""
    import pygame
    ox, oy = T((0, 0))
    ex, ey = T((PLAY_W, PLAY_H))
    ov = pygame.Surface((surf.get_width(), surf.get_height()), pygame.SRCALPHA)
    for i in range(GRID_COLS + 1):
        x = ox + (ex - ox) * i / GRID_COLS
        pygame.draw.line(ov, COL_GRID, (x, oy), (x, ey), 1)
    for j in range(GRID_ROWS + 1):
        y = oy + (ey - oy) * j / GRID_ROWS
        pygame.draw.line(ov, COL_GRID, (ox, y), (ex, y), 1)
    surf.blit(ov, (0, 0))


def draw_table(surf, T, Spx, nose_px=None, show_grid=False):
    """Layered render, Maker r4b layer order.

    1) wooden frame  2) cushion slope  3) baize  4) nose highlight
    (full-width line over the baize)  5) throat wraps + wrap rings
    6) pocket holes with radial depth  [optional 4x2 grid]
    """
    import pygame
    geo = pocket_geometry()

    # 1. Outer wooden frame
    o = FRAME_OFFSET + RAIL_WIDTH
    pygame.draw.rect(surf, COL_WOOD_EDGE,
                     (*T((-o - 8, -o - 8)), Spx(PLAY_W + 2 * o + 16),
                      Spx(PLAY_H + 2 * o + 16)),
                     border_radius=Spx(RAIL_WIDTH + 28))
    pygame.draw.rect(surf, COL_WOOD,
                     (*T((-o, -o)), Spx(PLAY_W + 2 * o), Spx(PLAY_H + 2 * o)),
                     border_radius=Spx(RAIL_WIDTH + 20))

    # 2. Cushion slope band
    pygame.draw.polygon(surf, COL_SLOPE, [T(p) for p in rail_back_polygon()])

    # 3. Baize surface (before highlight, so the nose line overlays cleanly)
    if nose_px is None:
        nose_px = [T(p) for p in flatten(build_cushion_path(), 3.0)]
    pygame.draw.polygon(surf, COL_BAIZE, nose_px)

    # 4. Nose highlight
    pygame.draw.polygon(surf, COL_NOSE_HI, nose_px, max(2, Spx(4)))

    # 5. Throat wraps (green fabric from the mouth side only) + dark rims
    #    NOTE: the rim is load-bearing — it defines the hole edge against
    #    the rail so the pocket never reads as a hole punched in cloth,
    #    while the trapezoid alone carries the baize into the mouth.
    for quad in throat_wraps():
        pygame.draw.polygon(surf, COL_BAIZE, [T(pt) for pt in quad])
    for p in geo:
        pygame.draw.circle(surf, COL_POCKET_RIM, T(p["centre"]),
                           max(2, Spx(p["r"] + RIM_MARGIN)))

    # 6. Pocket holes (with radial depth)
    for p in geo:
        _draw_pocket(surf, T, Spx, p)

    if show_grid:
        _draw_grid(surf, T)
    return nose_px


# ---------------------------------------------------------------- self-test
_EPS = 1e-6

def _near(p, q, eps=_EPS):
    return abs(p[0] - q[0]) < eps and abs(p[1] - q[1]) < eps


def selftest():
    path = build_cushion_path()
    assert len(path) == 36, f"expected 36 primitives, got {len(path)}"

    # 1) closure: every primitive ends where the next begins (incl. wraparound)
    for i, prim in enumerate(path):
        _, end = prim_endpoints(prim)
        nstart, _ = prim_endpoints(path[(i + 1) % len(path)])
        assert _near(end, nstart), f"gap after primitive {i}: {end} -> {nstart}"

    # 2) tangency at EVERY line<->arc junction (rails and jaws alike):
    #    the line direction must be perpendicular to the arc radius there,
    #    and the junction must sit exactly R from the arc centre.
    for i, prim in enumerate(path):
        nxt = path[(i + 1) % len(path)]
        pairs = []
        if prim[0] == "line" and nxt[0] == "arc":
            pairs.append((prim, nxt, prim_endpoints(prim)[1]))
        if prim[0] == "arc" and nxt[0] == "line":
            pairs.append((nxt, prim, prim_endpoints(nxt)[0]))
        for line, arc, jp in pairs:
            (x0, y0), (x1, y1) = line[1], line[2]
            c = arc[1]
            radial = (jp[0] - c[0], jp[1] - c[1])
            raild = (x1 - x0, y1 - y0)
            dot = radial[0] * raild[0] + radial[1] * raild[1]
            assert abs(dot) < 1e-6 * math.hypot(*raild) * KNUCKLE_R, \
                f"non-tangent junction at primitive {i}"
            assert abs(math.hypot(*radial) - KNUCKLE_R) < _EPS, \
                f"bad radius at primitive {i}"

    # 3) knuckle sweep sanity: 90deg at middles, 45deg at corners
    arcs = [p for p in path if p[0] == "arc"]
    sweeps = sorted(round(abs(p[4] - p[3]), 6) for p in arcs)
    assert sweeps == [45.0] * 8 + [90.0] * 4, f"bad sweeps: {sweeps}"

    # 4) containment: densely sample EVERY primitive (not just vertices) —
    #    nothing may protrude strictly inside the playing area.
    tol = 1e-9
    for prim in path:
        if prim[0] == "line":
            (x0, y0), (x1, y1) = prim[1], prim[2]
            samples = [(x0 + (x1 - x0) * t / 64.0, y0 + (y1 - y0) * t / 64.0)
                       for t in range(65)]
        else:
            _, c, r, a0, a1 = prim
            samples = [arc_point(c, r, a0 + (a1 - a0) * t / 64.0)
                       for t in range(65)]
        for p in samples:
            inside = (tol < p[0] < PLAY_W - tol) and (tol < p[1] < PLAY_H - tol)
            assert not inside, f"path protrudes into play area at {p}"

    # 5) pocket backs perpendicular to their throats
    backs = {3: (0, -1), 9: (1, -1), 15: (1, 1), 21: (0, 1), 27: (-1, 1), 33: (-1, -1)}
    for idx, d in backs.items():
        _, p0, p1 = path[idx]
        v = (p1[0] - p0[0], p1[1] - p0[1])
        assert abs(v[0] * d[0] + v[1] * d[1]) < 1e-6, f"pocket back {idx} not perpendicular to throat"

    # 6) pocket holes: centred on throat axes, entirely behind their mouth lines
    holes = pocket_holes()
    assert len(holes) == 6
    W, H, X = PLAY_W, PLAY_H, PLAY_W / 2.0
    rt2 = math.sqrt(2.0)
    mouth_clear = [
        abs(holes[0][0][0] + holes[0][0][1] - S) / rt2,          # TL: line x+y=S
        abs(holes[1][0][1]),                                     # TM: line y=0
        abs((W - holes[2][0][0]) + holes[2][0][1] - S) / rt2,    # TR
        abs((W - holes[3][0][0]) + (H - holes[3][0][1]) - S) / rt2,
        abs(holes[4][0][1] - H),                                 # BM: line y=H
        abs(holes[5][0][0] + (H - holes[5][0][1]) - S) / rt2,    # BL
    ]
    for (c, r), d in zip(holes, mouth_clear):
        assert d > r, f"pocket hole at {c} breaches its mouth line (clear {d:.1f} <= r {r:.1f})"
    assert holes[1][0][0] == X and holes[4][0][0] == X, "middle holes off throat axis"

    # 7) throat wraps: every wrap vertex outside the play area, and every
    #    e1/e2 coincides EXACTLY with a knuckle-arc endpoint in the path
    arc_ends = []
    for prim in path:
        if prim[0] == "arc":
            arc_ends.extend(prim_endpoints(prim))
    for p in pocket_geometry():
        for e in (p["e1"], p["e2"]):
            assert any(_near(e, a) for a in arc_ends), \
                f"wrap tangent point {e} is not a primitive node"
    for quad in throat_wraps():
        for v in quad:
            inside = (tol < v[0] < PLAY_W - tol) and (tol < v[1] < PLAY_H - tol)
            assert not inside, f"throat wrap protrudes into play area at {v}"

    print("SELFTEST OK — 36 primitives, closed, tangent, convex knuckles, "
          "contained; holes behind mouth lines; wraps anchored to primitive nodes.")
    return path


def print_table(path):
    print(f"\n{'#':>2}  {'type':<5} {'geometry'}")
    for i, prim in enumerate(path):
        if prim[0] == "line":
            (x0, y0), (x1, y1) = prim[1], prim[2]
            print(f"{i:>2}  line  ({x0:9.3f},{y0:9.3f}) -> ({x1:9.3f},{y1:9.3f})")
        else:
            _, (cx, cy), r, a0, a1 = prim
            print(f"{i:>2}  arc   c=({cx:9.3f},{cy:9.3f}) r={r:.1f}  {a0:>7.1f}deg -> {a1:>7.1f}deg")
    print(f"\nkey values: corner setback S = {S:.3f}mm, middle half-mouth = {HM:.1f}mm, "
          f"knuckle R = {KNUCKLE_R:.1f}mm, corner jaw = {CORNER_JAW:.0f}mm, middle jaw = {MIDDLE_JAW:.0f}mm")


# ---------------------------------------------------------------- preview
def preview():
    """Layered render: wooden rail, cushion face, baize, nose line, pocket holes."""
    import pygame
    SC, PAD = 0.55, 90
    w = int(PLAY_W * SC) + 2 * PAD
    h = int(PLAY_H * SC) + 2 * PAD
    pygame.init()
    screen = pygame.display.set_mode((w, h))
    pygame.display.set_caption("UK 6ft blackball table (r3)")
    T = lambda p: (int(p[0] * SC) + PAD, int(p[1] * SC) + PAD)
    Spx = lambda mm: max(1, int(mm * SC))
    nose_px = None
    show_grid = False
    clock = pygame.time.Clock()
    run = True
    while run:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                run = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_g:
                show_grid = not show_grid
        screen.fill(COL_BG)
        nose_px = draw_table(screen, T, Spx, nose_px, show_grid=show_grid)
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()


if __name__ == "__main__":
    import sys
    p = selftest()
    print_table(p)
    if "--preview" in sys.argv:
        preview()