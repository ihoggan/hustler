# Known Issues

The honest state of the open threads as of r23. None of these stop the game
being playable. Each is written up with its diagnosis so the next person to
touch it (quite possibly future me) starts from the answer, not the symptom.

---

## 1. Can't place balls right on the pocket jaws in custom mode

**Symptom:** in custom mode you can't set a ball close enough to a pocket to
have it sitting on the lip, ready to pot.

**Diagnosis:** the legal-placement test treats the table as a plain rectangle
and keeps every ball a full ball-radius inside the rails. That rule is correct
along a cushion — a ball can't be embedded in a rail — but it also walls off the
pocket mouths, where there is no cushion. A corner pocket's centre actually sits
slightly *outside* the rectangle, so the whole jaws area fails the test.

**Status:** one part of this is fixed (an over-cautious margin around each
pocket has been trimmed to the true minimum). The remaining part — the
rectangle not knowing about pocket mouths — is **not** fixed. An attempt to
exempt circular "mouth" zones from the rail rule was tried and reverted: the
middle-pocket zones reached out over the side rails and briefly let balls embed
in the cushion. A regression guard is now in the test suite to prevent that
class of mistake recurring.

**The right fix (not yet attempted):** test placement against the real cushion
geometry (the tangent-true nose path) instead of a rectangle. That handles rails
and pocket mouths in a single rule, with no special cases. It only *reads* the
existing geometry, so it doesn't disturb the table spec. Resist the temptation
to try another margin adjustment — that approach has now failed twice.

---

## 2. Full-screen at startup can run slowly on some systems

**Symptom:** the game can be sluggish or jerky when it starts full-screen, even
where a manually-maximised window runs smoothly.

**Diagnosis:** rendering is pure software (no GPU acceleration). A borderless
window created at full desktop resolution can land on an unaccelerated blit path
on some desktop environments, where a window the OS resizes to the same size
stays accelerated. Same pixel count, very different speed. A wedged compositor
or graphics driver can make it worse, and a reboot often clears that.

**Workarounds today:** reboot if it appears after the system's been up a while;
or start windowed and press `F11` to go full-screen once running.

**Options for a proper fix (not yet applied):** start windowed by default;
render at a fixed internal resolution and scale the finished frame up to fill
the screen (fewer pixels drawn, still full-screen); or add scaling/vsync flags
to the full-screen mode to try to keep the accelerated path.

**Worth knowing before adding features:** this is a real performance ceiling.
Anything that draws or recalculates every frame — a richer aiming overlay, a
per-ball table read — should compute once when the balls come to rest and cache
the result, rather than recomputing while you line the shot up.

---

## 3. The AI is too cautious at distance

The AI plays a complete, legal game — it breaks, pots, plays safeties, and wins
or loses by the rules. It currently errs on the cautious side, declining a lot
of makeable long shots, because its internal difficulty estimate is too harsh
with distance. A dead-straight pot from about two-thirds of a table length is
rated at roughly 9% when it actually drops about 24% of the time.

This affects the AI only. It has no bearing on single-player, where your own aim
is what counts — the human aiming display uses a separate estimate.

**The fix, when it's attempted:** the distance term must be *fitted against
measured results* from the Monte Carlo test rig, not derived from first
principles and hoped for. Deriving-and-hoping is precisely how the term came to
be over-harsh in the first place.

---

## Recently fixed

Resolved in r23 — kept here briefly because the diagnoses are worth having if
anything similar shows up again. Full descriptions are in the changelog.

- **Cue ball couldn't be repositioned after a scratch or on the break.** The
  simulation auto-respotted the white before the rules layer could offer you the
  placement. Fixed with an explicit flag set by whoever builds the simulation,
  so the physics layer still knows nothing about the rules layer.
- **Potting your last colour handed the table back** on a phantom foul.
- **Spin didn't reset between shots.**
- **Sandbox had no ball-in-hand concept**, so solo play couldn't place the white.

---

## A note on how these were found

None of the four r23 bugs were caught by the validation chain — not by the
self-test suite, not by the batch containment run, not by the smoke render or
the byte-identical screenshot check. All four were found by sitting down and
playing a game.

That's worth remembering when adding tests. The suite is very good at pure
functions and physics invariants, and blind to whether a turn passes to the
right player. A scripted play-through test — drive a whole frame through the
rules engine and assert the turn, visit, spin and placement state at each step —
would cover the gap these four fell into.
