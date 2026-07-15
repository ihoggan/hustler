# Known Issues

The honest state of the open threads as of r22. None of these stop the game
being playable. Each is written up with its diagnosis so the next person to
touch it (quite possibly future me) starts from the answer, not the symptom.

---

## 1. Cue ball can't be repositioned after a scratch or on the break

**Symptom:** when the white is potted, or at the break, you can't drag the cue
ball to where you want it. Ball-in-hand looks like it should be available but
the placement doesn't take.

**Diagnosis (real bug, not a missing control):** the moment the white drops,
the simulation auto-respots it onto the baulk line and puts it straight back
into play. This is leftover *sandbox* behaviour from before the rules layer
existed — the sim was built never to be without a cue ball. Meanwhile the rules
layer separately grants you ball-in-hand (a scratch is a foul, and the break
allows placement). So the sim has already decided where the white goes before
you get a say: you're holding ball-in-hand over a ball that's already been
placed for you.

**The fix (not yet applied):** the auto-respot should not fire when the rules
layer is driving — potting the white should simply remove it and let you place
it. The respot stays as a fallback for pure sandbox play. This needs a small
architectural decision, because the physics layer deliberately knows nothing
about the rules layer, and that separation is worth keeping.

---

## 2. Can't place balls right on the pocket jaws in custom mode

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
existing geometry, so it doesn't disturb the table spec.

---

## 3. Full-screen at startup can run slowly on some systems

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

---

## A note on the AI

The AI plays a complete, legal game — it breaks, pots, plays safeties, and wins
or loses by the rules. It currently errs on the cautious side (it declines a lot
of makeable long shots), because its internal difficulty estimate is too harsh
at distance. This affects the AI only; it has no bearing on single-player, where
your own aim is what counts. It's a known, measured issue with a clear fix path
and is noted for a future pass.
