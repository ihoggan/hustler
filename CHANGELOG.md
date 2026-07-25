# Changelog

A plain-language history of how HUSTLER came together. Revision tags (R6, r15,
etc.) are the internal build markers used during development.

---

## r23 — single-player gameplay fixes (current)

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
  (full jaws placement still pending — see Known Issues).

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
