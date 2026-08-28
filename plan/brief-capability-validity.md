# Brief-capability arm — can a brief move tone, and can it break the premise lock?

**Status: REGISTRATION, 2026-08-28. Written before any call.** The question is the operator's,
in their own words, from the fifth read: *"I didn't say Light Fantasy missing was a defect, I
was just concerned we build a system that is not capable of producing this."*
[`reader-read-5.md`](reader-read-5.md) §4.4 records why nothing on disk can answer it yet —
every listing this project has ever drawn ran under an **empty brief**, and all four dossiers
are disaster-shaped, so *won't by default* and *can't when asked* predict the same artifacts.
`research/quality-measurement/brief_capability.py` carries the frozen bytes; nothing there may
be interpreted outside this document.

## 0. Why there is no judge in this, and what the third seat is

Every seat here is arithmetic. No model is asked whether a listing is light, good, fresh or
grim — the judge channel is the one that died twenty times in `BRIEF.md` and six more in the
handoff session. What the models do is **write listings**; what the code does is **count tokens
and divide**, against the market's own 60-listing distribution and against our own empty-brief
baseline. A model that wrote a listing is never asked about it.

The one place a lexicon appears (§2's T) is a **membership count over our own outputs**, which
is §116's shape exactly — that entry counted an administrative word family over 30 forged
worlds, with no model judging and no bar. What stays banned is what the operator banned there:
a **craft word list**, in a prompt or as a refusal gate (*"forbidden-words list sounds like a
hack solution to an underlying problem"*). Nothing here enters a prompt and nothing here refuses
anything.

## 1. The three conditions, byte-frozen

One axis only: **the brief**. The listing task, the house floor, the writer dossiers, K, the
model and every counter are held fixed, so a difference between conditions is the brief.

| condition | the brief, verbatim |
| --- | --- |
| `empty` | `""` — renders as `render_overview_request`'s *"Anything you would most want to read."* This is the control every listing on disk was drawn under. |
| `label` | `light fantasy` |
| `situation` | `Nobody dies in this one. The worst thing that can happen is that somebody loses the work they are good at, in front of people whose opinion they mind.` |

**`label` is in the design on purpose and is expected to misbehave.**
`render_overview_request`'s own docstring is the reason: §136 measured `progression fantasy`
outweighing every rule in the prompt, and the rule that came out of it is *"a brief is a story,
a situation, a constraint somebody cares about — or nothing. It is not a shelf label."* An arm
that ran only a good brief could not tell **a brief works** from **a label works**, and the
second is the failure this project has already bought once. `label` is the two-word shelf label,
included so the distinction is measured rather than assumed.

**`situation` carries no tonal adjective and no genre word**, deliberately. It is a constraint
about stakes, which is one of the three shapes the rule admits. If tone moves under it, the
situation moved it — not a tone word being echoed back.

Four writers (`ferreira`, `halloran`, `vance`, `okonjo`), **K = 4 draws** per writer per
condition, the same K as every sibling instrument (§124). 48 generation calls, exactly.

## 2. The measurables, all code

**P — premise lock.** Per writer per condition: mean pairwise Jaccard over the K draws'
**first-sentence content-token sets** (stopwords removed, lowercased, punctuation stripped).
This is `blurb_rewrite.draw_agreement`'s and `blurb_tribunal`'s KD idea pointed at the opening
sentence instead of at flags. High P means the writer opens the same way every draw — which is
what §4.3 found in text: 7 of 7, 5 of 5, 4 of 4, 4 of 4. **Direction: a brief that breaks the
lock lowers P against the same writer's `empty` baseline.** No bar.

**T — threat-word share.** Per listing: members of a frozen threat family per 100 words. The
family and the false-positive discipline are §116's, including its lesson that a recall-tuned
list run as a gate has inverted error costs — so T is **reported and never gates**. Read against
two references: the same statistic over the market's 60 admitted listings, and the same
statistic over our own `empty` draws.

**C — coordinator density.** `and`/`then` per 100 words, the statistic
[`reader-read-5.md`](reader-read-5.md) §4.1 used to locate the operator's *"list with constant
and then"* — pilot 11 at 6.48 against a market max of 5.88. Carried here for free because the
draws exist anyway, so the arm also reads whether a brief moves that defect.

**The shipped counters**, imported from `listing_arms.panel` rather than reinvented: words,
sentences, longest sentence, genre nouns per 1k, numbers per 1k, and `outside` against the
market's p10–p90 band.

## 3. Kills and controls, fixed before any call

- **KT — transport.** A failed call is excluded from every rate and counted per condition and
  per draw, never scored. **§145 is why this is spelled out**: that run recorded 18 failures,
  every one on one leg, and the committed file read as a result until they were attributed. The
  run output says to read KT first, and no cell with a failure is reported without its count.
- **KP0 — P must be able to be low.** Across writers *within* a condition, P computed on
  different writers' openings is the floor. If between-writer P is not clearly below
  within-writer P, the statistic is measuring the prompt rather than the premise and **the arm
  reads nothing about premise lock**. This is the arm's own sham.
- **KD — degenerate draws.** If any cell's K draws are byte-identical, the transport replayed
  or the sampler collapsed; that cell is void.
- **KN — the null is a result** (§61). *"No brief moves P or T"* is a finding and is written up
  as one. It is the outcome that **confirms the operator's concern**, and this document says so
  before the numbers exist so that a null cannot later be read as a failed experiment.

## 4. The readings, fixed before any call

All four cells are named now, so no result can be arranged into a story afterwards.

1. **`situation` lowers P and moves T toward the market's lighter end.** Then the default is
   manufactured by our own text, the system can when asked, and the operator's concern is
   answered in the reassuring direction. The lever is the dossiers (§4.3's roster act).
2. **Neither brief lowers P.** Then the premise lock is not brief-breakable, and that is a
   **genuine capability finding** — the operator's concern confirmed. It escalates to the
   dossiers as the only remaining lever, and to whether a writer can be given a beat-free
   dossier at all.
3. **`label` moves things and `situation` does not.** §136 replicating: the brief channel is a
   label channel, and the rule that a brief is not a shelf label needs re-examining rather than
   restating.
4. **T moves and P does not, or the reverse.** Tone and premise are separable, which decides
   whether the roster needs one change or two.

**What no cell licenses.** Nothing here says a listing is good, and nothing here ranks the four
writers (§137 leaves that with no key). T is a description of word membership and is not a
measure of whether a book is fun.

## 5. Anti-scope

- **§97.1 and the read boundary.** The brief is the **designed operator input channel** —
  briefs were always operator-supplied and pilot 3 ran under one. The operator's direction
  entering there is not a diagnostic laundered into a prompt. Nothing in
  [`reader-read-5.md`](reader-read-5.md) §4's defect quotes is mined for prompt language, and
  the `situation` brief above is written from the operator's *stated wish*, not from their
  defect sentences.
- **RS1.** The market pool enters on the measurement side only, as a band of counters. No
  corpus text reaches any generation call.
- **§95.** LLM-only: the seats that write are models, the seats that measure are arithmetic.
- **No production path changes.** This writes to `derived/` and `results/`; no drafting,
  planning or revision path reads it. No clause is added to any prompt whatever the result.
- **Not a metric proposal.** `BRIEF.md` governs anything that would become a quality measure;
  T and P are descriptions of our own outputs under a manipulation, with no bar and no target.

## 6. Cost gate

Free legs first: `--selftest` and `--dry-run` print the exact call arithmetic and construct no
registry. `--run` refuses without `--yes`, and refuses above the registered guard of **60**
worst-case calls. The exact planned cost is **48 generation calls**, one per writer per
condition per draw. One CLI arm at a time on this box; the process list is checked at launch,
and the arm does not run beside a drafting run.

## 7. What is owed and is not in this arm

**A dark-direction control.** This arm can show a brief moving T toward the lighter end; it
cannot show the same statistic moving the other way on demand, because no grim-situation
condition is drawn. So a T that moves is evidence the channel works in the direction tested and
not evidence that T tracks tone in general. Named here rather than discovered later; it is one
more condition and 16 more calls whenever it is wanted.
