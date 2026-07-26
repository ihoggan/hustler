# Known Issues

The honest state of the open threads as of r24. None of these stop the game
being playable. Each is written up with its diagnosis so the next person to
touch it (quite possibly future me) starts from the answer, not the symptom.

---

## 1. Full-screen at startup can run slowly on some systems

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

## 2. The AI is too cautious at distance

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

Resolved in r23–r24 — kept here briefly because the diagnoses are worth having
if anything similar shows up again. Full descriptions are in the changelog.

- **Couldn't place a ball on the pocket jaws in custom mode (r24).** The
  placement test treated the table as a rectangle, which walls off the pocket
  mouths (there is no cushion across a mouth). It now tests against the real
  tangent-true cushion-nose polyline — inside the loop and a ball-radius clear
  of every edge — handling rails and mouths in one rule, no special cases. An
  earlier "exempt the mouths" attempt leaked along the side rails and was
  reverted; the polyline approach has no such failure mode, and the regression
  guard that caught it is still in the suite.
- **Cue ball couldn't be repositioned after a scratch or on the break (r23).**
  The simulation auto-respotted the white before the rules layer could offer you
  the placement. Fixed with an explicit flag set by whoever builds the
  simulation, so the physics layer still knows nothing about the rules layer.
- **Potting your last colour handed the table back (r23)** on a phantom foul.
- **Spin didn't reset between shots (r23).**
- **Sandbox had no ball-in-hand concept (r23)**, so solo play couldn't place the
  white.

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
