#!/usr/bin/env python3
"""Graphics Pass 3 — headless EGL feasibility probe (2A gate viability).

Answers one question: can we get a working offscreen OpenGL context in this
CPU-only container via EGL + llvmpipe, compile a shader, render, and read
back correct pixels? If yes, the --smoke-gl render gate can run in-CI here.
If no, that gate must live on nix5's real GPU.

Not a build — throwaway diagnostic. Verifies at the PIXEL level (finding
6.10 doctrine: world-space correctness does not survive to the framebuffer
for free).
"""
import os
# Force software rendering (llvmpipe) so the probe reflects the CI container,
# not any accidental GPU. Standalone context on headless Linux -> EGL backend.
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
os.environ.setdefault("MESA_LOADER_DRIVER_OVERRIDE", "llvmpipe")

import sys
import numpy as np
import moderngl

FAILS = []
def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    if not cond:
        FAILS.append(name)
    print(f"  [{tag}] {name}" + (f"  ({detail})" if detail else ""))

print("GL PROBE — headless EGL / llvmpipe feasibility")

# 1. Standalone (windowless) context. MUST force the EGL backend — the
#    glcontext default on Linux is X11/GLX, which needs a display we don't
#    have headless. backend='egl' is the whole point of the CI path.
ctx = None
last_err = None
for kw in ({"require": 330, "backend": "egl"},
           {"require": 330, "backend": "egl", "device_index": 0}):
    try:
        ctx = moderngl.create_standalone_context(**kw)
        break
    except Exception as e:
        last_err = e
if ctx is None:
    print(f"  [FAIL] EGL standalone context raised: {last_err!r}")
    print("PROBE RESULT: EGL/llvmpipe context UNAVAILABLE in-container.")
    sys.exit(1)
ok_ctx = True

renderer = ctx.info.get("GL_RENDERER", "?")
vendor   = ctx.info.get("GL_VENDOR", "?")
version  = ctx.info.get("GL_VERSION", "?")
glsl     = ctx.info.get("GL_SHADING_LANGUAGE_VERSION", "?")
check("standalone EGL context created", ok_ctx, renderer)
print(f"         vendor : {vendor}")
print(f"         version: {version}")
print(f"         glsl   : {glsl}")

# 2. GLSL adequate for bloom/grade passes. The authoritative test is whether
#    a #version 330 program actually compiles+links below (check #4), not the
#    info string (moderngl 5.12 doesn't always expose the GLSL key). GL 4.5
#    Core mandates GLSL 4.50, so record that and defer the real proof to #4.
gl_major = 0
try:
    gl_major = int(version.split()[0].split(".")[0])
except Exception:
    pass
check("OpenGL >= 3.3 core (GLSL 330+ guaranteed)", gl_major >= 3 or "4." in version,
      f"GL {version.split('Mesa')[0].strip()}")

# 3. Float framebuffer support (bloom bright-pass wants >8-bit for HDR-ish).
try:
    fbo_f = ctx.framebuffer(color_attachments=[ctx.texture((16, 16), 4, dtype="f2")])
    check("half-float FBO (f2) allocatable", True, "rgba16f")
    fbo_f.release()
except Exception as e:
    check("half-float FBO (f2) allocatable", False, repr(e))

# 4. Full-screen-triangle post-process pass with pixel read-back.
#    Shader paints a known gradient; we verify exact corner pixels so this is
#    a real correctness check, not just "it ran".
W, H = 64, 48
tex = ctx.texture((W, H), 4, dtype="f1")
fbo = ctx.framebuffer(color_attachments=[tex])
fbo.use()
ctx.clear(0.0, 0.0, 0.0, 1.0)

prog = ctx.program(
    vertex_shader="""
        #version 330
        in vec2 in_pos;
        out vec2 uv;
        void main() {
            uv = in_pos * 0.5 + 0.5;
            gl_Position = vec4(in_pos, 0.0, 1.0);
        }
    """,
    fragment_shader="""
        #version 330
        in vec2 uv;
        out vec4 frag;
        void main() {
            // R ramps with x, G ramps with y, B flat — deterministic target.
            frag = vec4(uv.x, uv.y, 0.25, 1.0);
        }
    """,
)
# Full-screen triangle (covers clip space with one primitive).
verts = np.array([-1, -1, 3, -1, -1, 3], dtype="f4")
vbo = ctx.buffer(verts.tobytes())
vao = ctx.vertex_array(prog, [(vbo, "2f", "in_pos")])
vao.render(moderngl.TRIANGLES)

raw = fbo.read(components=4, dtype="f1")
img = np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 4)

# Pixel-level assertions. GL origin is bottom-left; read-back row 0 = bottom.
bl = img[0, 0]        # uv ~ (0,0)   -> R low,  G low
br = img[0, W - 1]    # uv ~ (1,0)   -> R high, G low
tl = img[H - 1, 0]    # uv ~ (0,1)   -> R low,  G high
b_flat = int(img[H // 2, W // 2, 2])

check("shader compiled + linked + rendered", True)
check("pixel R ramps left->right", int(bl[0]) < 40 and int(br[0]) > 215,
      f"R bl={bl[0]} br={br[0]}")
check("pixel G ramps bottom->top", int(bl[1]) < 40 and int(tl[1]) > 215,
      f"G bl={bl[1]} tl={tl[1]}")
check("pixel B flat at 0.25", 55 <= b_flat <= 73, f"B={b_flat}")

# 5. Round-trip an image the way the real 1A path will: numpy RGBA (a pygame
#    frame) -> texture -> sample in shader -> read back unchanged. This is the
#    exact upload/download the post-process pipeline depends on.
src = np.random.randint(0, 256, (H, W, 4), dtype=np.uint8)
src[:, :, 3] = 255
utex = ctx.texture((W, H), 4, data=src.tobytes(), dtype="f1")
utex.filter = (moderngl.NEAREST, moderngl.NEAREST)
otex = ctx.texture((W, H), 4, dtype="f1")
ofbo = ctx.framebuffer(color_attachments=[otex])
ofbo.use()
ctx.clear()
copy = ctx.program(
    vertex_shader="""
        #version 330
        in vec2 in_pos; out vec2 uv;
        void main(){ uv = in_pos*0.5+0.5; gl_Position = vec4(in_pos,0,1); }
    """,
    fragment_shader="""
        #version 330
        uniform sampler2D src; in vec2 uv; out vec4 frag;
        void main(){ frag = texture(src, uv); }
    """,
)
utex.use(0)
copy["src"].value = 0
vao2 = ctx.vertex_array(copy, [(vbo, "2f", "in_pos")])
vao2.render(moderngl.TRIANGLES)
back = np.frombuffer(ofbo.read(components=4, dtype="f1"),
                     dtype=np.uint8).reshape(H, W, 4)
# Determine the exact row-order convention rather than assuming it: a lossless
# pipeline must match src either as-is or vertically flipped. WHICH one tells
# the real 1A path whether a flip is needed when compositing a pygame frame.
same_direct = np.array_equal(back, src)
same_flip   = np.array_equal(back, src[::-1])
lossless = same_direct or same_flip
orient = ("no flip (row-aligned)" if same_direct else
          "vertical flip needed" if same_flip else "MISMATCH")
err_direct = int(np.abs(back.astype(int) - src.astype(int)).max())
err_flip   = int(np.abs(back.astype(int) - src[::-1].astype(int)).max())
check("RGBA upload->sample->readback lossless", lossless,
      f"{orient}; err direct={err_direct} flip={err_flip}")
if lossless:
    print(f"         -> 1A convention: pygame frame needs "
          f"{'a vertical flip' if same_flip else 'NO flip'} on GL round-trip")

print("")
if FAILS:
    print(f"PROBE RESULT: {len(FAILS)} check(s) FAILED -> {FAILS}")
    print("2A in-container gate NOT viable as-is; --smoke-gl -> nix5.")
    sys.exit(1)
else:
    print("PROBE RESULT: ALL PASS — headless EGL/llvmpipe render is viable "
          "in-container.")
    print("=> 2A --smoke-gl gate CAN run in CI here; nix5 remains the "
          "real-GPU confirmation, not a hard dependency.")
