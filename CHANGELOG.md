# Changelog

A plain-language history of how HUSTLER came together. Revision tags (R6, r15,
etc.) are the internal build markers used during development.

---

## r27 — the potted-ball chamber clears when the table does (current)

Emptying the table now empties the chamber. In sandbox, re-racking (`T`),
resetting (`R`) or clearing (`C`) rebuilt the table but left the *previous*
frame's balls sitting in the glass, so the chamber quietly accumulated across
frames until it bore no relation to what was actually missing from the table.

The cause is a promise nothing kept. `potted_all` — the game-scoped pot
history added at r22, which the chamber reads — carries a comment saying it is
"never cleared by `strike()`; only a rebuild/new rack resets it." No code ever
did that second part. It went unseen because the game modes are unaffected:
re-racking there builds an entirely new simulation, so the chamber is new too.
Sandbox is the only path that reuses one, and sandbox is exactly where the
game is mainly played.

A new `reset_potted_history()` empties both pot records, called from
`clear_objects()` (which covers re-rack, sandbox clear, the custom-mode clear
button and layout load in one place) and from `rebuild()` — but only when
there are no ball positions to carry over. That condition is the whole care of
the fix: a rebuild *with* positions is a live-slider rebuild, which is what the
ball-radius, cushion-elasticity and rolling-friction keys do, and the frame in
progress survives those. So must its chamber. An over-broad version of this fix
would wipe the chamber every time you nudged the ball size mid-frame, and the
new assertion pins that case specifically.

Also added, unrelated to the above: an assertion guarding the r26 fix. It holds
STEADY's attempt threshold above `POT_FLOOR` as an *invariant* rather than
checking it equals 0.24, because the number likely to move is the floor — its
own comment invites re-deriving it — and if the floor ever rises past the
threshold, r26's bug returns with nothing to catch it.

Found by playing, not by the validation chain. That makes five.

## r26 — STEADY's attempt threshold moved above the distance floor

STEADY (the cautious AI personality) now actually plays cautiously again at
long range. Follow-on from r25: fixing `pot_estimate()`'s distance floor left
both SHARK's (0.10) and STEADY's (0.18) "confident enough to attempt"
threshold sitting BELOW `POT_FLOOR` (0.19) — so any geometrically valid
long or thin shot read as exactly 0.19 and cleared both thresholds
identically, regardless of how different those numbers were meant to be.

`floor_threshold_audit.py`, a new tool, watched 50 real headless AI-vs-AI
games and measured the actual size of this: 30.6% of ALL shots were pots
sitting exactly on the floor, and 88.7% of those would have been a safety
instead if the floor read its old, collapsed value. Not a rare corner case —
roughly one shot in three. Mechanically, `_search()` takes the best pot that
clears `threshold` outright and only falls to a safety when NOTHING clears
it, so once `POT_FLOOR` sits above a personality's threshold, that threshold
stops being able to reject anything.

SHARK's threshold is left at 0.10 — an aggressive personality attempting a
genuine ~19% shot is in-character. STEADY's moves to 0.24, clear of the
floor, restoring its ability to prefer a safety over a bare-floor pot. Re-
running the audit confirms it: STEADY now shows 0% floored pots (its
threshold correctly rejects them) and its safety rate rose from a blended
~9% to 41.8%. SHARK is essentially unchanged (34.5% floored, same as before).

This is a personality-tuning change, not a physics or geometry fix —
`POT_FLOOR` itself is untouched and still measured correct.

## r25 — AI distance calibration

The AI no longer treats long or thin pots as nearly hopeless. A dead-straight
shot from about two-thirds of a table length was rated at roughly 9% when it
actually drops closer to 19-20% of the time — the AI's shot-selection estimate
was declining a lot of makeable long shots, per Known Issues #2.

`pot_estimate()`'s distance handling had two problems, only one of which
turned out to matter. The r16 lever-arm term, which narrows the pocket's
angular tolerance as cue-throw distance grows, is sound physics but had no
floor, so it kept shrinking the predicted pot chance toward true zero the
longer and thinner a shot got. On top of that sat a second, flat
`exp(-t_cue / 10.0)` knockdown with no stated physical basis — the one Known
Issues named as "derived from first principles and hoped for." Measuring
showed the flat term was a minor contributor (an 8-10% reduction at 1 m); the
lever-arm term's missing floor was the real cause.

The fix is `distance_calibration_sweep.py`, a new headless tool that fires
real, physically simulated shots — the AI's own aim-jitter and power model,
not a hand-picked stand-in — across a grid of cue-to-object distance and cut
angle, and compares the measured pot rate against `pot_estimate()`'s
prediction with a Wilson interval on each cell (300 trials/cell). It found
that from about 0.9 m out, measured pot rate goes flat at ~19% (7 cells,
mean 0.192, s.d. 0.016) regardless of exactly how bad the shot gets within
that range, while the old prediction kept falling toward zero. `POT_FLOOR =
0.19` now clamps the prediction to that measured floor via `max(p_aim,
POT_FLOOR)` — a hard floor rather than a blend, deliberately, so it only
bites once the aim-error term has already collapsed below it and leaves the
model's short/mid-range behaviour untouched. The flat decay term is removed
outright rather than retuned.

This is the fix Known Issues #2 called for and is exactly the discipline it
insisted on: fitted against the Monte Carlo rig, not derived and hoped for —
the same mistake that made the term over-harsh the first time. It also
surfaced two new open threads (Known Issues #2 and #3): the floor sits above
both AI personalities' attempt threshold, so a floored shot always clears it
now, and the floor itself is validated at only one pocket/distance
combination.

## r24 — custom-mode jaws placement

You can now set a ball right on the lip of any pocket in custom mode — a hanger
ready to pot — which the placement rule previously walled off.

The old rule treated the table as a plain rectangle and kept every ball a full
ball-radius inside the rails. That is correct along a cushion, but a pocket
mouth has no cushion, so the rectangle blocked the one spot you most want when
setting a trick shot up. Placement is now tested against the real tangent-true
cushion nose: a ball is legal if its centre sits inside the cushion loop and at
least a ball-radius clear of every cushion edge. That single rule handles the
straight rails and the pocket mouths together, with no special cases — which is
what an earlier "exempt the pocket mouths" attempt got wrong (it leaked along
the side rails and was reverted). Balls still cannot be embedded in a rail, nor
set where the pocket would instantly swallow them.

This is the fix flagged as pending in the r22 notes and Known Issues #1.

## r23 — single-player gameplay fixes

Four bugs, all found by actually playing the game rather than by the test
suite. That's the headline: the validation chain (compile, self-test, batch,
smoke, screenshot) caught none of them, because every one lived in the
gap between a rule and the thing that rule was supposed to control.

- **Potting your last colour no longer hands the table back.** Clearing your
  colours and going on to the black was being scored as a foul. The rules were
  asking "what was this player allowed to hit?" *after* the shot's potted balls
  had already been taken off the table — so potting your final colour made it
  look as though you should have been on the black all along, and your own
  perfectly legal shot was judged a wrong-ball foul.
- **Spin now resets between shots.** Choosing bottom (draw) once applied it to
  every subsequent shot, and the spin pad wouldn't de-select. The shot was
  reading the spin correctly but never clearing it afterwards.
- **The cue ball can be repositioned after a scratch and on the break.** The
  simulation was putting the white straight back on the baulk line the instant
  it dropped — behaviour left over from before the rules layer existed — so you
  were "placing" a ball that had already been placed for you. Potting the white
  now simply removes it and leaves the placement to you. A related fix: ball in
  hand is now granted after *any* foul, not only a scratch, per the rules.
- **Sandbox play gets ball in hand too.** People play solo on pool tables, so
  sandbox mode now lets you place the white at the start of a rack and whenever
  you pot it — it previously had no concept of ball in hand at all.

Also fixed: the baulk highlight (the shaded area showing where placement is
legal) was checking a player's *name* where it should have checked whether that
player was human, so it had never once appeared in a game against the AI.

## r22 — single-player polish

- The game now starts **full-screen** instead of in a small window.
- The **potted-ball chamber** now stacks every ball potted during a game, in
  order, so you can read back the whole frame — previously it only showed the
  most recent shot.
- Trimmed an over-cautious margin around the pockets in custom-mode placement
  (full jaws placement completed later, at r24).

## r19–r21 — AI study tools and calibration

- Added a **per-shot study log** (JSONL) and a calibration report, so the AI's
  shot-quality estimates can be measured against what actually happens.
- Fixed the AI's obstruction check to account for aim variation, and to use the
  true clearance a ball needs.
- Corrected the calibration measurement to exclude "free shots," where the AI
  may legally strike any ball first.
- A long investigation into the AI's shot-quality estimate concluded that the
  estimate itself is sound; remaining differences come from shot selection, not
  from the physics. (One over-harsh distance term is noted for a future pass.)

## r18 — fairer AI matchups

- The two AI personalities (SHARK and STEADY) were re-tuned so they differ only
  in *strategy*, not in raw aiming skill — making an AI-vs-AI result a genuine
  test of tactics rather than of who aims straighter.

## r17 — performance

- Made the AI-vs-AI games roughly four times faster (pocket detection moved into
  the physics engine's own collision handling; games can run in parallel),
  every step verified to leave behaviour unchanged.

## r16 — AI shot-quality fix

- Fixed a significant flaw in how the AI judged the difficulty of a shot, which
  had been making it wildly over-confident and causing it to attempt almost
  everything.

## r15 — study output

- Added seeded, reproducible AI games with a per-shot log and confidence
  intervals — the foundation that made all the later measurement work possible.

## r13–r14 — ball in hand and the aim overlay

- **Ball in hand:** the cue ball can be placed within the baulk area on the
  break and after a foul (the modern UK rule; the "D" is not used).
- **Aim overlay:** a richer aiming display — layered aim lines, a translucent
  ghost ball, a pocket glow when a pot is on, and a predicted cue-ball
  resting position. The aim line's colour shows the pot chance (red → green).

## r9–r12 — rules, HUD, custom mode, chamber

- A full **rules layer**: fouls (wrong ball first, no contact, no cushion,
  scratch), free shots, two visits after a foul, and evaluated safety play.
- **Fine aiming controls** — angle to a hundredth of a degree, a spin pad with
  nudge buttons.
- **Custom mode** — clear the table and place balls freely, with four save/load
  layout slots.
- **Potted-ball chamber** — a glass-fronted readout of what's been potted, in
  order (the cue ball is excluded, since a scratched cue returns to play).

## r7–r8 — graphics and sound

- **Table graphics:** cloth shading with an overhead-light falloff, wood-grain
  rails, and cushions correctly coloured as felt-green cloth.
- **Sound:** ball contact reworked from scratch into a solid polymer "knock" —
  synthesised, like everything else, with no audio files.

## R6 — foundations

- Integrated the tangent-true cushion geometry, finalised the WEPF table spec,
  and settled on the classic (software) renderer and the tabbed control panel.

---

*Older internal detail lives in the project's development notes.*
