# Changelog

A plain-language history of how HUSTLER came together. Revision tags (R6, r15,
etc.) are the internal build markers used during development.

---

## r60 — the machine only resolves fixtures it can actually play (current)

Found the moment r59 shipped, in the Maker's own terminal output. `--league`
ended with:

```
your next fixture: season complete
AI fixtures still to resolve: 7
```

Both lines are wrong. Seven fixtures were left and every one of them was
**his**. Running `--league resolve` on that crashed:

```
AttributeError: 'NoneType' object has no attribute 'choose'
```

### Why

The CLI took the human's name from `os.environ.get("HUSTLER_PLAYER", "PLAYER")`
— and PLAYER is nobody. `league_pending_ai` excluded fixtures containing "the
human", so with the wrong name it excluded nothing, handed MAKER to
`play_ai_game`, and `league_ai("MAKER")` returned None four frames down.

**This was filed as KNOWN_ISSUES #6 at r56 and called unreachable**, on the
reasoning that the pending list already excludes the human. That was true of the
menu, which passes a real profile name, and false of the CLI, which passed a
guess. The note said at the time that "harmless because nothing exercises it"
has a shelf life. It lasted three releases.

### The fix, in three places

**Stop asking who the human is; ask who the machine can play.** The pending
lists now screen on `league_playable_by_ai()` — is this name on the ladder —
which is a question the CLI cannot get wrong, because it does not depend on
knowing anything about the caller. It also closes the hand-edited-nickname route
the original issue was actually about.

**`play_ai_game` refuses an unrostered name and says which one**, rather than
raising an AttributeError from deep inside the shot loop. Same posture as r53's
seat check: say who.

**`default_human_name()` asks the profile store.** It has marked the human seat
with `kind == "human"` since r49 and nothing ever read it. `HUSTLER_PLAYER`
still wins; the fallback is now the data instead of a guess. This also fixes a
quieter version of the same bug in the GUI, where a career reverted to a
stranger on every launch unless the variable happened to be set.

No league file was harmed: the crash happened before the write, verified
byte-for-byte against the original.

### Notes

**A mutant survived, and the reason is worth writing down.** Screening only the
`home` side of a fixture passed cleanly — because `league_fixtures` pins the
first player, so listing MAKER first made him the home side in all seven of his
fixtures and an away-side bug could not appear. Moving him to fourth gives home
3, away 4, and the mutant dies. That is the **third** time test data has hidden
a bug here (r56 alphabetical seeding, r59 interval bounds), and all three were
the same mistake: a fixture chosen for convenience rather than to make the
failure visible.

Self-test **118**. `--snap` byte-identical at `62c87ddb…`.

---

## r59 — rankings: who you beat, not just how many

Fork D, signed off at r57 and built now. The league has produced results since
r52 and nothing has ever said who is actually **better** — only who has the most
points, which is a different question.

### Why this is not Elo

Elo is the obvious reach and it is the wrong tool here. It is an **online
approximation**: it exists for open pools where history cannot be recomputed, so
it updates incrementally and carries a K-factor and a starting rating, both
invented. Worse, it is **order-dependent** — the same 28 results fed in a
different order give different ratings. Everything else in this game is derived
on read from the stored results, and a ranking that changed depending on which
fixture you happened to resolve first would be the one number in HUSTLER that
could not be reproduced.

**Bradley-Terry** solves the whole result set at once. Player i beats player j
with probability `p_i / (p_i + p_j)`, fitted by the standard MM update — no
derivatives, no step size, no numpy, no constants to invent. Same results, same
answer, always. Normalised so **1.00 means average**, which makes seasons
comparable.

### The prior is a named trade, not a magic number

Without it, an unbeaten player has infinite strength: the likelihood keeps
rising as their rating climbs and never turns over. BULLET went 6 from 6 in the
live season, so this is not hypothetical. `BT_PRIOR = 0.5` adds a half-win and a
half-loss against an imaginary average opponent — worth about one game, so a
seven-game season keeps its shape while every rating stays finite. Measured: an
unbeaten player sits at **3.31** with the prior and **1e+24** without.

### The table did not move, deliberately

`playoff_seeds` reads `league_standings` directly, so re-sorting the table by
strength would silently re-draw the play-offs. **Points decide the season;
strength only describes it.** The menu standings gains a `str` column and keeps
its points order; `--league` prints a separate ranking block underneath, sorted
by strength, with the Wilson-bounded win rate beside each entry — because at
seven games a win rate is a hint, not a measurement.

On the live season: BULLET 12.99, then CHALKY/MAGPIE/SHARK at 1.95, MAKER at
1.00 on nothing played, and DOC/SPIDER/STEADY at 0.22.

### Notes

`prior=0` used to raise `ValueError: math domain error` — a winless player hits
exactly zero and `log(0)` took the whole menu down. The normalisation is now
floored, so an unregularised fit degrades into very large and very small numbers
instead of crashing. That is the honest picture of a likelihood that does not
turn over.

Assertion 117's fixture is built so the two orderings **disagree**: B wins three
against players who have won nothing and tops the table; A wins two against
players who have won three each and tops the ranking. That pins the feature to
the property it exists for rather than to its own output.

**Three mutants survived the first pass.** One was benign — MM converges to the
same optimum from any starting vector, so perturbing the seed is not a bug.
The other two were real and both were inequalities that could not see a wrong
number: removing the prior's *games* from the denominator while leaving its
*wins* in the numerator stayed bounded and correctly ordered, and replacing the
Wilson bounds with a flat 0.0-1.0 satisfied `lo < rate <= hi` perfectly. Both
are now pinned to literals.

Self-test **117**. `--snap` byte-identical at `62c87ddb…`.

---

## r58 — solo you can actually get to, and the flag that ate a clearance

The Maker's requirement, in their words: solo is fine **"as long as it is
accessible for practice sessions and it records and displays the data"**. r57
did the recording. This is the accessibility — and a defect r57 introduced,
found while checking it.

### Solo was three keypresses deep with no route from the menu

`Practice` sets no mode. It closes the menu and leaves you in whatever mode was
already up, which at boot is SANDBOX. To reach SOLO you pressed **M three
times**, cycling through two AI modes, each press tearing down and rebuilding a
frame.

So the mode that is **65% of every shot the Maker has logged** had no way in
from the career shell at all. SOLO now has its own full-width menu row, and the
button carries the target before the clock starts:
`Solo — timed clearance  (PB 4:25.2)`. Practice keeps doing exactly what it did
— a free table and a timed clearance are different things, and both get used
(108 practice rows against 295 solo).

### The flag that ate a clearance

r57 kept six separate locals for the run state and reset them in **one**
routine: `do_rack`, i.e. pressing T. `do_cycle_mode` reset three of the six.
`do_reset_solo` reset the same three. So:

- clear a rack — `recorded` becomes True;
- reach SOLO again by cycling, or press reset instead of T;
- clear another rack — the write is guarded on `if not solo_recorded`, which is
  **still True**, and the run is dropped in silence.

A run that said it counted and did not — precisely the fault r57 was written to
remove, reintroduced by the release that removed it. The same staleness put a
`★ NEW BEST` on runs that had not earned one, and could disqualify a legitimate
rack from setting a best.

The cure is structural rather than a fourth careful reset: `new_solo_session()`
returns the complete state, `solo_reset()` is the only thing that applies it,
and all three routes call it. A caller can no longer reset half of it. Same
shape as r49, where two routines stood a frame up and drifted apart.

One subtlety kept: `do_reset_solo` does not re-rack, so an arranged table is
still arranged and `keep_table=True` preserves the rack-standard flag. Resetting
it there would hand out a personal best for laying out an easy rack and pressing
reset instead of T.

### Notes

**The assertion found a third broken path before it shipped.** Written to cover
`do_rack` and `restart_frame`, it failed on a source clause that said no partial
reset survived anywhere — because `do_reset_solo` still held one. That was not
in the brief and would have gone out.

**And a mutant survived the first pass**, again for the r56 reason: the
`keep_table` check was on the *call site* text, so gutting the guard inside the
closure left the call written and the behaviour gone. Moved into a pure
`solo_session_after_reset()` and asserted on what it returns. Seven mutants,
all caught, each verified as actually applied — a mutation that fails to apply
reads exactly like a caught one.

Self-test **116**. `--snap` byte-identical at `62c87ddb…`.

---

## r57 — a solo run leaves a trace

The Maker was asked whether to follow the roadmap (rankings) or their play. They
said **play over the roadmap**, and the shot log says they were right.

**295 of their 454 logged shots are solo — 65%.** Practice is 108, tournament 51.
And a solo clearance was recorded *nowhere*. The run ended, the strip printed
`CLEARED 4:32.5 — 27 shots, 1 foul — T = rack`, and pressing T threw it away.
`record_frame` is only reached from the game-mode block; solo never touched it.

The shot log could not rebuild it either: solo rows carry no clock, no run
boundary and no verdict, and only 22 of 295 have a session stamp at all. Runs
were separable only by watching the ball count jump back to 16. Done that way:
**twelve runs, nine of which reached the black.** All gone.

Which is worth stating plainly. Eleven releases, r46 to r56, built a tracked
record-keeping system — profiles, standings, Grannie counts, trophies, a
play-off bracket — for a league the Maker has played **zero** fixtures of, while
the mode that is two thirds of their play remembered nothing.

### What is stored

A completed run now writes to the player's profile: elapsed time (with the foul
penalty already inside it, as the strip shows it), shots, fouls, the verdict,
and whether it began from a standard rack. `PROFILE_SCHEMA` goes to 3.

**This is the one place the project stores an aggregate rather than deriving
it**, and the exception is deliberate rather than a lapse: a clearance time
cannot be recovered from the shot log, because it was never written down.
Derive-on-read cannot rebuild what does not exist. The *best* is still derived —
recompute the ranking, keep the record.

**Every attempt is stored, not just the clearances.** Nine of twelve runs
reached the black; the three that did not are the interesting ones, and "how
often do I actually finish" is a question only the failures can answer.

**Only a cleared run from a standard rack can set a best.** Solo stays editable
until the first strike, so a player can arrange an easy table and then start the
clock. Those runs still record — they just cannot set a best, because a best you
can beat by laying out a simple rack is not one.

### What is shown

`SOLO 2:14.3   6 colours + black  (PB 4:25.2)` while a run is on, and
`CLEARED 4:12.0  ★ NEW BEST` when one lands.

The best **rides on the two lines that already exist and never adds a third**.
That cap is r37.1's and it is load-bearing: the strip clips silently, and r37
lost a whole finished-state line exactly that way.

Measured before it was written, and the measurement changed the design. The live
SOLO line is already 344px against a 240px strip budget at 1.0 scale — a
pre-existing overflow — and appending a best would have taken it to 448px. So
the suffix is **dropped when there is no room** rather than shortened. In the
band, where the readout has lived since r47, the budget is 996–1734px and
everything fits at every scale. A NEW BEST is never dropped: it measures
217–351px against strip budgets of 240–370px, so it fits regardless.

`--profiles` grows a solo line: runs, clearances with a Wilson interval, best.

### Notes

Assertion 115 was mutation-tested seven ways, all caught. The one worth naming
is the r48 fault: `serialise_profile` rebuilds a profile field by field rather
than copying it, which is how `grannie` and `trophies` were silently dropped on
the round trip once already. Deleting the new `solo` block from the serialiser
fails 115 — a run that survives the frame and dies on the save would be worse
than one never recorded, because the strip said it counted.

`standard_rack` defaults to **true** on read: every run recorded before the
field existed came from a normal rack, and defaulting it false would silently
disqualify a real best.

Self-test **115**. `--snap` byte-identical at `62c87ddb…`.

---

## r56 — play-offs, trophies, and three things that were quietly wrong

The last item of the league brief, and the thing `award_trophy()` has been
waiting for since r48 — it was written then and nothing has ever called it.

### The bracket

Eight players, so **everyone qualifies**. That is the Maker's choice and it
changes what the round-robin is for: the season stops being a qualifier and
becomes purely a seeding exercise, which is the only reason a table you finish
eighth in is still worth playing out.

The final table seeds it, and there is **one pairing rule used throughout**:
fold the field, first against last. In the opening round that is 1v8, 2v7, 3v6,
4v5; applied again to the winners it puts the 1/8 winner against the 4/5 winner,
which is what keeps the top two seeds apart until the final. Pairing the winners
in the order they come out is the obvious way to write it, and it is wrong —
seeds 1 and 2 meet in a semi. Both produce a plausible-looking bracket, which is
why the self-test checks it rather than trusting the eye.

Ties are **derived on read** from the seeds plus the recorded results, the same
way standings are derived from fixtures. A stored bracket is an aggregate, and
r16 is why this project does not trust stored aggregates.

### Two decisions, both the Maker's

**Losing does not stop the tournament.** Knocked out, it carries on without you
— a trophy you cannot lose is not worth winning, and a season with no champion
is a hole in a record that is meant to be permanent. The remaining ties resolve
when you press the button, not in a stall you did not ask for.

**The bracket is strict to play and provisional to view.** Playing it needs all
28 fixtures in, because a bracket seeded from a part-played table is seeded from
a lie: a player sitting eighth on nothing played is not eighth, they are
unmeasured. But waiting seven frames to see the feature at all is a long time to
show nothing, so the screen displays the bracket **today's table would make**,
dimmed and labelled as provisional, and your seed climbs as you play.

### The champion's trophy

`playoff_trophies()` is the caller `award_trophy()` never had. It is idempotent
even though award_trophy allows duplicates on purpose — winning the same
competition twice is two trophies, but reading the same finished bracket twice
is not, and this runs every time a frame ends.

The league is also now settled **before** the profiles are written rather than
after. That order did not matter while a result only changed a table; a play-off
result can put a trophy on a profile, and a profile written before the tie is
recorded is a profile written one frame too early.

### Three things that were quietly wrong

**You have never seen your own row in your own league table.** The standings box
was 214 units at 24 a row, which fits a header and *seven* rows. The row that
fell off the bottom was the eighth and last seed — which, all season, has been
the Maker's. The highlight colour marking your line has never rendered once.

**The Resume button had the footer printed over it.** Resume ran 636→670 while
the two footer lines sat at 634 and 654, and the footers draw last: 36px of
overlap at 1.0 scale, 54px at 1.5.

Both are the same fault — fixed offsets that must be re-totalled by hand every
time anything moves — and it is the third time this project has hit it (r41
button rects, r42 strip leading). The menu is now laid out on a **cursor**, and
the panel height is derived from the stack instead of the stack being crammed
into a hardcoded 560. A cursor cannot get the total wrong. The standings box
asks the league how many players it has, so a bigger division grows the box
rather than silently truncating it.

**A season was never reproducible, and the docstring said it was.**
`league_resolve_ai` derived its seed from `abs(hash(key))`, and CPython salts
string hashing per process: the same fixture drew 106203, 62979 and 49318 on
three consecutive runs. Order-independence within one run was real; the
reproducibility promised in the docstring was not, and nothing ever failed
because no test asked the same question twice in two processes. `stable_seed()`
uses CRC32 — stdlib, fixed by standard, identical on every platform.

### Honest notes

Laying out the bracket screen, the button row was written with fixed offsets and
at 1.5 scale the Resolve button ended at x=1131 in a 1024-wide window — the
exact fault this release exists to fix, reproduced within the hour of fixing it.
It now runs on a cursor like everything else, and was re-measured from 1024x768
to 3840x2160.

Assertion 114 was mutation-tested nine ways and **two survived the first pass**.
One was a weak mutant. The other was a real hole: seeding the bracket
*alphabetically* passed, because the seed checks compared `playoff_seeds` to
itself, and the test data's runaway leader happened to also be first in the
alphabet. Fixed by asserting that points never rise down the seeding.

Self-test **114**. `--snap` byte-identical at `62c87ddb…`; the bracket is gated
on `smoke` exactly as the menu is.

---

## r55 — a league you can play, and fouls that get written

Three fixes, all of them things the first season exposed.

### Play now starts your fixture

The menu showed a league table and then handed over a **sandbox**. `mode = 0` at
startup, so Play dropped you on a practice table with no game, no opponent and
no fixture — the league marker could never appear, because sandbox has no Game
at all. To play your fixture you had to know to press M twice, and nothing said
so. Career mode you can read and cannot play.

Play now sets YOU vs AI (resolved by NAME, r30's rule), seats the fixture's
opponent and racks up, and the button says which fixture: `Play MAKER v SPIDER`.
**Practice** gets its own line, doing what Play did before.

### The ladder matches on jitter, so the league tests temperament

The first ladder spread `aim_jitter` as well as strategy, and the first season
showed precisely what r18 warned it would: the two straightest cues finished
first and second, and the table could not say whether DOC went unbeaten for
being patient or for aiming better. The jitter/wins correlation was −0.20 across
21 fixtures — weak, and pointing the wrong way for a league that is supposed to
be about how people play.

Every player now shares `STUDY_JITTER`, which is r18's own constant, introduced
to remove this exact confound from the two-player study. Strategy is the only
difference between eight players. The eight strategies stay distinct — matching
the skill must not flatten the personalities into eight copies of one player,
and assertion 113 checks that too. `default_ais()` is untouched, so the study
log stays byte-reproducible.

**The cost, stated plainly:** every opponent aims equally straight now. A weaker
player who misses more is a *skill ladder*, which is a different feature — and
mixing the two is what made the first table unreadable.

### KNOWN_ISSUES #5, closed

The `foul` field was null on every human row. The diagnosis at r44 was right —
the log write sits above the game block, so `on_rest()` has not decided the foul
and `last_event` still describes the previous shot — and the dismissal was
wrong. It was filed as "harmless because the log has no game-mode rows". The
league produced fifty, every one logging a null foul in the mode the Maker would
now be playing most.

The row is HELD now and flushed once the rules have spoken, using the same
fouls-delta the AI study path has always used. Sandbox and solo rows still go
straight out: there is no Game to wait for.

**"Harmless because nothing exercises it" is a statement with a shelf life.**
This one expired the moment a feature started exercising it.

---

## r54 — walk away mid-frame and come back to it

The last item from the Maker's original league brief, designed at r52 and built
after five other things. Their reason: walking away from a digital game and
loading it back is the modern computer way.

**The frame autosaves at rest, between shots, and only there.** That single
constraint is what makes it small — at rest every velocity is zero by
definition, so there is no momentum to capture and no physics to reconstruct.
What is left is where the balls are and whose turn it is. Saving mid-shot would
mean serialising a live pymunk space, and would be pointless besides: nobody
walks away from a table with the balls still rolling.

Positions ride on `serialise_layout()`, which has stored METRES since r10
precisely so a layout saved at one window size loads at another — selftest 37
has covered that round trip for forty revisions, and this inherits it.
Alongside them go the colour assignment, whose turn it is, visits, fouls, shot
count, free shot, visits left, ball in hand, and the fixture it belongs to.

**Resume sits in the menu, and only when there is one.** A dead button that
does nothing is a worse answer than no button, so it reads "no frame in
progress" until there is one, and then names the fixture: `Resume MAKER v
SPIDER (league)`.

**A save that is missing anything is refused outright.** Not half-restored — a
resume that quietly lost the colour assignment, or came back with the wrong
player to shoot, would have you carrying on from a position that never existed
and noticing several shots later, by which point it is unrecoverable either
way.

**Not tracked, deliberately.** `hustler_resume.json` joins the layout slots in
`.gitignore`. The shot log, the profiles and the league are RECORDS that grow
and get committed as they grow; a half-played frame is true only while you are
away from the table and meaningless the moment you sit back down.

**And a resumed frame is not a break.** r39's flag would otherwise mark the
next shot as one, and the shot log would quietly report a second break in a
frame that only ever had one.

### The validator was written against an assumption

`serialise_layout()` returns a dict, not a list. The reader checked for a list
and therefore refused every real save. The round-trip assertion caught it on
its first run — but only because it round-tripped through actual
`serialise_layout()` output rather than a hand-built fixture, which is the
whole reason to test against the real thing.

---

## r53 — the season moves into the shell

"Can I not select league mode in the game?" — no, and the honest answer was
worse than that. The league existed only at the command line. A fixture was set
as your opponent without saying so, the result recorded without ever showing
you a table, and starting or resolving a season meant dropping to a terminal.
Career mode you cannot see is not career mode.

The menu now carries the standings, your position highlighted, Grannies where
they have happened, and two buttons: **New season** and **Resolve AI**, the
latter showing how many fixtures are outstanding.

**Resolving blocks, and says so.** Roughly 3.2 seconds a frame, so it goes a
round at a time — four fixtures, about thirteen seconds — with the message
drawn and flipped before the work starts. Bounded and explicable beats a single
long stall with nothing on screen, and it is honest work rather than a progress
bar over a statistical shortcut: the Maker's requirement was that AI results
are earned on the same table they play on.

**New season refuses while one is running.** A league is weeks of play, the
button sits next to Play, and there is no undo behind a tracked file that has
just been overwritten.

**And the band says when a frame counts.** A league fixture is an ordinary YOU
vs AI frame that happens to be the one the season is waiting on — which is what
lets the result record with no second mode to be in, and also exactly what made
it invisible. `LEAGUE — MAKER v SPIDER` now sits where the mode name was. That
is also why league is NOT a mode: the modes describe how a frame is played, and
a fixture is not a different kind of frame.

### Two mutants that survived because the test matched the wrong line

The new-season guard was checked by looking for
`league_next_fixture(menu_league, profile_name)` in the source — which also
appears in the band marker. Gutting the guard left the clause matching the
other occurrence, and the mutation passed. Same for the batch size. Both are
matched against text unique to each guard now.

It is the third time this session a source-level assertion has been fooled by
its own subject: r50's comments quoted the bug it searched for, r50's picker
cap shared argument text with the aim call, and now this.

---

## r52.1 — you can actually play your fixtures

r52 built a league of eight and left the opponent picker offering two. The
Maker's first fixture was MAKER v SPIDER, and there was no way to put SPIDER on
the table — asking for one silently seated SHARK, and since SHARK was not in
the fixture the frame would not have counted either. The loop was open at
exactly the point they would have walked into it.

Three fixes, and the first two are the same lesson twice.

**`OPPONENT_ROSTER` is DERIVED from the ladder**, not maintained beside it. It
was `("SHARK", "STEADY")` from r49.1, when those were the only two AI with
parameters, and r52 added five more without widening it. A hand-kept copy of a
list that grows is the fault r49 spent a whole revision removing.

**`ais_for_seats()` seats from the ladder too.** It looked players up in
`default_ais()`, which only ever held SHARK and STEADY — so any other league
opponent resolved to `None` and would have crashed the moment it took a shot.
`default_ais()` itself is still untouched, because the study log's
byte-reproducibility rests on it.

**The fallback is no longer silent.** A name the seat cannot seat still falls
back — a GUI must not crash because a stale name reached it — but it now says
so, on screen. r49 was an entire revision about a seat whose name and occupant
disagreed, and falling back without a word is precisely how that happened.

**And the opponent now defaults to your next league fixture.** Walk in, press
play, and you are playing the game the season is waiting on. The picker still
cycles the whole ladder for a friendly.

### An assertion that had baked in a size

Widening the roster broke assertion 103, which asserted
`next_opponent("STEADY") == "SHARK"` — true only while STEADY happened to be
last in a two-name list. The code was right and the test was stale. It is
stated against the roster now: every name maps to the next, the last wraps to
the first, and an unknown name starts from the top, whatever length the ladder
grows to.

---

## r52 — the league

Eight players, twenty-eight fixtures, a table. `--league new` starts a season,
`--league resolve` plays out the AI ones, `--league` shows where you are.

**Five new opponents.** The ladder needed eight and only two had parameter
sets. BULLET, DOC, MAGPIE, CHALKY and SPIDER are drafted like their names
were — expect re-tuning once there are results to tune against. `aim_jitter` is
spread across them with strategy varied independently, because r18's whole
point was that skill and strategy are separate axes; eight players differing
only in straightness would make the table a ranking of one number.

**SHARK and STEADY keep the exact parameters `default_ais()` gives them, and
that function is untouched.** The study log is byte-reproducible for a fixed
seed and r17 proved three optimisations behaviour-preserving by diffing it. A
league that re-tuned the study's two players — or even reached them by a
different route — would retire the technique without failing anything.
`play_ai_game(names=None)` runs exactly the code it ran before; `--aigame 12
--seed 4200` still returns SHARK 9-3.

**AI fixtures resolve by playing real frames**, not statistically. Measured at
~3.15s each here, so 21 fixtures is about a minute. The seed is derived from
the fixture rather than a counter, so resolving in a different order changes
nothing and a season replays identically.

**Your own fixtures count automatically.** A finished frame is matched against
your next league fixture by OPPONENT rather than by a "league mode" flag, so
there is no way to play your fixture and have it not count, and no second mode
to forget you are in. `league_record()` refuses to overwrite a fixture already
played, so a rematch is just a friendly — a league whose table depends on what
you did most recently rather than what you did is not a league.

The table is computed from the played fixtures on every read, never stored.
Same reasoning as profiles storing frames, and the same scar behind it: r16
found `pot_estimate` five times over-confident and every conclusion drawn from
a stored aggregate had to be thrown away.

### A bug found on the way, and it was mine

The profile write at frame end had a **duplicated exception handler**, shipped
since r48 and carried through five releases:

```
except OSError:
    pass
    with open(...)      # a retry, inside the handler
except OSError:         # a sibling handler, which cannot catch it
    pass
```

So the "a frame is not worth losing the game over" guard was defeated by its
own duplicate: a failed profile write retried inside the handler, and that
second exception escaped uncaught and would have taken the game down at the end
of a frame. It only fires when the disk write fails, which is why nobody has
seen it. Introduced by my own r48 edit leaving the original block behind, and
found only because r52 needed to write to that same spot.

---

## r51 — the career shell

The game boots into a menu now: your name, your nickname, and a way onto the
table. **Skippable**, per the Maker — Escape plays. Escape from the table
returns here, which is a change of meaning after eleven revisions of it
quitting outright, so Q still quits from anywhere.

It is drawn OVER the table behind a scrim rather than instead of it, so
skipping the menu feels like stepping forward rather than loading a level.

### The first text entry in the project

Everything until now has been a button, a slider, a dial or a tab strip — which
is precisely why the game could treat **every letter key as a global
shortcut**. M cycles the mode, T racks up, G toggles the overlay, O swaps the
opponent. Typing "Steady" into a field that had not properly taken the keyboard
would rack up, cycle the mode and toggle the overlay on the way past.

So a focused field takes the keyboard whole, and `text_edit()` is pure — the
focus rule at the call site is then the only thing that can get it wrong, and
it is one line. The filter is on the CHARACTER rather than a list of key names,
because arrows and modifiers arrive with an empty `unicode` and Return and
Backspace arrive with control codes, and a name written to a tracked file must
not be able to contain either.

### Naming yourself moves your career

The Maker played two frames before there was any way to enter a name, so they
are recorded under the default key `PLAYER` and already committed. Their
instruction was "Rename for me and I will keep that profile", so
`rename_profile()` MOVES the career rather than starting a fresh one beside it.
It merges if the target already exists: a career is a list of frames, and
dropping some to a rename would be the one thing it exists to prevent.

### The gate

`--snap` runs `run_gui(smoke=True)` and saves the presented frame. A menu that
could appear there would rewrite a baseline unchanged across thirteen releases.
There are **two** gates — on `menu_on` and on the draw call — and a mutation
test showed why that matters: removing either one alone leaves the snap
byte-identical, because the other still holds. The md5 could not have caught
it, so assertion 107 pins both in source.

Still to come: league fixtures and standings, which is what the shell was built
to hold.

---

## r50.1 — the power slider stops being dwarfed

With the full-size dial and picker now sitting on the Shot tab, the power
slider looked tiny beside them. It was: **every dimension of the widget was a
fixed pixel.** A 6px track, 20px down from the top of its rect, a radius-7
knob, a 14px grab margin — identical at 1.0x and at 1.5x, while the dial next
to it grew to 300px across.

That is the fourth revision to find this same fault somewhere new: r41 in the
button rects, r42 in the strip leading and the call clamp, r50 in the spin
picker's cap, and now here. Each looked correct at exactly one HUD scale.

At 1.5x the track goes **6px to 15px** and the knob **7 to 11**. The power
slider also gets a taller rect than the Table tab's, because it is the one
control used on every single shot.

**Two changes to how the geometry is derived, both worth keeping.** The track
is anchored to the BOTTOM of the widget rect rather than a fixed drop from the
top, so a caller that wants a chunkier slider simply hands it a taller rect and
the label keeps its room automatically. And the track is now INSET by the knob
radius at each end — without that the knob's centre sits at the track's end, so
at full power half of it hung off the panel edge. It always did, at every
scale, unnoticed because 7px of a white circle over a dark panel reads as a
rounded end rather than as a mistake.

`slider_geometry()` is pure, so assertion 106 can pin all of it: scaling, the
inset at both ends, a taller rect giving a lower track rather than a clipped
label, and the label clearing the track at every scale and rect height.

---

## r50 — the cue controls live on the Shot tab

The Maker asked why spin and angle each had a whole tab when they belong where
the shot is taken. Measuring it agreed, and turned up a defect on the way.

**The Aim tab held nothing but a second copy of the dial** — and already the
same radius as the Shot tab's at three of four window sizes. It cost a click
and gave nothing.

**The Spin tab looked like it earned its keep** — 150px against the Shot tab's
100 at 1.5x — but that gap was a bug, not a decision. The Shot call passed no
`r_max`/`r_min`/`extra`, so `spin_group_radius()` fell back to its UNSCALED
defaults and capped the picker at 100px at every HUD scale, while the aim call
three lines above always passed `U(100)`. A fixed pixel inside a scaled layout:
the same family r41 and r42 kept finding, and missed because r41 scaled the
literals inside `build_panel_widgets` and not the arguments handed to a pure
function.

Fixed, the Shot tab's picker reaches **150 at 1.5x and 125 at 1.25x**, matching
what the dedicated tab used to give. So the tab had nothing left to offer:

| window | aim, before / after | spin, before / after |
|---|---|---|
| 2160x1350 | 150 / **150** | 100 / **150** |
| 1920x1080 | 125 / **125** | 100 / **125** |
| 1024x768 | 100 / **100** | 83 / **83** |

**What was Spin is now Call**, holding the nomination table alone. The caller
was put under the picker at r33 for the room, never because it belonged there;
it now starts at the top of its own tab rather than a third of the way down
someone else's, which is why its fit-or-omit test almost always passes.

Five tabs also un-crowds the strip. Six were overflowing their cells by 2-3px
at 1.25x and 1.5x — the widest label rendered wider than its share. Five leaves
10-13px spare at every size.

**One capability is genuinely lost, at one window size.** At 1144x548 — the F11
windowed size — the Shot tab cannot fit a spin picker, and there is no longer a
Spin tab to fall back to. The aim dial there also runs at 73px rather than 100.
Everything at desktop size is unaffected or better.

### Two assertions that did not work first time

Assertion 105's first cut failed with every value in its own diagnostic
correct: it searched the raw source for `panel_tab == 3`, and this file's
comments deliberately QUOTE that as r30's warning. Checking a warning about a
fault reports the fault. It strips comment lines now.

Then a mutation stripping the scaled arguments back off survived **twice** —
first because the assertion tested the pure function rather than the call site,
and then because the aim call three lines above carries the identical argument
text, so the substring was still present. It counts both calls now.

---

## r49.2 — a real name and a nickname

The first real career got written, and it read like a list of parameter sets:
`PLAYER` beat `SHARK` twice. The Maker's model is how pub players actually
work — Joe Bloggs known as Bullet — so a profile now carries both. The
nicknames were already here; SHARK and STEADY are exactly that register. There
was simply nowhere to put a name.

Eight are drafted as placeholders, to be overwritten when the league fills them
out: **Ronnie Vance "SHARK"**, **Alan Prosser "STEADY"**, Tommy Fenn "BULLET",
Bernard Ash "DOC", Kev Dolan "MAGPIE", Danny White "CHALKY", Errol Nash
"SPIDER", Pat Cardew "DUCHESS". Only the first two have parameter sets today,
so the playable roster stays a subset of the named one rather than a second
list that can disagree with it.

**The store stays keyed on the nickname**, because that is what a fixture list
shows and what gets shouted across a pub. That invariant broke the moment real
names arrived: `profiles_from_json` keyed on `name`, so a round trip quietly
re-filed SHARK as "Ronnie Vance" and every lookup pointing at SHARK missed.
Assertion 102 caught it.

Schema 2, upgraded on read rather than by a migration pass — there are already
real frames recorded the old way. A schema-1 profile stored its nickname in
`name`; the roster supplies the real name behind it, and anyone off the roster
keeps their nickname as their name, which is what a human who has not filled
the field in should read as. **The schema has to be read off the RAW record:**
`deserialise_profile` stamps the current schema onto its output, so asking the
output means the upgrade never fires. It did exactly that in the first cut.

### And the zero that could not be recovered

`record_frame` takes a `shots` argument and the call site never passed it, so
every frame row recorded **0 shots** — including the two already committed.
Found by reading the first real career rather than by any test, because the
call sits in `run_gui` where no unit test reaches. A mutation test then proved
the fix was unguarded, so assertion 104 checks the call site in source, the
same technique assertion 103 uses.

The name field itself is still to come. There is **no text-entry widget
anywhere in this codebase**, and every letter key is a global shortcut — typing
"Steady" during a game would rack up, cycle the mode and toggle the overlay on
the way past. It belongs in the menu, where no frame is running and nothing is
listening. Until then `$HUSTLER_PLAYER` sets the key.

---

## r49.1 — and now you can actually swap

r49 fixed *which* AI sits in the seat and shipped no way to choose it.
`human_opponent` was assigned once and nothing on earth ever touched it. The
Maker put it plainly: "I dont see anyway to switch opponents."

**Opponent picker on the Game tab, beside Mode, and the O key.** It restarts
the frame exactly as a mode change does, because swapping opponents halfway
through a frame is not a thing that happens — the record would be half one
player's and half another's, and r48 writes that record to a tracked file.
Outside YOU vs AI it still cycles, so the next human game uses the choice, but
it does not tear down an AI-vs-AI frame that has nothing to do with it.

`next_opponent()` walks a roster and wraps, rather than flipping a boolean: the
league needs eight of these, and a two-way toggle would be thrown away the
moment the roster grows.

**One source of truth, again.** Standing up a fresh frame was about to exist
twice — `do_cycle_mode`'s tail and a copy inside the picker. That is precisely
the fault r49 spent a whole revision removing, reappearing three inches to the
left. Extracted to `restart_frame()`, which both now call. Four `nonlocal`
declarations in `do_cycle_mode` became dead in the process and pyflakes said so.

Assertion 103's guard had to change, and the reason is worth recording. It
demanded `human_opponent` be assigned exactly once in `run_gui` — which the
picker legitimately broke. The thing that actually matters is that no *literal*
name is ever assigned, so that is what it checks now: `'human_opponent = "'`
must not appear at all, and `human_opponent = DEFAULT_OPPONENT` exactly once. A
guard that forbids the fix rather than the fault is the wrong guard.

Measured: `Opponent: STEADY (O)` renders 260px against a 348px button at 1.5x
and 160px against 232px at 1.0x, so it fits at every size, and the Game tab's
headroom is unchanged.

---

## r49 — you were never playing SHARK

The Maker asked whether they could swap between the two AI opponents. Checking
the answer turned up something worse: **the opponent was not the one named on
screen.**

The human game set `names = ("YOU", "SHARK")` from one list and took its
players from `default_ais()`, which returns `[SHARK, STEADY]`. The AI is
indexed BY SEAT — `ais[game.current]` — so seat 1 got `ais[1]`, which is
**STEADY**. Every readout, every event line and every win message said SHARK.
The opponent had the opposite temperament: threshold 0.24 against 0.10, greed
0.25 against 0.55, caution 0.70 against 0.35. Where SHARK takes on anything and
plays for position, STEADY demands a better chance and plays safe.

Nothing caught it because both lists were the right length and the wrong AI
still played a perfectly good frame. It is the same shape as the r23 find where
`controllers[...] == "you"` compared a name to a controller value and silently
never matched: two parallel lists, one truth, no check between them.

**r48 turned it from wrong into damaging.** Profiles are recorded under
`game.names[...]` into a file that is tracked, so the first finished frame would
have credited SHARK with a result STEADY earned — and committed it. Found the
day after r48 shipped and before any real frame was played into the store.

Names and players now come from a single `seat_lineup()`, resolved BY MODE NAME
rather than by the literal 1 (the r30 rule), with `ais_for_seats()` looking each
player up by the name shown in that seat. A human seat gets `None` rather than a
spare AI: it can never be reached, and if it somehow were, a crash beats a
second personality quietly taking shots. Assertion 103 checks every seat in
every mode.

The Maker's choice for the default is **SHARK** — the livelier frame, and what
the HUD had been claiming all along. `seat_lineup()` also accepts STEADY, which
is the beginning of the opponent picker the league needs.

One more source of truth removed on the way: the default opponent was about to
exist twice, as a default argument and a literal inside `run_gui`. A mutation
test caught it — changing `run_gui`'s copy left the assertion passing — so it
is now one module constant that the assertion pins in both places.

`--aigame 12 --seed 4200` still returns SHARK 9–3, unchanged: AI-vs-AI was
always seated correctly, and the fix touches only the human game.

---

## r48 — everyone gets a profile

The first piece of league mode with a file behind it. Every player, human and
AI, now carries a tracked profile: frames played, frames won with their Wilson
interval, Grannies given and taken, and trophies. `--profiles` prints the
table. It is keyed per player, so a second person on the same clone builds
their own career rather than joining this one — which is what the Maker meant
by every player getting their own tournament.

It also finishes what r46 could only announce. A Grannie is now **recorded for
ever more**, which was the requirement; r46 had nowhere to put one.

### Written twice, because the first version was worse than what was here

Profiles already existed. r32 built `new_profile`, `profile_record_game`,
`profile_record`, `serialise_profile` and `deserialise_profile`, and pyflakes
caught the collision the moment the duplicate was compiled.

The r32 model is also the better one, for a reason its own docstring gives:
**it stores the frames and derives every aggregate**, where the first r48 cut
kept win/loss counters. That warning is not abstract — r16 found `pot_estimate`
five times over-confident and every conclusion drawn from it had to be thrown
away. Aggregates on disk would have had to be migrated or discarded; functions
over raw rows just get rewritten and re-run. So the counters were deleted and
r48 became a *store* around r32's per-profile model rather than a replacement
for it. The Grannie rides on the frame row, which means the record says which
frame it happened in — something a tally could never answer.

### Two real bugs, both found by the round-trip assertion

`serialise_profile` rebuilds each game row field by field rather than copying
it, so the new `grannie` marker and the `trophies` list were being **silently
dropped** on the way to disk. The serialiser had to be extended rather than
written around.

And `deserialise_profile` returned `None` for a malformed entry — r32's
documented behaviour, "a hand-edited profile should cost you a row, not the
game" — which the new reader then called `.get()` on. A second pass found it
iterating `games` without checking it was a list, so `"games": 7` raised
TypeError. Both would have crashed on exactly the file the Maker asked to have
tracked **so they could edit it by hand**. Assertion 102 exists for that file.

### What a profile deliberately does not carry

No pot rates, no cut-angle bands, no foul counts. All of that lives in the shot
log and is computed on demand by `--stats`, over the whole history rather than
from whenever a profile happened to be created. One place per fact.

And the table is a **record, not a ranking**. Ranking has to weigh opponent
strength — beating the strongest AI is not the same as beating the weakest —
and letting a sorted win column stand in for it would be the r43 mistake told
backwards. The Maker has asked for rankings separately.

---

## r47 — the readout moves off the HUD

The Maker noticed the empty strip above the table and asked whether the HUD's
text could live there instead, leaving the panel free to be controls. Measuring
it made the case better than the idea already was.

The band is what the table fit leaves over, and it is **wide and short** —
about 1734 x 126 on a 2160x1350 screen. The panel strip is narrow and tall.
They suit opposite content, and the difference is not marginal: the same status
fields that wrap to **six lines** in a 370px strip pack into **two** across the
band. A game with ball in hand, the worst case, needs two lines at 2160x1350
and 1024x768 and one at 1920x1080.

So the readout moves up and **the panel strip collapses to nothing**, handing
113-170px back to the panel and lifting every tab with it. Measured at
1920x1080: the Shot tab's headroom goes from **25px to 166px**.

It also cures the overflow found in the Maker's screenshot rather than papering
over it. `BALL IN HAND — drag cue in baulk` renders 416px against a 370px strip
budget — `wrap_fields` packs several fields onto a line but cannot break a
single field that is too long alone, so it ran clean off the panel edge. In a
1734px band it is not remotely close. Better to give it a home that fits than
to shorten the words.

### Decided by the window, never by the text

`status_goes_in_band()` answers from geometry alone. Had it consulted the live
line count, the panel would relayout the moment an event line appeared and
every tab below would jump a shot at a time. The window decides once; the
content then flows into whichever home it was given.

And it must survive there being no band at all: at the F11 windowed size
(1144x548) the table fills the window exactly, the band is 0px, and the panel
strip carries on precisely as it did before r47.

### A feature the reclaimed space paid for

At 1024x768 the panel gained five widgets nobody asked for. That is r30.2's
fit-or-omit rule working: `spin_group_radius()` puts a second strike-point
picker on the Shot tab when the window is tall enough, and at r46 the strip's
113px meant it did not fit at that size. Collapsing the strip bought it.

---

## r46 — the Grannie

A Scottish pub rule, and the first piece of league mode. If one player's
**colour** never goes down while the opponent clears all seven of theirs and
the black, that is a Grannie — a whitewash, and socially the results are
unpleasant.

The Maker's wording settled the design before a line was written: it is judged
on the **colour that never got potted, not on who potted it**. That is what
makes it computable from state the game already keeps — `potted_colours_all()`
plus the colour assignment — with no per-player pot attribution to build.

It also settles the case that decides the rule. If the winner knocks one of the
loser's balls in by accident, the loser's colour *has* been potted, so there is
no Grannie — even though the loser never sent a ball down themselves. A
shooter-based reading would call that a whitewash. Confirmed with the Maker
before building, and assertion 98 pins it. A frame won because the opponent
fouled on the black is not a clearance either, however one-sided it looked.

The payoff is a granny drawn from pygame primitives with big writing, on the
existing black-pot finale and inside its `not smoke` gate, so the `--snap`
baseline never learns about her. **Shift+G previews her** without having to
earn a whitewash first — a real one is rare and awkward to stage, and she
cannot be judged unseen. The preview drives the actual finale path rather than
a separate renderer, so what it shows is what a real Grannie shows; a parallel
preview would be free to drift and would then be worse than useless, because it
would be believed. Plain G still toggles the aim overlay, as it has since r14. On quality the brief was explicit: it does not
matter if she is naff for now, as long as she is there and the whitewash is
recorded for ever more. She will get another pass once she has been seen on a
real screen; the permanent record arrives with profiles at r47.

### A leak found while checking the rule

`clear_objects()` removed balls from the table and the physics space but never
pruned `self.colours`, so the map grew by a full rack every time the table was
cleared — 4 entries, then 19, then 34, against a space correctly holding 16.

It never produced a wrong answer, which is why it survived this long: ball ids
are never reused, and `remaining()` walks `self.balls` rather than the colour
map. But league mode racks hundreds of frames in a single run, and the day
something walks `colours` instead of `balls` it becomes a real bug with a
plausible wrong answer. Fixed, and assertion 99 pins the invariant rather than
the one-off symptom.

---

## r45 — the log learns what a sitting is

Everything the report said was a lifetime aggregate, which cannot tell a bad
Tuesday from a decline. Worse, the before-and-after comparison run at r44 was
only possible because the *commit history* marked where one batch of play
ended and the next began — read from the log alone, nobody could reproduce it.
There was no timestamp and no session marker anywhere in the schema.

So human rows now carry `session` (fixed once when the game starts) and `t`
(the shot's clock, UTC). Schema 7. `--stats` grows a BY SESSION block listing
the last ten sittings.

**A session is one run of the program, not one day.** Two sittings in an
evening are two sessions; leaving the game open overnight is one. That is the
only boundary the game can actually observe, and documenting it honestly beats
a heuristic that guesses at wall-clock gaps and is wrong on the days it counts.

### The guard matters more than the feature

A study run with a fixed seed writes a byte-identical JSONL every time. That is
not a curiosity — it is how r17 proved three separate optimisations
behaviour-preserving, by md5-diffing the study log before and after. **A
timestamp in the shared record builder would have ended that silently:** no
test fails, nothing goes red, the diff simply stops meaning anything, and it
gets discovered months later by whoever next needs to prove a change safe.

Session and clock are therefore written on the human path alone, and assertion
96 exists solely to fail if they ever move — it checks both that
`make_shot_record` stays clean and that exactly one site in the file assigns
them. Verified empirically too: two fixed-seed study runs still produce
identical bytes, and the only field that changed against the pre-r45 baseline
is `schema`, 6 to 7.

### What was deliberately not done

**The 377 existing rows were not backfilled.** The commit boundaries would have
allowed four plausible chunks to be reconstructed, and that is exactly the
problem: a guess written into a tracked data file cannot be told from a
measurement a year later, and this file is the project's only record of how the
game was really played. They sit in one honest "before sessions were recorded"
bucket.

**No trend line and no verdict.** With a handful of sittings an arrow would be
noise with a direction painted on it, which is what r43's intervals were built
to prevent. The sittings are listed; the reading is the player's.

Assertion 39 needed relaxing from `STUDY_SCHEMA == 6` to `>= 6`. The reader was
always keyed on field presence rather than a version number, so only the
assertion pinned the value — and assertion 47 already used `>=`.

---

## r44 — what a foul actually costs you

The log has carried `foul` as a schema field for a long time and it is null on
every human row. Investigating that turned up two different things wearing one
label, and only one of them was a bug.

`event` is correct as it stands. It is passed `game.last_event`, and there is
no `Game` object in solo or practice — no rules engine, so no event. `foul` is
a real gap, but not the missing-argument kind: the human log write sits above
the game block in the frame loop, so at write time `on_rest` has not run and
the foul has not been decided yet. That is written up as KNOWN_ISSUES #5 rather
than patched, because it only bites in game modes and the log holds no
game-mode rows at all.

None of which matters for solo, because **a solo foul was already derivable**.
`solo_apply_shot` defines one as the cue ball potted or nothing hit at all, and
both have been in every row since r15. So `--stats` now reports them, over the
whole history rather than from the day this shipped:

```
FOULS  (cue ball potted, or nothing hit at all)
  all shots    10/244 =   4.1%  [ 2.2- 7.4]
    7 scratch, 3 no contact
  solo          7/140 =   5.0%  [ 2.4-10.0]
    cost 70s on the clock at 10s a foul
```

The seconds are the reason this was worth building. A 5% foul rate is easy to
shrug at; seventy seconds off a clearance is not, and it was a cost with no way
to see it. Solo is counted separately from practice because solo is the only
mode where a foul is actually charged — practice has no clock, and pooling them
would put a price on shots that were never billed.

**One definition, two callers.** The clock charges a foul and the report counts
one, and a second copy of that test is exactly how a rule and its report drift
apart: add a third foul condition to the run state and the report would go on
counting two, with nothing failing anywhere. `shot_is_foul()` is now the single
predicate and assertion 94 pins that both sides route through it. Same
treatment `TIP_FRAC` got at r42.

r43's `scratch_summary()` was removed rather than left sitting unused — the
fouls block reports the scratch count as one of the two causes, and the two
sections would have been near-duplicates disagreeing on scope.

---

## r43 — the pot rate stops flattering you

`--stats` has recovered the target of every shot since r36 and reported pot
rates by cut angle, distance, power and spin. Two things were wrong with it,
and one of them was quietly changing the answer.

**The denominator dropped the worst shots.** `shot_target` resolves the pocket
from the drop when the ball goes in, and from the departure line when it does
not — and the line branch refuses when it points further than 50mm from every
pocket. Refusing is correct, and r36 built it deliberately: a safety is not a
failed pot. But the refusal is triggered by *missing badly*, and the refused
rows were then dropped from the rate altogether. On the 244-row log that was 27
rows, 22 of which potted nothing at all. The overall figure moves from 56.2% to
50.9% when they are counted — and it will not move evenly, because the
exclusion bites hardest in exactly the bands where the player misses worst.

There is no correct denominator to pick here. From the log alone a wild miss
and a deliberate safety are genuinely indistinguishable. So both are now
reported, **confirmed** and **inclusive**, and the gap between them is the
honest measure of what is not known.

**Nothing carried a confidence interval.** `wilson_interval()` has been in the
file since r15 and the player-facing report never used it, so `6/35 = 17.1%`
and `3/4 = 75.0%` printed with identical authority on the same page. Every band
now prints its 95% Wilson bounds — including the comfortable ones, because
showing the interval only on small samples turns it into a warning label and
teaches the reader to skip precisely the rows that need care.

That change does most of the work on a third problem. The spin table does not
measure what spin does to a shot; it measures which shots the player reaches
for each spin on. Centre ball gets the awkward ones. Separating the two needs
the rate stratified by cut angle *and* distance within each spin family, which
at a couple of hundred rows leaves cells of five and six — the r18 confound in
a new costume. It is labelled as confounded rather than corrected, and the
intervals now make `left 3/4 = 75.0% [30.1-95.4]` disqualify itself on sight.

A scratch section was added and deliberately says almost nothing: seven events
in 244 shots supports "you rarely scratch" and no statement whatever about why.

One more thing worth recording, because it is a trap for anyone reading the
provenance line: the drop pocket only exists when the ball dropped, so
`observed` rows are 100% pots by construction and `inferred` rows are 0% by
construction. The label *is* the outcome. Those counts are a census of how the
target was found, never a comparison, and the report now says so.

---

## r42 — the constants get a reference, and the strip gets its air back

Four numbers had been sitting in the persistent status strip since r11:
cushion elasticity, roll deceleration, ball size, cue size. They were honest
and they were useless. `cushion e 0.77` tells a reader nothing, because 0.77
only means something next to the range it came from.

They now live on the **Table tab**, directly beneath the sliders that change
them, each drawn against what it is actually measured against. The two kinds of
reference are deliberately different, because the underlying numbers are:

* **Ball and cue are WEPF Annexe A** — legal equipment, one discrete value.
  They get a hard tick, and toggling the casual 2" cue ball in reads *off spec*
  immediately.
* **Cushion and roll are measured literature ranges** — a tick there would
  invent a precision nobody has, so they get a band. Roll sits at the top of
  its band, which is the correct picture: 0.015 is the slow end of the measured
  range for napped UK cloth.

One trap is worth recording because it would have shipped looking perfectly
reasonable. The measured 0.6–0.9 cushion range is for the **pair** value, while
`CFG` carries the rail component 0.77. Plotting 0.77 against a pair band
compares two different quantities. The row plots the pair value (0.98 × 0.77 ≈
0.75) and says so, and assertion 90 pins the arithmetic so a later
"simplification" back to the raw constant fails here rather than in a
screenshot nobody re-measures.

The cue ball and object ball are also drawn side by side at true relative
scale. 47.6mm against 50.8mm is a six per cent difference that is impossible to
feel from two numbers and obvious once you see it, and the tip circle uses the
same `TIP_FRAC` the strike-point cursor uses — the literal is now defined once.

### Why they left the strip

The Maker reported the strip text looking squashed at 1.5x. Measuring it turned
up two faults rather than one, and neither was the leading alone.

The strip was **already clipping**. A game with ball in hand wanted nine lines
against a budget of seven, so the last event and the ball-in-hand prompt were
both silently vanishing — assertion 85's failure mode, in the game path this
time. And the call indicator's clamp was `STATUS_STRIP_H - 14`, an unscaled
literal inside a strip that scales: it overlapped the last line's ink by 4px at
1.5x and 12px at 1.25x and 1.0x, and spilled past the strip's own rule onto the
tabstrip at every scale. The same defect r41 found in the button rects.

Moving the four constants out takes the worst case from nine lines to six, so
nothing clips any more. The leading is now **computed rather than chosen**:
`strip_leading()` shares out the spare height when there are few lines — a solo
run gets 9px of air at 1.5x instead of 1px — and tightens back to the old
one-pixel floor when a full game fills the strip, because a wider fixed gap
would have deleted a line rather than spaced one out. The call row is paid for
up front instead of being clamped on top of the text.

Measured after the change: no clipping in any case at any scale, the call row
inside the strip everywhere, and a clean gap below the last line in every case
but one — a full game at 1.25x still touches it by 2px, down from 12.

---

## r41 — the HUD grows with the screen

The panel was drawn in fixed pixels — 260 wide, 14pt type, 22px buttons — while
the table scaled through `RSF`. On the screen it was designed for that looked
right. On a 2160x1350 high-DPI panel the table grows to fill the space and the
HUD does not, so the type ends up physically tiny beside it.

Worth recording that nothing was broken. Measured off the Maker's screenshot,
a nudge button really was 115 pixels wide against the 116 the code asks for.
The panel was doing exactly what it was told; the screen had moved on.

`panel_scale()` now derives a factor from the window height and everything in
the panel is expressed through it: width, font, button heights, row pitches,
the dial and picker radii, and the status strip's budget. The layout literals
are deliberately left recognisable and passed through a `U()` helper rather
than rewritten, so 34 is still visibly the r10 separation gap and the comments
explaining them stay true.

**The cap of 1.5 is a trade, not a limit, and it is the Maker's to make.** On
this layout the scene is width-limited, so every pixel the panel gains comes
straight out of the playing area: at 2160 wide, doubling the panel to 520 would
shrink the table from 1852x926 to 1592x796 — fourteen per cent of the baize
gone. 1.5 costs seven per cent and roughly doubles the apparent type size. The
self-test pins that number so a future reader raising it has to notice they are
spending table to buy panel.

**The probe gained the check that would have caught this class of bug, and it
earned its keep immediately.** Nothing existing verifies that a label actually
FITS inside its own button — overlap and extent checks both pass straight over
text spilling out of a widget. The new check found six overflows on its first
run, all at 1.5 and none at any smaller scale: four button heights had been
missed by the transform because their rectangles start with an expression
rather than a bare `px`, so the font grew and the buttons did not.

The strip keeps its seven-line budget at every scale, checked rather than
assumed — a fixed 113px height would have clipped at 1.5 exactly as it clipped
at r37.1, the same bug arrived at from the other direction.

Self-test 89, mutation-tested six ways. One mutant deliberately survived and
was then made impossible: it deleted a `win_h <= 0` guard and the test still
passed, which was the correct result — the `max(1.0, ...)` below already
handled zero and negatives, so the guard could never change an answer. It was
removed rather than tested. Dead code that looks defensive is worse than none.

---

## r40 — the aim dial

The last of the three shot controls that could not reach the precision it
displayed. The dial was 38px, which is 238 pixels of circumference for a full
turn: **1.51 degrees per pixel of drag**, against a readout showing tenths and
nudge buttons offering hundredths. Power had this fixed at r29 and spin at r30;
aim had been outstanding since.

It is now sized like the strike-point picker — radius 100 where there is room,
which is 0.573 degrees per pixel, nearly three times finer — and it gets an
**Aim tab** of its own alongside a Shot-tab copy, the arrangement the spin
picker settled on and the Maker judged to have earned its place. One builder
makes both, so they cannot drift, and both are views onto the same `aim_angle`,
so they cannot disagree.

Around the rim: **plain degree ticks**, every 10 degrees with every third
labelled. A compass rose and a clock face were both considered and both
rejected — this table measures angles from the x-axis with y increasing down
the screen, so a compass would be reversed in one direction and a clock would
have to pick a handedness. Degrees say exactly what the readout says.

The angle now snaps to 0.01, the same grid the buttons use, so the dial and the
buttons finally live in one value space. **Snap then wrap**, not the reverse:
359.999 snaps up to 360.00, which is not a legal angle, and wrapping afterwards
returns it to 0.0. That is r30's snap-then-clamp lesson wearing new clothes.
The grid is finer than a drag can reach even at radius 100, which is the point —
it exists so the two controls agree, not to make dragging more precise.

The handle scales with the dial and is drawn as an outline plus a centre dot,
so it cannot hide the tick underneath it — the r30.1 lesson about a cursor
obscuring its own guide.

**A note on what the extra size costs.** The Shot tab is the deepest in the
panel, and the dial only grows there when it honestly fits; below a floor it
falls back rather than degrading into something unusable. My first attempt at
that arithmetic ran the tab 19 pixels off the bottom of a 548-tall window,
because I costed the dial group and forgot the separation gap and the Shoot
button below it. The reserve is now counted line by line in the source with
headroom deliberately left over, for the same reason r37.1 gave: a layout that
merely fits here meets a taller font fallback somewhere else.

One consequence worth knowing: at 1024x768 the Shot tab now carries the big aim
dial and **omits** its copy of the spin picker. The Spin tab still has the
full-size picker, so that costs a tab click rather than a capability — but it is
a trade, and on a 1080-tall desktop both fit together.

Self-test 88, mutation-tested six ways.

---

## r39 — marking the break

The break is the one shot whose job is position rather than potting, and
nothing in the log told it apart from any other shot. Asked for a break
analysis, the best that could be done was to infer it — find the rows played at
a full rack and assume. That produced nine breaks out of 179 shots, and the
assumption is not safe: in sandbox the balls are set out by hand and can be
re-racked mid-session, so a full rack is not proof of a break.

So the break is now recorded at the table. A flag is set on any fresh rack or
mode change and spent by firing, and the row carries `break_shot`. No inference,
no reconstruction.

`break_shot(row)` reads it back and returns **True, False, or None** — and the
third value is the point. Rows written before this carry no flag, and there is
no honest way to recover one, so they report None and a reader must exclude them
from a break sample rather than counting them as non-breaks. Folding 179 old
rows into the "not a break" pile would produce a table that looked authoritative
and was partly invented, which is the contamination pattern r21 spent five dead
hypotheses undoing and the same reason r36's target recovery refuses rather than
guessing a best-aligned pocket.

It keys on the presence of the field rather than on the schema number, which
self-test 87 forced: the first version tested `schema < 6` and failed
immediately, because the schema is stamped by the writer and a record that has
not been written yet carries no version. Presence is the better key regardless —
it asks the row what it contains instead of trusting a version number to imply
it.

`STUDY_SCHEMA` is 6. Nothing else changes; the file plays exactly as r38 did,
and the break statistics arrive once there are real breaks to report.

Self-test 87, mutation-tested six ways.

---

## r38 — the shot log moves into the repo

The log was written to the home directory and `.gitignore` treated every
`.jsonl` as runtime state to be thrown away. That was the wrong call. The log is
not scratch: it is the record of every shot ever played, it is the thing the
whole stats arc was built to produce, and it grows into the most valuable thing
the project owns. Nothing that takes months to accumulate should live somewhere
a fresh clone cannot see.

It now sits beside `hustler.py` — in practice, inside the repo — and it is
tracked, so it can be committed as it grows. `.gitignore` keeps its blanket
`*.jsonl` rule and carries one deliberate exception for this file.

The path is resolved from the script's own directory rather than from a fixed
location, so a second clone logs to itself instead of quietly appending to the
first one's history. `$HUSTLER_SHOT_LOG` overrides it outright, which is what
to reach for when running an experiment that should not land in the tracked
file. The writer and `--stats` call the same resolver, because a log written to
one path and summarised from another fails silently in the worst possible
direction: the summary reports an empty file while the real rows pile up
somewhere else, and nothing anywhere says so.

**Expect `git status` to show the log as modified after playing.** That is real
data, not a phantom — the distinction r30.3 went to some trouble to restore.

Self-test 86, mutation-tested six ways. Two of those mutants survived the first
attempt, and both taught the same thing: asserting the resolver in isolation
proves nothing about whether either END still calls it. One pointed `--stats`
back at the home directory and one pointed the writer back, and the test passed
happily through both. Both ends are now checked by code-object introspection —
the self-test 72 technique — and the writer needs the recursive walk, because a
flat name check on `run_gui` misses a nested function entirely.

---

## r37.1 — the readout that was being cut off

Two defects in r37's solo readout, both found by one question: where exactly is
the clock on screen?

The persistent status strip is a fixed 113px and its draw loop stops the moment
another line will not fit. **Silent clipping is the dangerous kind** — an
overrun does not look like a bug, it looks like the line was never written. The
finished-run readout measured eight lines against a budget of seven, so
`3 shots, 1 foul — T = rack again` disappeared at precisely the moment it was
worth reading. The widget-overlap probe could never have caught this: it checks
the tabs, and the strip sits deliberately outside the tab system.

The readout is now built by a pure helper that caps itself at two lines. The
ball count goes during a run, because `7 colours + black` already says what is
left and says it better. The foul tally rides on the clock line rather than
taking its own, which is also truer — a foul in this mode *is* time, and the
penalty is already inside the figure shown.

The second defect was worse than cosmetic. **A finished run still accepted
shots.** `solo_apply_shot` is guarded by `not over`, so those strikes were not
counted, not clocked and not part of the run: ghost shots after the verdict.
That is the r23 turn-handover bug in miniature — the state said the visit was
finished and the input path had not been told. A finished run is no longer your
turn, which disables the Shoot button and takes the aim overlay down with it.
T racks a fresh run, as the readout says.

Fixing that is also where the headroom came from: every state now sits at six
lines against a budget of seven. The margin matters because the panel font is
resolved by `SysFont` with fallbacks, so line height is not identical on every
machine, and a layout that merely fits on one is a font substitution away from
clipping on another.

Self-test 85 caps the readout across every reachable state, mutation-tested six
ways. One of those mutants survived the first attempt — deleting the clock-off
branch entirely still returned one line, so a budget-only assertion was blind to
a readout that showed a clock the player had switched off. The check now asserts
that switching the clock off actually drops the time.

---

## r37 — solo mode

The rules for a timed solo clearance were written at r34 and then sat there:
pure, self-tested, and called by nothing. This connects them. `SOLO` is a fourth
mode — deliberately a mode rather than a switch inside SANDBOX, because free
practice is what actually gets played here and a stopwatch must not displace it.

Rack up, study the table as long as you like, and the clock starts on your first
strike. Pot the colours in any order, black last. A foul — potting the white, or
failing to hit anything — costs ten seconds rather than a turn, because with no
opponent to hand the table to, time is the only currency the game has. Black down
before the colours are cleared and the run is over. The clock can be switched off
at any point, which drops the timing and keeps the rules, and a run can be reset
without re-racking.

**The interesting part was not the feature.** `MODES` had three entries and
eighteen places in the code tested `mode == 0`. That single literal was answering
three different questions which had only ever agreed because SANDBOX was the one
Game-less mode:

- *is the human the one shooting?* — SANDBOX yes, SOLO yes
- *may the player edit the table?* — SANDBOX yes, SOLO only before the run starts
- *is this practice, for the shot log?* — SANDBOX yes, SOLO neither

SOLO answers them differently, so every one of those eighteen sites was a bug
waiting for a fourth mode to exist. It is precisely the shape of `custom_active()`
testing `panel_tab == 3` for years, at nine times the scale — and that one was
caught by luck rather than by design.

So none of them test a mode index any more. `mode_intents()` answers the three
questions from a mode's NAME, once, out where it can be asserted; the closures
inside `run_gui` delegate to it. Self-test 84 checks the whole table across all
four modes and both run states, which means a fifth mode cannot be added without
failing the build until somebody has classified it deliberately.

The table locks on the first strike rather than when the shot comes to rest. That
sounds like a detail and is not: run state advances at rest, so gating on it would
have left the table editable for the entire flight of the opening shot.

The clock's readout sits in the persistent status strip, because a clock you have
to change tabs to read is not a clock. Its two controls sit on the Game tab, because
a switch pressed twice a session does not need that real estate. A finished run
freezes and shows how it ended, its final time, shots and fouls, rather than
auto-racking away the number you wanted to see.

`solo` joins `practice` and `tournament` as a shot-log tag, and `--stats` reports it
on its own line. A timed clearance you racked yourself is a third population: no
opponent, no fouls that hand over the table, and the balls set out by the player.

Self-test 84, mutation-tested five ways. The panel was probed at three window sizes
for pairwise widget overlap — zero everywhere, Game tab now five widgets deep.

---

## r36 — reading the shots you never called

Nominating a shot is optional, and on the first real session with r35 it went
unused — 55 of 67 rows carried no call, including every shot of the best game in
the log. Those rows looked thin. `--stats` could say nothing about them, because
every geometry field it wants hangs off the nominated ball.

They were not thin. Since r35 each row carries the whole pre-shot layout, the
cue ball's contact trail and the pocket that took each potted ball. Between
them that is enough to reconstruct what the shot actually was — which ball was
played, where it stood, and where it was sent. **Nothing new is written to
disk.** This release adds readers, not fields, which is why it works
retroactively: shots played weeks ago become analysable without having been
logged any differently.

Four ways a target gets resolved, and the difference between them is not
cosmetic. **Called** — the player nominated it; they said so. **Observed** —
the ball they struck went down and r35 recorded which pocket took it; also a
fact, and free. **Inferred** — neither, so the line the object ball departed on
decides. **None** — that line points nowhere near a pocket, so it was not a pot
attempt and no target is recorded. `--stats` prints the breakdown above the
percentages, because two of those are facts and two are readings, and a reader
is entitled to know the mix.

**The refusal is the design.** The obvious way to fill in a missing target is
to take whichever pocket is best aligned, which is what `pot_assessment` does —
and it always returns something. Every safety, cannon and deliberate roll-up
would come back as an attempted pot and be scored as a miss. That is the
contamination r21 spent five dead hypotheses undoing, wearing new clothes: not
a broken pot model, a wrongly-chosen population. So the line must pass within
50mm of a pocket, and a pocket sitting behind the object ball is rejected
however neatly the infinite line through it fits.

The threshold was measured rather than picked. Across 29 logged shots where the
ball dropped and the answer is therefore known, the departure line passed within
28mm at worst and 14mm typically; the two logged shots that were not pot
attempts passed 100mm and 200mm away. The threshold sits in the gap. On that
same set of 29 the inference agreed with the recorded pocket every time — which
is a reason to trust it, not a reason to prefer it, so an observed pocket still
outranks an inferred one always.

Effect on the session that prompted it: 59 of 67 shots now carry a target, up
from 12.

`shot_accuracy` is unchanged and still counts called shots only. Tightening it
would silently re-base a figure already read off a real session. The derived
numbers are reported separately, under their own heading.

Self-test 83, mutation-tested six ways. One of those mutants initially *crashed*
the assertion rather than failing it, which is not a test result — the check was
rebuilt so every mutant now produces a clean failure.

---

## r35 — log the leave

Every row in the shot log described the table as it stood at the moment of
striking, and nothing described the other end. That was fine for the questions
the log was first built to answer — how hard was this shot, did it drop — and
it is exactly why the natural follow-up had no answer anywhere in the system.
"Why did the white go down, and how do I avoid it" needs to know where the cue
ball finished, what it touched on the way, and which pocket took the ball. None
of the three was recorded.

All three now are. `cue_rest` is where the white came to rest, or `null` if it
was potted — which is unambiguous rather than lazy, because `auto_respot` is
off on both logged paths, so nothing puts the ball back before the row is
written. `leave_layout` is the whole table at rest. `cue_trail` is what the cue
ball touched, in order. `drop_pockets` says which pocket took each ball potted
on that shot.

**The trail's de-duplication is the part that matters.** pymunk calls back once
per substep for as long as two bodies stay in contact, and this engine runs
eight substeps a frame. One ordinary shot, measured before any of this was
written, produced fifteen cue-cushion callbacks that a player would describe as
four rebounds — with a single contact firing eleven times on its own, because a
ball sitting in the jaws touches several cushion primitives at once. Appended
raw, the trail would have looked richly detailed and been mostly one cushion
repeated, and the first thing anyone asked of it — how many cushions did the
white find before it dropped — would have come back wrong by a factor of four
while reading entirely plausibly. `trail_append` folds a contact of the same
kind against the same thing arriving within two substeps into the entry already
there, keeping a callback count and the substep span. The order survives,
because the order is the whole point: going in off the object ball, and coming
back off two cushions, are the same set of contacts and completely different
shots.

The drop pocket is read off the sensor shape that actually fired, not inferred
from where the ball was last seen. A nearest-pocket lookup would in fact have
been unambiguous here — the pockets sit 924mm apart against a 35mm capture
radius — but it would still have been a guess standing next to an exact answer,
and this project has already paid once for deriving a plausible-looking
geometric result instead of the real one (see `pocket_axis`, r32.1). Each pocket
sensor now carries its own index, and `_pending_pot_ids` became a map from ball
to pocket rather than a bare set.

`potted_log` was deliberately left exactly as it was. It is read by the rules
engine, its shape is load-bearing, and r22 already split `potted_all` off it
rather than teach one variable to mean two things. The destinations live in a
separate shot-scoped `drop_log`, which nothing but the logger reads.

Nothing visible changed. There is no new `--stats` section and no widget; the
file plays exactly as r34.1 did. `shot_accuracy` still scores a called shot on
whether the nominated BALL went down, deliberately — tightening it to require
the nominated POCKET would silently re-base a figure already read off a real
session, and would score rows written under the old schema against rows written
under the new one on the same scale. That is precisely the pooling the
provenance fields exist to prevent. The reading comes later, designed against
real rows.

Row cost, measured rather than estimated: a mean row went from 1,095 bytes to
1,896. The brief predicted about forty per cent because it costed the second
layout and forgot the trail; the honest figure is seventy-three.

`STUDY_SCHEMA` is 5. Self-test 82, mutation-tested five ways — de-duplication
removed, ordering destroyed, the fold window widened, the cap removed, and the
drop pocket pinned to a constant. All five caught.

---

## r34 — the solo clearance rules

The rules half of a timed solo game, built and tested before anything draws
it. Pot every colour in any order, the black last, against the clock.

Any-order won over a reds-then-yellows sequence, and the Maker got there by
asking the right question: how do you foul a player who pots two different
colours at once? Notice what the answer does — with no sequence to break, a
mixed pot cannot break one. The rule that caused the problem was the rule
worth dropping. It is also the better rule for a time trial: with a clock
running, a forced colour order mostly punishes how the rack happened to break,
while any-order rewards reading the table and choosing a run.

The black is the only ordering rule left and it is absolute. Down before the
colours are cleared and the run ends there.

Fouls cost TIME rather than a turn — ten seconds — because a solo game has no
opponent to hand the table to. The clock is the only currency it has. A
scratch and an air shot both foul; a scratch still gives ball in hand in
baulk, which the r13 placement machinery already handles.

One rule went in wrong and the assertion caught it on its first run. Potting
the last colour and the black on the same shot read as a clean clearance,
because the test compared the colours remaining AFTER the shot — which is zero
either way. A lucky double-pot would have handed the player a clearance they
had not earned, and it would have looked entirely reasonable in the log. The
black is now judged against what was potted alongside it as well as what is
left.

**r34.1 shows the spin back to you, and says whether the call came off.** The
spin used on every shot has been recorded since r33 and never displayed, which
made the most interesting thing in the log invisible: the full-follow and
full-side corner strikes that hold or swing a ball into a pocket the straight
line does not serve. `--stats` now bands by spin family.

The bands are families rather than exact values on purpose. The picker snaps
to a 0.01 grid but rim values are clamped to the unit circle instead, so a
45-degree maximum is stored as 0.7071 while the readout shows 0.71 — keying on
exact numbers would scatter the corner shots across a dozen near-identical
keys and report each as a sample of one.

The indicator now says whether the nominated ball actually went down rather
than merely that a row was written. "Did I get that one right" is the question
being asked at the table, and it is answerable the moment the balls stop.

Rules only so far: nothing calls this yet and no mode draws it. The clock, the
readout and the fourth mode come next.

---

## r33 — calling your shot

The first visible half of the stats work. A scale model of the table now sits
in the Spin tab: click a ball, click a pocket, take the shot. That nomination
is what makes a result meaningful — without it, "did it go in" has no answer,
because nothing knows where it was supposed to go.

The model is not a drawing of a table. It is the actual `nose_loop_m()`
cushion polyline and the actual `capture_points()`, scaled down, so the jaws
sit exactly where they sit on the full-size table. A mini table with invented
pockets would misplace the one feature that decides whether a pot survives.
Both axes take the same scale, for the same reason: stretched to fill its box,
a click would land on different geometry from the one under the cursor.

Nomination is HUD-only, like every other shot parameter. The widget converts
its own pixels, never a table click, so R6.6 is untouched.

A click that lands nowhere near a ball or a pocket nominates nothing rather
than snapping to whatever happened to be closest. A call the player never made
is worse than no call at all — an unnominated shot logs honestly as
`intent: "none"` and is excluded from accuracy, while a wrong nomination is
data that looks right.

Shooting without calling is allowed and always will be. The shot fires
normally and records with no intent; it still contributes its geometry and its
outcome. Calling can be switched off entirely.

**One thing this exposed:** sandbox has no shot-completed event at all.
`pending` is only ever set when a `Game` exists, so in mode 0 — which is
precisely where the practice frames happen — nothing ever resolved a shot. The
logging carries its own flag rather than borrowing one that was never going to
fire.

Rows land in `~/hustler_shots.jsonl`, appended, one per shot, and the write is
best-effort by design: a full or unwritable disk costs a row and never a shot.

**r33.1 adds the indicator that should have been there from the start.** A
session of real play found the gap immediately: there was no way to tell
whether a shot had been nominated, or whether anything had been recorded. A
control whose effect is invisible is a control you cannot trust — and a half
nomination, a ball chosen without a pocket, silently recorded as un-nominated:
an honest row, but not the one the player believed they were making. A small
lamp now sits in the persistent status strip, readable from every tab
including the one where the shot is actually taken, and reads dark for off,
red for armed, amber for a ball without a pocket, green for ready, and flashes
when a row lands.

**r33.2 adds `--stats`.** The log existed and was filling up correctly, but
there was no way to read it without writing a script, which is a poor place to
leave a feature whose whole point is telling you how you are playing. The
summary reports called-shot accuracy banded by approach angle and by distance,
and finishes with the spread of your aim error — which is the same quantity as
the AI's `aim_jitter`, measured rather than assumed, and eventually the number
a human profile gets cloned from. Practice and tournament are reported on
separate lines rather than pooled, and a log with no called shots says so
plainly instead of printing a confident 0.0% over nothing.

**r33.3 fixes a units bug in that summary**, found the first time it ran on
real shots. `aim_jitter` is measured in radians — `PoolAI` says so in its own
constructor — and the summary printed the human's spread in degrees directly
beside it. The comparison looked meaningful and was wrong by a factor of 57:
a player roughly four times more accurate than the study AI read as twelve
times worse. Both numbers now print in radians, with the ratio spelled out.

Validation: 79 assertions, 0 containment escapes over 30 batch strikes, 90
smoke frames, `--snap` byte-identical, `--aigame 12 --seed 4200` unchanged at
SHARK 9–3. Probed at three window sizes with zero widget overlaps; the caller
is omitted outright at the F11 windowed size rather than drawn off the panel.

---

## r32 — the shot ledger

Groundwork, and it changes nothing you can see. Nothing in the game calls any
of it yet: the file plays exactly as r31.1 did. What it adds is the shape the
data will be recorded in, decided and tested before a single row exists —
because a schema is the one thing that cannot be fixed afterwards. Shots
logged under an ambiguous model can never be disambiguated later; you cannot
recover, a year on, whether a given miss was a miss or a well-judged safety.

**Every row now carries provenance.** Four fields decide which records may
legitimately be added together: `source` (human or ai), `mode` (practice or
tournament), `intent` (called or none), and `p_model` — which of the two
difficulty functions produced the predicted pot chance. Each exists because
pooling across it would be a quiet lie. A human aims by typing a number into
the HUD and has no applied jitter; the AI does. In practice the player sets
the balls up themselves, so a practice pot rate measures which shots they
chose to rehearse rather than how well they play. An un-nominated shot has no
declared goal, and scoring a safety as a failed pot is the exact mistake that
cost r19 through r21 a five-hypothesis rabbit hole. And the two difficulty
models have drifted apart — different thinness term, different distance decay
— so their numbers are not on one scale.

**Aim error is now measurable, which is the interesting part.** The AI's
`aim_jitter` is noise we add, so we know it. A human's execution is exact —
the cue goes precisely where the angle says — which means all of a human's
error lives in judgement, and it is one specific number: the gap between the
angle they chose and the angle that would have potted the ball they nominated.
The spread of that over many shots *is* their aim_jitter, on the same axis r18
established for the AI personalities. It is only meaningful on a called shot,
so it returns nothing without a nomination rather than inventing a plausible
zero.

**Profiles store identity and completed frames. Nothing else.** Every
statistic — pot rate, win rate, aim spread, whatever nobody has thought of yet
— is derived from the log on read. That is what makes it safe to create
profiles before any real data exists. Store computed aggregates instead and
the day a statistic turns out to have been wrong, every profile on disk is
wrong with it. r16 found `pot_estimate` had been five times over-confident and
every conclusion drawn from it was discarded; functions over a raw log get
rewritten and re-run, stored numbers get migrated or lost.

An abandoned or crashed frame writes nothing at all. Telling a rage quit from
a power cut is not reliably possible, and a forfeit inferred from an orphaned
marker would punish the wrong player often enough to matter — so only whole,
clean games count.

**r32.1 adds the half that was missing.** The first cut recorded the cut angle
and the distance to the pocket, and stopped there — so a ball half a metre out
tight against the cushion and one half a metre out in open baize produced
identical rows. On a table with these knuckles they are not remotely the same
shot. Rather than bolt on another derived number, the rows now carry the raw
positions: the cue ball, the object ball, and the whole table layout in metres
at the moment of striking. Every angle is derived from those on read, including
the one that turns out to matter — how far round from the pocket's own mouth
axis the ball was sitting. Over four logged AI frames the pot rate runs 59%
within ten degrees of the mouth and 5% beyond thirty. Distance alone could
never have shown that.

Two things surfaced only by running the pipeline on real games rather than
fixtures. The accuracy check compared a nominated BALL against a list of
potted COLOURS, so it could never match anything and quietly scored every
shot a miss. And the AI, which does nominate a ball and a pocket before every
pot, was throwing the ball id away — its own shots were unscoreable by the
very statistic being built for them. Both are fixed; AI pot shots are now
recorded as the called shots they always were.

One known limitation, recorded rather than hidden: a shot scores as made when
the nominated ball goes down, not when it goes down the nominated pocket. The
sim does not currently record which pocket swallowed which ball.

Four assertions, mutation-tested ten ways. One of those mutants survived the
first attempt: the test that guards against counting un-nominated shots as
missed pots had no un-nominated shot in its fixture, so the guard could be
deleted with the assertion still passing. The fixture has one now.

Validation: 76 assertions, 0 containment escapes over 30 batch strikes, 90
smoke frames, `--snap` byte-identical, `--aigame 12 --seed 4200` unchanged at
SHARK 9–3.

---

## r31 — a hardening pass, and a reset that never reset

No new features. Before anything else went in, the repository was audited end
to end for the class of thing that does not announce itself: code that runs
without error and does nothing, checks that cannot fail, and guards that have
quietly been reporting green over a real problem.

**The bug.** `do_rack()` carried `finale = None`, but omitted `finale` from
its `nonlocal` list. In Python that makes the name local for the whole
function, so the reset wrote to a throwaway and the enclosing value was never
touched. Racking during the slow-mo black finale left the win animation
playing over the fresh rack until it aged out on its own. Cosmetic, and it
healed itself in about a second — but it is the second time this exact shape
has landed. At r23 the HUD's spin values were re-sent every shot for the same
reason. Nothing in the validation chain can see it, because there is nothing
wrong with the code except which variable it wrote to.

So the fix is not the one-line `nonlocal`. It is selftest 72, which reads the
compiled code objects and asserts that no nested function inside `run_gui`
assigns a piece of the enclosing state without declaring it — a leaked name
lands in the nested function's `co_varnames` when it belongs in
`co_freevars`. That guards the class rather than the instance. The assertion
carries a deliberately planted leak alongside the real check, so a clean
result cannot be a check that simply never fired; mutation testing showed the
first version of that canary was one level deep and still passed when the
detector's recursion was removed, so it is nested two deep now.

**Two assertions were being computed and thrown away.** The impact-sound test
built `ok31i_polymer` and `ok31i_lp` and never passed them to `check()`. The
comment above them said, in as many words, that these properties get asserted
rather than merely described — and then they were not. Both passed once wired
in, so nothing was hiding, but the properties that separate a polymer knock
from a glass plink had been unguarded since r8.2: noise-dominated, partials
below 1500 Hz, inharmonic, dead inside 20 ms. The sound could have been
retuned back to a plink with the whole chain green. A variable built for an
assertion and never consumed is a test that cannot fail.

**CI counted nothing.** It ran `--selftest` and trusted the exit code. Exit
codes are correct, so a genuine failure did fail the build — but a stale or
truncated file whose remaining assertions all pass exits 0 and turns the
workflow green, which is precisely how an R7-era file once survived every
check. The workflow now asserts the assertion count and the cushion-path
primitive count, both as named environment variables that must be bumped
deliberately. The upkeep is the guard. Checked against an older build: it
reports 69 assertions against an expected 72, and is caught.

**And the lint job had been green over a red check.** `isort` was failing and
`continue-on-error` was hiding it. It is clean now and blocking — and in
r31.1 the last soft failure went with it. No step in the workflow carries
`continue-on-error` any more.

black was removed rather than fixed. Its diff on this repository runs to 1353
removals against 2469 additions, roughly a third of `hustler.py`, and 251 of
those lines are aligned inline comments — including the configuration table
where the alignment is doing real work explaining the physics constants.
Enforcing it would bury every future change under a reformat, which is the
same problem the line-ending normalisation had just removed. pyflakes took the
slot instead, and earned it: pyflakes is what found the `finale` bug in the
first place, by reporting a local variable assigned and never used. A cosmetic
check that can never pass was swapped for a semantic one that already caught
something. The two measurement scripts, tracked since r26 and never checked by
anything, are now compiled and linted with the rest.

Also: three dead locals and three placeholder-free f-strings removed, the dev
extras in `setup.py` corrected to the tools actually used, an unreferenced
104 KB image dropped, and the re-entry prompt in the handoff strengthened to
quote the file md5s and the assertion count — it had been weaker than the one
actually in use, and would not have caught the stale copy that the real one
did.

Validation: 72 assertions, 0 containment escapes over 30 batch strikes, 90
smoke frames, `--snap` byte-identical, `--aigame 12 --seed 4200` unchanged at
SHARK 9–3.

---

## r30 — a contact point you can name

Aim got fine adjustment at r10 and power at r29. Spin was the last of the three
shot parameters still set by eye, and it had the same defect to within a
rounding error: the pad is 36 px in radius, so one pixel of movement is 0.028
of spin against a readout formatted to two decimals. It displayed hundredths it
could not reach. Worse, `nudge_spin()` did not snap where `nudge_power()` did,
so a spin could be placed finely by dragging and then walked 0.3572, 0.3672,
0.3772 — tracking correctly in the readout while never once being round. A
value you cannot write down is a value you cannot play again.

Three decisions shaped the fix, and the first two were reversals.

**The picker lives on its own tab, not over the table.** Drawing it on the
baize would have given it 200–300 px and cost no panel space, which is what
first recommended it. It was rejected for a better reason than it was proposed:
an overlay sits on the cloth exactly when the table needs reading. A fifth tab
costs a click, and the persistent status strip already shows the live spin
readout on every tab, so the value is never out of sight while it is being set.

**The rim of the drawn ball *is* the unit circle.** The plan had been to draw a
whole ball with the unstrikeable outer band greyed, teaching the real
constraint. That was dropped on measurement. This engine models no tip, no
miscue limit, no squirt and no swerve — those words appear nowhere in the
source — and `spin_pad_map()`'s unit circle already means *maximum usable
spin*. Greying an outer band would have asserted a miscue radius nothing here
has measured: the conventional half-ball rule says 0.5 R, a training cue ball's
outer printed ring measures about 0.75 R through 21° of photographic tilt, and
the two disagree. It would also have cost half the picker's linear resolution
for no gain in truth. So the rim means "the most spin this engine can apply",
which is exactly true, and the teaching point survives as a dashed advisory
ring at 0.75 labelled as a real-cue note — drawn, not enforced.

**It snaps to the same 0.01 grid power uses**, on both axes, with the seventeen
named contact points drawn as labelled guides rather than as snap targets. A
seventeen-point snap would have made the picker discrete while the r10 nudge
buttons stayed continuous — two value spaces inside one control, which is the
shape of several bugs in this project's history.

Order matters, and it is the opposite way round from what feels natural: snap
first, clamp second. A 45° maximum is (0.7071, 0.7071); snapping that to the
grid gives (0.71, 0.71), whose magnitude is 1.0041 — more spin than the pad's
own budget allows. Clamping afterwards pulls it back to exactly 1.0. The
deliberate consequence is that rim values sit on the circle rather than on the
grid.

The picker is 100 px in radius, and that number is chosen rather than left
over: 1/100 is 0.0100 of spin per pixel, exactly the snap step, so every value
on the grid is reachable by dragging and no pixel is wasted. The cursor is now
drawn at true tip scale — 20% of the ball's radius, measured from that same
training ball — instead of the old hardcoded 5 px dot at 13.9%. The tip's size
is precisely why fine spin placement is hard in reality, and drawing it
honestly is part of the point. It is an outline rather than a disc so it cannot
hide the guide underneath it.

Adding a fifth tab set a trap that was caught before it bit. `custom_active()`
tested `panel_tab == 3`; inserting Spin after Shot moved Custom to 4, and
custom-mode mouse-table ball placement would have started firing on the Spin
tab with the entire validation chain still green. Tabs are now resolved by name.

**r30.1** fixed two things found by playing it. The Shoot button had been moved
up by a wrong constant and overlapped the aim row by 10 px — the `y += 34` it
replaced was never "the separation gap", it was the row's own 22 px height plus
a 12 px gap, and the comment got read instead of the arithmetic. And the ball
face had been drawn as two offset circles to suggest a lit sphere; because
`pygame.draw` paints flat, that was not a gradient but a hard-edged step from
238 to 222 at about r=0.45, with the advisory ring falling inside the darker
band. It read as exactly the greyed-out region this revision had argued against
drawing. Unrequested decoration is not free: in a control whose job is to teach
a constraint, any visual distinction will be read as meaning something. The
face is flat now.

**r30.2** puts a second copy of the picker on the Shot tab wherever the window
is tall enough to hold it, so a full-screen game never needs the tab switch at
all. Both copies are built by one function and are views onto the same two
closure variables, so there is no second copy of the state and only the visible
tab receives events. The fit rule is pure and tested: below a 60 px radius the
group is omitted outright rather than shrunk into uselessness, because the Spin
tab always carries the full-size one — omitting the convenience copy costs a
tab click, not a capability.

Validation: 71 assertions, 0 containment escapes over 30 batch strikes, 90
smoke frames, `--snap` byte-identical, `--aigame 12 --seed 4200` unchanged at
SHARK 9–3. Selftests 62 and 63 were both mutation-tested four ways before
shipping.

---

## r29 — power you can name

Aim had fine adjustment from r10. Power did not, and the difference was not
cosmetic: the slider spans 6.5 m/s across about 232 px of panel, which is
0.028 m/s per pixel, while the readout is formatted to two decimals. The
control displayed hundredths it could not physically reach — one pixel of drag
jumps roughly three of them. Setting a specific power was guesswork.

Measured on an empty table, using total cue-ball path length (net displacement
is meaningless once the ball starts rebounding off cushions, which it does):
0.01 m/s is worth 48 mm of travel at power 1.0, 24 mm at 1.5, 13 mm at 2.0. A
ball is 50.8 mm. At break speed it falls to 5 mm, which is why a coarse step
earns its place alongside the fine one.

A row of four buttons now sits under the slider: -0.1, -0.01, +0.01, +0.1. Four
across in a single row rather than the aim group's two stacked rows, because at
the minimum window height the Shot tab had 33 px of headroom and a second row
would have had to be paid for by shrinking the aim dial and the spin pad. The
layout was verified by instrumenting the real panel builder and reading the
widget rectangles: 15 widgets ending at 515 px became 19 ending at 540, against
a 548 px window. Eight pixels clear.

Each press snaps the result to the 0.01 grid, and the order is deliberate. The
delta is applied first and the result snapped second. Snapping first would mean
the opening press off a dragged value merely moved it onto the grid — 1.8472
would become 1.85, displaying "1.85" both before and after, and the button
would look broken. Applying first guarantees the readout always moves by
exactly one step.

Snapping is the part that answers the actual complaint. Without it a nudged
power is precise but never round, so it can be adjusted finely and still never
be repeated. With it, the displayed number is the true number, and since the
human shot path adds no noise — `do_shoot()` passes power straight to
`strike()`, unlike the AI which perturbs it — a power you can write down is a
power you can play again.

Selftest 61 covers the pure core: that a step lands on the grid, that repeated
steps do not drift off it, and that the buttons clamp to the same range the
slider spans. It failed on its first run against a wrong expectation of 1.85.
The code was right and the test was wrong; both the expectation and a docstring
describing the inferior snap-first order were corrected, and the episode is
recorded in the assertion's own comment.

## r28 — a whole frame, driven through the rules engine

The validation chain gained the test it was missing. Every assertion before
this one checks a single function in isolation: given these inputs, does it
return the right answer. A frame is not a function, it is a state machine, and
its bugs live in the ordering — in what the previous shot left behind. Nothing
tested shot N+1 against the state shot N produced, which is precisely why all
five bugs that reached the table got through: turn handover, spin reset, cue
repositioning, sandbox ball-in-hand, and the potted-ball chamber.

Selftest 60 plays a real frame, eight shots long — a dry break, an open-table
pot that assigns the suits, a continuation, a miss that hands the table over, a
wrong-ball foul, the free shot and second visit that foul buys, the last ball
of a suit, and the black — and asserts eleven named invariants after every
shot.

The shots are synthesised rather than played out in physics. That turns out to
be cheap: the rules layer reads exactly four things from the simulation, so a
frame can be driven by setting three fields and removing balls, with no physics
step at all. It stays deterministic, it runs in well under a second, and it
does not inherit the float sensitivity that makes a seeded `--aigame` score a
per-machine check. The cost is stated plainly in the source: it tests the rules
against the events the engine is *believed* to emit, and cannot catch the
physics emitting something else.

Two choices are worth recording. It asserts named invariants rather than
freezing a golden trace — a golden catches more but rewrites a large literal on
every deliberate change and freezes in whatever was wrong when it was captured,
which is the trap selftest 22 fell into at r16. And the full per-shot trace
prints only on failure, so a break diagnoses itself: with the r23 handover bug
reintroduced, the trace names shot 7 and shows the turn flipping to the wrong
player, which is the whole diagnosis in one line.

It was also mutation-tested before shipping. Five historical bugs were
reintroduced one at a time and each was confirmed caught, on the principle that
a test which has never failed has not been shown to work.

No game code changed. `--snap` is byte-identical and the seeded `--aigame`
score is unmoved, both of which are the point.

## r27 — the potted-ball chamber clears when the table does

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
