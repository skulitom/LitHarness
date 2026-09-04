# Findings — v3, the replication: the effect survived a fresh draw of the permutation luck

House form: the claim, the number beside it, and the caveat travelling with the claim.
`PREREG-v3-replication.md` owns the design, the prediction and the four outcomes fixed before
this arm ran; v1's and v2's registrations and findings are untouched beside it. Status:
**OBSERVED**, 2026-09-04, and **REPLICATED** by the registered table. Raw records in
`raw-v3.jsonl`, result in `results-arm-v3.json`. Nothing here promotes a claim past OBSERVED and
nothing here qualifies a mechanism to steer a book.

## The prediction, and what happened

The registration fixed this before the arm ran:

> `intact − shuffled` excludes zero on the low side, with a point estimate near +0.164 — made
> explicit as **[+0.08, +0.25]**, so that "near" could not be decided after the fact.

**Observed: +0.1890, 90% interval [+0.0747, +0.2955].** Inside the band, excluding zero. By the
table fixed before spend this is **REPLICATED**: the effect survived a fresh draw of the
permutation luck that v2's own seed spread said was the size of the effect.

| | v2 | v3 |
| --- | --- | --- |
| shuffle seeds | 0, 1, 2 | 3, 4, 5 (and 3, 5, 6 for `fitness-08`) |
| **intact − shuffled** | **+0.1640 [+0.0881, +0.2390]** | **+0.1890 [+0.0747, +0.2955]** |
| **sham − shuffled** | **+0.2411 [+0.1512, +0.3366]** | **+0.1571 [+0.0690, +0.2437]** |
| intact − sham | −0.0771 [−0.1658, +0.0146] | +0.0318 [−0.0506, +0.1173] |
| books moving as predicted | 16 of 20, median +0.2054 | 14 of 20, median +0.2440 |
| `fp5` | 0.219 | 0.196 |
| capacity, slot-A share | 0.5508 | 0.5740 |
| sessions scorable | 180 of 180 | 180 of 180 |
| transport failures | 0 | 0 |
| spend / wall | $49.78, 2h04 | $50.35, 2h04 |

**Nothing is pooled.** Two arms, reported side by side, no combined interval — combining them
after seeing the first would make the pair one arm with a larger n and no registration.

## The caution the replication actually removed

v2's findings led with three ways the result could be less than it looked. **The first is now
substantially weaker.** The worry was that the whitespace sham's point estimate ran *negative* in
v2 (−0.0771: the re-flowed copy drawing more reads than the intact one), which is not what an
inert placebo does, and that a layout confound would first show there. Across three measurements
of that contrast the sign scatters:

| | v1 (slot-A cells) | v2 | v3 |
| --- | --- | --- | --- |
| intact − sham | +0.089 | −0.077 | +0.032 |

All three contain zero and they do not agree on a direction, which is what an inert placebo looks
like and not what a confound looks like. The other two cautions stand unchanged: the effect is
still in the band this design can see rather than comfortably inside it (v3's +0.189 is nearer
the declared 0.1875 target than v2's +0.164 was), and the shuffle-seed spread is still about the
size of the effect — 0.1957 here against 0.1804 in v2 — which is precisely why this arm existed.

## What the two arms together license, stated narrowly

**A reader whose continuing costs it something reads a book less when that book's paragraph
order is destroyed, and the finding is not an artifact of which permutation was drawn.** For a
book in the slot this reader attends to, on this system's own twenty drafted books, with
`claude-haiku-4-5` over `claude -p`.

That is the first mechanism in this house to move with a **story-level** manipulation and hold
under replication, where §195.5's panel and §199.1's `readers` lanes both moved with surface or
not at all. It is **not** a quality instrument, and the distance is the same one `BRIEF.md`'s
whole ledger measures: a whole-book paragraph shuffle is the most violent order damage available,
and noticing it says nothing about noticing a chapter that is merely worse.

## Provenance: this arm ran on the pre-fix module

v3 was bought while `elicit.spend()` still read the cache unlocked (§228, fixed on main as
`ffaee27` after this arm started and before these results were committed). **What that defect
could do is raise, and nothing else.** It cannot alter a session's content, its cache key or its
scoring: the ceiling check between sessions either completes or throws, and a throw would have
stopped the run with every bought session intact in the cache. Nor could it miscount silently —
CPython raises on a size change during `.values()` iteration, every key these arms write is new
so a same-size replacement cannot occur, and in the v2/v3 path the sum was compared against an
infinite dollar ceiling in any case. It did not fire: 180 of 180 sessions ran and the arm exited
zero. So the numbers above are unaffected, and the fix changes what a *future* run risks rather
than what this one measured.

## What is owed

**The milder manipulation**, unchanged from v2's findings and now the whole of what stands
between this and a real claim: the gap between "notices a shuffled book" and "notices a worse
chapter" is where every dead proxy in `BRIEF.md` lives. §104's D1P families are the candidate the
ledger already owns, and they wanted a seated reader before a dose meant anything — two
replicated arms is the closest this instrument has to a seating.

**And the skip this session owes to its own code**: `run_cells` evaluates `spend()` before
comparing it, so the v2/v3 path priced a full cache sum about 180 times to compare it against
infinity. That call is pure waste in these arms and was the sole trigger of §228's race from this
side. Named here so it is fixed against the next arm rather than forgotten.
