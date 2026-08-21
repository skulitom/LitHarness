# Royal Road platform priors: seven claims, six manipulations, and the policy fact that changes the launch

**Status: REGISTRATION, 2026-08-21.** Written before any battery runs and before any variant is
generated, which is what makes §2's directions pre-registered rather than reported. The
operator reviewed advice from a Royal Road author in the platform's top ~1% (~2,000 followers)
on what sells there; it was distilled into the claims in §1 on 2026-08-21. **Every claim below
is a hypothesis to test under this project's regime and none of them is a rule to hard-code. A
null is a result and is recorded as one.**

Stage-0 [§104](stage-0-decisions.md) is this programme's ledger entry and carries the scope and
the bars in the canonical place; this document carries the design.

## 0. What this is, and the four things it is not

**It is** the incorporation of go-to-market priors into the measurement programme: a
manipulation family set (§2, built), a launch-package instrument design (§3), a replication arm
that mirrors the platform's browse funnel (§4), a mining scope extension (§5), and the
platform's own AI-content policy verified from the live site (§6).

It is **not** a change to any drafting directive. `plan/serial-pilot-1.md` is pre-registered and
possibly mid-run; it was read and not touched, and nothing here proposes an edit to it.

It is **not** a claim that any of these seven things is true. Two of them are already this
project's defaults — the Serial Pilot's tone note already declares close third person and past
tense, and constraint C4 already prices every gain on the page — so for those the families test
a default the project already has, and the informative outcome is the one that *refutes* it.

It is **not** licensed to run. §2's battery, §3's instrument and §4's arm are registered here
and gated on a seated reader, an operator signature on the spend, and — for §2 — the variant
generation whose ceiling is declared in §2.6.

And it is **not** a human-feedback proposal in any form. The regime is LLM-only: no readers, no
critique circles, no labels, no operator diagnostics. The one human bit in the system remains
§97.1's book-grain acceptance gate, which trains nothing.

## 1. The claims, as distilled

Numbered so §2's families and §5's mining note can cite them, and worded as the operator's
distillation rather than as findings.

| id | claim |
|---|---|
| **RR1** | Amateur signals in ch.1–2 kill trust: info dumps, many named characters at once, waking-up/mirror openings, heavy internal monologue, AI-slop-looking prose, weak blurbs/titles/covers. |
| **RR2** | The site rewards power progression front and centre (LitRPG, isekai, time loops, kingdom builders); the premise should do the genre's work. |
| **RR3** | Literary/atmospheric prose that steals the show is a liability; so are lecture-y openings. |
| **RR4** | Readers want early wins and competence (escapism); early MC torture or humiliation without adjacent triumphs bleeds readers. |
| **RR5** | Comedy is fine when native; trope imitation by an author who has not absorbed the genre is sensed and punished. Audience skews Gen Z / Alpha. |
| **RR6** | Multi-POV and present tense are hard mode; readers want one MC to root for. |
| **RR7** | The browse funnel is blurb → chapter 1 → follow decision; deep backlog and steady cadence powered the author's Rising Stars run. |

**Which claims this session can reach, and which it cannot.** RR1, RR3, RR4 and RR6 name
properties of *prose* and become §2's manipulations. RR1's blurb/title/cover half and RR7's
funnel become §3 and §4. RR2 and RR5 are premise- and authorship-level claims with no
manipulation this project can certify — a "premise that does the genre's work" is not a
transform of a text, and "trope imitation by someone who has not absorbed the genre" names an
author rather than a page. They are recorded as **unmanipulable at this instrument's grain**
rather than quietly dropped; §5's mining is the only channel that reaches them, and it reaches
them as conventions rather than as this claim.

RR7's cadence half is already settled in-repo and needs no new work: §63 owns publication
cadence and §101 owns the serial grain.

## 2. The manipulation families — D1P

**Built this session**: `research/quality-measurement/platform_priors.py`, with
`tests/test_platform_priors.py` carrying the structural invariants. Nothing has been generated
and nothing has been run.

### 2.1 Why they are D1P and not D1, and why the distinction is load-bearing

`bcr.D1_FAMILIES` is **certified damage** — graded paragraph shuffle, matched-word-count
deletion, `stat_flatten`, `interiority_strip` — damage whose sign nobody disputes. That is
precisely why `llm-reader-engagement.md` §A3 can write that a dose-response inversion there
**kills the instrument**: if allocation does not turn against certified damage, the reader is
not reading.

Nothing in this section is certified damage. "Lyrical prose is a liability on this platform" is
a claim about a readership, and the manipulation's sign is the hypothesis under test. So the
kill reading inverts:

| tier | material | an inversion kills | order |
|---|---|---|---|
| D1 | certified damage | the **instrument** | first; it is what seats the reader |
| **D1P** | platform priors | the **family** | second, on a model D1 already passed |

**A D1P family may be read only on a model already seated under §A2 and already through D1.**
Run the other way round, a family that moves nothing is indistinguishable from a reader that
perceives nothing, and there would be no way to tell which. `PRE_REGISTRATION["runs_only_on"]`
in the module says this in the artifact, so a later session cannot reorder it by accident.

### 2.2 The six families, their lanes and their signatures

| family | claim | lane | signature counter (must move) |
|---|---|---|---|
| `purple_prose_dose` | RR3 | blend | `lyric_index` up (similes + `-ly` adverbs + participial openings per 1k) |
| `suffering_load` | RR4 | blend | `setback_per_1k` up |
| `info_dump_dose` | RR1/RR3 | blend | `exposition_per_1k` up |
| `character_flood` | RR1 | insert | all six declared names present |
| `pov_fragment` | RR6 | insert | every fragment names the second POV |
| `tense_shift` | RR6 | blend | `present_aux_per_1k` up |

Two lanes, and the lane is a property of the manipulation rather than a convenience:

- **blend** — the model rewrites the whole scene under one instruction, returned under a
  numbered-paragraph contract that holds a 1:1 index map. The *changed set is discovered rather
  than requested*, so a dose is a set of the model's own edits and never a second instruction it
  could read differently at each rung.
- **insert** — the model writes K new paragraphs and the original survives byte-for-byte at
  every dose. That is a stronger certification than any blend arm can offer, and the tests
  assert it.

**Dose grows from the front.** Every claim in this set is about the opening — chapters one and
two, the browse funnel, early wins — so a dose is *how far into the book the manipulation
reaches*, front-first, and at full dose it reaches the end. A dose that damaged the middle first
would be a different manipulation from the one the claims describe.

**The grain a shelf reads is the book, not the scene.** A `bcr` shelf member needs
`MIN_CHUNKS` = 13 chunks (~3,900 words) or the budget exhausts it, and one own-generated scene
is 912 words. Generation stays per scene, because a scene is the size a single rewrite can hold;
`build_book` assembles the dosed book. Each lane counts its own front-first units: blend pools
eligible paragraphs across the book in reading order; `character_flood` puts all its names in
the opening scene, because "many at once" is a property of one place and not of a book-wide
sprinkle; `pov_fragment` counts *scenes* carrying a fragment, because a second POV is a
book-level property and the dose is how much of the book is written in two heads.

### 2.3 The placebo is the ruler, and certification is about the manipulation only

`platform_placebo` runs the same paragraph contract with an inert instruction (fix any typos).
Whatever a revision pass does on its own — drift, house-style creep, unprompted improvement —
lands there, and no family certifies except against it: it must have changed **more paragraphs
than the placebo changed** and moved **its own signature further than the placebo moved it**.
That is `repair_generation.py`'s floor discipline, reused rather than reinvented.

Certification also asserts, per (family, scene): the four rungs render four distinct texts; the
blend rungs are strictly nested; every protected system-voice span survives byte-for-byte; the
insert lane lost no original paragraph; and the word ratio is recorded, because summary is
shorter than scene and `info_dump_dose` is the arm most likely to move length — the incumbent
that correlates with everything.

**Certification is a statement about the manipulation and none at all about the claim.** A
certified family is one whose variants are what they say they are. Whether the platform prior
holds is a question for a seated reader.

### 2.4 Pre-registered directions, and three outcomes named in advance

Each family declares `confirms`, `refutes` and `null` in the module, so whichever arrives it was
a declared result rather than a story told afterwards. **The reading is two-sided for every
family**, and `purple_prose_dose` is why: the platform claim and the general craft prior point
in opposite directions, so a one-sided registration would have made one of the two answers
unreportable.

- **confirms** — allocation against the manipulated side increases with dose, and the top rung's
  interval excludes 0.5 in that direction.
- **refutes** — the same statistic in the opposite direction. For `purple_prose_dose` that is
  the interesting outcome and it is named as such; for `suffering_load` it would say early cost
  reads as stakes rather than as bleeding.
- **null** — no monotone movement and the top rung's interval contains 0.5. Recorded, and the
  claim is **not** re-run with a different manipulation to find a number.
- **kills the family** — an inversion across the ladder (largest effect at the smallest dose,
  shrinking after) says the rungs are not a dose of one thing. The family is withdrawn; the
  instrument is untouched.

**Two costs are declared with the families rather than discovered afterwards.**
`suffering_load` at high dose can contradict what a later paragraph assumes, so an honest
confirm there reads as "setbacks *or* the incoherence they introduce", and separating the two
needs a coherence-matched control this session does not build. And `tense_shift`'s ladder
measures two different things: dose 1.0 is a present-tense book, which is the claim, while every
rung below it is part-present and part-past, which is *tense instability* — a manipulation
nobody claimed anything about. The confirmatory reading there is the top rung's interval, and
the ladder is a shape reading reported under its own name.

### 2.5 Attainability, computed before the bars were written

Declared-bars rule, executed rather than asserted. The quantity is the **allocation share
against the manipulated side**, `S ∈ [0, 1]` (range), higher for the manipulated side under
`confirms` (direction), in units of `BUDGET` = 12 fetches so the per-session resolution is
1/12 = 0.0833 — except that the only model ever seated commits for a whole session, so the
effective unit is the session (unit). Non-emptiness: the corpus holds one own-generated book of
10,049 words = 33 chunks against a floor of 13, and a rehearsal on a synthetic cache built **24
shelves with none skipped**, so the shelf set is non-empty at the declared shape.

Sizing runs from the observed reader and never from `bcr --attainability`'s simulation, per the
RUNBOOK's rule: the simulator draws twelve independent fetches per session, and `phi4`'s 72
seating sessions produced shares of exactly 0.0, 0.5 or 1.0 at a per-session sd of **0.4039**.
Sessions needed for the interval half-width to reach δ, from `results/bcr-seat-phi4.json`
through `bcr.cluster_interval` (computed 2026-08-21; `platform_priors.py --selftest`
recomputes the 0.15 row and fails if it becomes unreachable):

| δ | α = 0.05 | α = 0.025 (§4's divided secondary) | α = 0.00833 (six-family adjusted) |
|---|---|---|---|
| 0.15 | 24 | 24 | **48** |
| 0.10 | 64 | 96 | 128 |
| 0.05 | 320 | 448 | 448 |

**So the confirmatory bar is stated at δ = 0.15, and the reason is arithmetic rather than
modesty.** At δ = 0.10 the six-family set costs 6 × 128 = 768 sessions = 9,216 calls ≈ 31 GPU
hours at the measured ~5 calls/min, against §97.9's cap of 40 GPU-hours **shared with F3**.
Declaring 0.10 would have named a quantity the budget cannot reach, which is the failure seven
prior declarations made.

**Multiplicity.** Each family reports its own interval at α = 0.05 and the six-family adjusted
level 0.00833 prints beside it. Any sentence about *the set* — "the platform priors reproduce" —
uses the adjusted level. There is no pooled headline.

**The declared shape, per family:** intermediate rungs 0.15 / 0.35 / 0.65 at 3 replicates × 2
orientations = 6 sessions each, top rung at 24 replicates × 2 = 48 sessions. 66 sessions =
792 calls ≈ 2.6 h per family, ≈ 16 h for six. A **screen runs first**: six families at the top
rung only, 3 replicates × 2 orientations = 36 sessions = 432 calls ≈ 1.4 h, enough to catch a
broken variant set or a wildly opposite direction before sixteen hours are spent.

At six sessions per intermediate rung the per-point sd is about 0.16, so the isotonic fit sees
only a gross inversion. **No subtle non-monotonicity is claimed**, and that limit is registered
here rather than discovered in the reading.

### 2.6 Model spend, bounded and stated before it is spent

Variant generation is the only model spend these deliverables need.

- **70 generations** — 10 scenes × (6 families + 1 placebo) — on `claude-opus-5`, the book's own
  drafter, at §85's measured **$0.2316 per generation** (32 generations for $7.41) ≈ **$16.21**.
- **Hard ceiling $25**, enforced *per call* by `--ceiling-usd`: the run stops at the ceiling
  rather than reporting an overrun afterwards.
- **Digest-keyed replay cache** (`results/platform-priors-raw.jsonl`), so an interrupted run
  resumes for free and a re-certification costs nothing. Sequential, one job: §89.5 records 390
  transport failures from two `claude -p` jobs running beside each other.
- **The D1P sessions themselves are local** (`phi4:latest` under the duty-cycle governor), so
  they are $0 marginal and cost GPU wall clock instead — §2.5's hours.

Free legs first, and each has already caught something:

```bash
uv run python research/quality-measurement/platform_priors.py --selftest
```

```bash
uv run python research/quality-measurement/platform_priors.py
```

Then, on an operator signature:

```bash
uv run python research/quality-measurement/platform_priors.py --generate --yes --certify
```

### 2.7 What is still owed before D1P can run

1. A **seated reader**. `phi4:latest` is the one live candidate and is not seated: V1's variance
   floor needs twenty own-generated texts and D2's transplant check needs a second own-generated
   book, and this repository holds one. Both print NOT RUN with their price, and `seated` is
   false while either is unrun.
2. **D1 on certified damage**, passed on that reader. §2.1's ordering is not optional.
3. **Variant generation and certification** (§2.6), with every family certified on every scene
   it will be served on.
4. **One additive line in `bcr.py`'s battery path**, or a small runner, so `shelves()`'s
   `bcr.Shelf` objects reach `bcr.play`. `battery_shelves` iterates the frozen `D1_FAMILIES`
   tuple, so registering into `ablate.BY_KEY` is not enough on its own — that is stated in the
   module's docstrings so nobody discovers it mid-run. Left undone here deliberately: `bcr.py`
   is shared with parallel sessions and the wiring belongs in the session that runs the battery.

## 3. The launch package as a modelled product surface — design only

**Nothing here is built and nothing is run.** The design exists so that the instrument shape is
registered before a blurb is written.

### 3.1 The surface, taken from the platform's own form

Royal Road's submission form (§6's `knowledgebase/84`) is the product surface, and using its
fields rather than invented ones is what keeps the design testable against the real funnel:
**Title**, **Synopsis** (the blurb), **Genres and Tags** (a selection over the platform's fixed
vocabulary, not free text), **Content Warnings** — which is where the AI-Generated tag lives,
and it is mandatory rather than optional (§6) — and **Cover**.

### 3.2 BSC — the Browse-Shelf Choice instrument

A session is one reader model, fresh context, and a shelf of **K entries** for the *same book*,
each showing title, tags and blurb and nothing else. The reader opens one; the opened entry's
first chunk is served and the session continues under a BCR budget. Recorded: **which entry was
opened first**, and the fetch sequence after it. Position-swapped across replicates, blinded.

**Why this is not the dead verdict channel.** No verbal verdict is elicited at any point — the
reader's output vocabulary is the BCR's — and the choice is *costly*: opening one entry spends
budget that cannot be spent on another. §89.4's 4,676-to-1 result is about a channel this
instrument does not use.

**And what it honestly cannot do, said here rather than found later.** With K entries pointing
at one book, everything after the first open is the same text, so continuation carries no
information about the blurb. **The endpoint is the first-open share and nothing else.** The
budget's role is to make the choice cost something, not to produce a second endpoint. A design
that reported a continuation curve here would be reporting the book under K labels.

**Controls, at packaging grain, borrowed from §A2 unchanged:** placebo (two byte-identical
entries), whitespace sham (an entry against its own respacing), rename sham (character names in
the blurb changed), and the positional check across swapped replicates. A candidate that fails
any of them is unseated for this instrument regardless of what it did on BCR — the shelf is a
different stimulus and a licence is not transferable.

**Selection is best-of-K and nothing more**, under §61 Add 3 / §72's expires-on-use rule. The
winning blurb is a selection among our own K, and the artifact says so.

### 3.3 The hard constraint, and it is sharper than "the label is refuted"

**Follower and view columns are never ground truth for blurb or packaging quality.** The
refutation is on the record (BRIEF §2 Pass 2; §77.1's `rr_high_vs_low` VOID on bias; §79), but
the specific reason this arm must not touch them is worse than a general refutation: BRIEF §3
records that the engagement label **tracks cover art and launch timing**. Scoring packaging
against a label whose known confound *is* packaging plus timing, with no story-grain matching,
would be circular and refuted at the same time. The label may appear beside a result as a
covariate; it may never grade one.

### 3.4 The cover is a brief, not a measurement

No instrument in this repository reads an image. The cover therefore enters as a **declared
brief** — a specification an operator or an image tool executes — and never as a measured
product; a "cover A beats cover B" claim has no channel here and is not proposed. The brief is
also constrained by the platform: cover art must relate directly to the story, mature or
suggestive artwork is prohibited, and the good-taste exception the rules allow for borderline
art is explicitly **not** available for AI-generated artwork (§6). That last clause is a
GTM-level fact about how our covers will be reviewed, and it is recorded here for the operator.

### 3.5 One open design question, recorded unresolved

A blurb that wins our shelf has beaten our own K, not the platform's browse page. Putting
third-party blurbs on the shelf is permitted by RS1 (measurement side) but drags BRIEF §2 Pass
6's memorisation problem onto the packaging arm — a reader-sim may open the entry it recognises.
The rename-delta rail §A6 uses for the prose baseline is the obvious candidate and has not been
designed for blurbs. **Left open rather than resolved by assertion.**

## 4. The opening-weighted BCR arm — design only

RR7's funnel says the follow decision is made in the first chapter or two. The whole-book AUC
primary endpoint averages that window with 90% of a book no browsing reader ever reaches. This
arm mirrors the funnel.

**Shape.** Each shelf member is truncated to its **first 3,000 words** — two chapters at the
~1,500-word publication format this project has already adopted as the Royal Road target — and
the budget drops to `B_open` = 9 fetches with the free opening chunk unchanged at 1. Everything
else is the BCR body untouched: same chunking, same byte-frozen system prompt, same
position-swapped replicates, same clustered bound.

**Status: an alpha-divided secondary endpoint beside the whole-book AUC primary**, per the
operator's instruction. The primary is unchanged.

**The declared bar, checked on all four properties before registering:**

- **Range** — `S_open ∈ [0, 1]`, the allocation share of the opening-only shelf. Non-degenerate.
- **Direction** — higher for the target; the arm confirms when the interval's lower bound
  exceeds 0.5, and the two-sided interval is reported either way.
- **Unit** — a share of 9 fetches, so the per-session resolution is 1/9 = 0.1111, coarser than
  the primary's 0.0833. The binding unit is still the session: an all-in reader's shares are
  0.0 / 0.5 / 1.0 whatever the budget is, which is why §2.5's sizing transfers.
- **Non-emptiness** — a member needs (1 + 9) × 300 = **3,000 words**. The own-generated book
  holds 10,049; the fitness shelf's median book holds 3,950; the RR publication format reaches
  3,000 at chapter two. The arm is non-empty on every substrate this project has.

**Alpha and what the division costs.** The secondary reads at α = 0.05 / 2 = **0.025**. From
§2.5's table that is 24 sessions at δ = 0.15 (the same as the primary) and 96 rather than 64 at
δ = 0.10 — a 50% surcharge where the arm is most likely to be sized. Recorded so the price of
the instruction is visible: a fixed-sequence test (secondary at full α, gated on the primary
clearing) would preserve family-wise error and be more powerful, and the division is the
conservative choice the operator asked for. It was considered, not overlooked.

**Sizing rule.** The table above is the *only* observed reader distribution that exists and it
comes from a full-length shelf. The opening arm's own per-session sd must be measured from its
first pilot and the arm re-sized from `bcr.empirical_sessions_needed` on that, per the RUNBOOK.
Until then §2.5's table is a price, not a promise.

**What the arm can and cannot say.** It measures allocation between two openings under scarcity.
It does not measure a follow decision, and no result here may be worded as one: RR's follow
button is a population behaviour this project has no access to and whose proxy is the refuted
label §3.3 excludes.

## 5. Trope-convention mining — an additive scope note

**A correction first, because the instruction named a retired home.**
`plan/machine-taste-program.md` is **RETIRED** (its own header, and §95.1 retires the
`PREFERENCE` class for machines at every grain); nothing in it may be executed. The live owner
of property mining is stage-0 **§97.4**'s property ledger: candidate taste-properties are mined
as **E6-located contrasts** between summit and matched mid-tier text, each entering the ledger
with **its counter or locator committed first**, and each facing §97.4's fidelity gate before
any sim or writer may act on it. This note is therefore additive to §97.4's scope and lands here
and in §104 rather than in the retired document.

**Convention properties to mine, all measurement- and mining-side only:**

- **Status-block idiom** — how a summit renders system output: field vocabulary, placement
  within the scene, frequency per 1k words, and whether a block is ever rendered as prose
  instead. Locator: the block spans; counter: blocks per 1k words and fields per block. This is
  the property the Serial Pilot already had to decide by hand when it declared `Loop | Day`.
- **Chapter-hook shapes** — what the last paragraph of a chapter does, as a small closed set of
  located contrasts (a question opened, a reversal, an arrival, a threat named, a price paid).
  Locator: the final paragraph; counter: the shape distribution over chapters.
- **Progression cadence** — the interval between visible gains in power or understanding, per 1k
  words and per chapter. Counter first, and it interlocks with W2's payoff windows and W3's
  cadence discrimination: if a reader cannot name a cadence difference, a cadence convention is
  a property of the corpus and not of a reader, and the mining note says so before it is mined.
- **Win-adjacency in openings** — RR4 as a measurable convention rather than an instruction: the
  distance in words between a named setback and the nearest named gain, within the first N words
  of a fiction. Counter: that distance, and the fraction of setbacks with a gain inside a
  declared window.

**RS1, and the near-miss it already has behind it.** Anchor and contrast text may enter
measurement, mining and validation and may **never** enter a drafting, revision or planning
prompt — whole or in part, paraphrased or verbatim. The object that crosses to the generation
side is the **located axis restated in our own words**, never the prose, and the rail is
provenance rather than pattern: corpus digests are never referenced by any generation-side
module, checkable in CI (§97.3). The specific risk this note adds is that a "convention
property" restated too closely *is* a paraphrase — "status blocks appear about twice per
thousand words" is a property, and a rendered example of one is text. The Serial Pilot's
directives are the existing precedent for the safe form: properties stated in our own words,
with C3 making the prohibition binding on the generator too.

**Nothing is mined here.** The anchor set is still incomplete (`plan/anchor-set.md`: three
verified summits, seven pending, and anchor *text* acquisition is a separate operator decision
that has not been taken), and mining without it would be a machine's taste claim wearing an
operator's authority.

## 6. Royal Road's AI-content policy, verified from the live site

**Retrieved 2026-08-21** through a real browser session. The plain fetcher returns HTTP 403 on
this site — `plan/anchor-set.md` records the same — so every line below comes from the rendered
page and every URL is checkable by opening it.

### 6.1 The finding, stated first

**AI-generated fiction is permitted on Royal Road and must be tagged.** There is no ban, no
discovery-surface exclusion written into the rules, and no Rising Stars eligibility clause about
AI anywhere in the knowledge base. The AI tags are **content warnings**, which is the mechanism
by which readers can filter them.

### 6.2 What the live pages say

**Content Guidelines** — <https://www.royalroad.com/support/knowledgebase/114>, section
"A.I. Content". It defines two tags and gives four rules for AI-generated work. The tag
definitions, verbatim in the operative part: **AI-Assisted** is for a story where "the author
has used an AI tool for editing or proofreading"; **AI-Generated** is for a story that "was
generated using an AI tool" with the author prompting, directing and editing. The four rules,
paraphrased except where the exact obligation matters:

1. Quality must be retained — AI-generated content is to be moderated and refined by the author
   for quality, continuity and readability, and low-effort text generation is to be avoided.
2. Reviews, comments, forum posts and user interaction generally may not contain AI-generated
   content unless quoted.
3. The content must not violate laws or the site's rules, and the page states plainly that this
   is a new area where the law may change: **"any use of AI-generated content is at your own
   risk."**
4. **"You must tag your story as 'AI-Generated'."** The page adds that readers may say a story
   is AI-generated in reviews whether or not it carries the tag.

Two adjacent clauses on the same page matter for §3.4. Cover artwork "must relate directly to
the story it represents", and on the good-taste exception the rules allow for borderline art:
**"No such exceptions are granted for AI-generated artwork."**

**AI Text Policy blog post**, dated 21/06/2023, marked OFFICIAL POLICY and linked from the
Content Guidelines page as the full explanation —
<https://www.royalroad.com/blog/57/royal-road-ai-text-policy>. It sets out three tiers (general
assistive technologies such as spell-checkers, which need no tag; AI-Assisted; AI-Generated) and
records why the platform chose to allow rather than ban: detection is unreliable, and the post
declines to write rules it cannot enforce. It also states the platform's disposition plainly:
readers decide what they want to read, and the site's lists let them filter it. Blog index page
1 (retrieved the same day) carries no later AI-policy post, so the 2023 post is still the linked
authority.

**Submitting and verifying novels** —
<https://www.royalroad.com/support/knowledgebase/84>. AI-Assisted Content and AI-Generated
Content appear in the **Content Warnings** section of the submission form, beside Graphic
Violence, Profanity, Sensitive Content and Sexual Content. Approval is a manual staff check;
around 10% of submissions are rejected, and the named checks are plagiarism, links in the
synopsis, fanfiction tagging, sexual content, political or religious content and disturbing
content. **AI is not among the named rejection checks.**

**Advanced search** — <https://www.royalroad.com/fictions/search?advanced=true>. "AI-ASSISTED
CONTENT" and "AI-GENERATED CONTENT" are listed under **Content Warnings**, i.e. they are
filterable by readers in the same control as the mature-content warnings.

**Discovery & Ranking** — <https://www.royalroad.com/support/knowledgebase/78>. Describes Front
Page, Best Rated, Trending, Ongoing, Complete, Popular this Week, New Releases, Latest Updates,
**Rising Stars**, Recommended for You and Others Also Liked. Rising Stars is described only as
"the newest, hottest fictions on the platform determined by multiple factors and complex
calculations", rotating often. **No AI clause appears anywhere on the page**, and the only
stated eligibility rule of any kind is that recommendation lists need a fiction to be Ongoing or
Completed.

**General Rules** — <https://www.royalroad.com/support/knowledgebase/115>. No AI clause. One
line is directly relevant to any automated go-to-market: **"Manipulating fiction scores and
rankings is strictly prohibited"**, including alternate accounts and rating trades.

**Terms of Service** — <https://www.royalroad.com/tos>, last updated March 03, 2025. **No
AI-content clause at all.** It does prohibit scraping, crawling, caching and spidering, and the
use of bots or automated methods to access the services, without express permission.

### 6.3 The GTM-level reading, for the operator

**The launch is not blocked, and the risk is reputational rather than procedural.** Four
consequences:

1. **The AI-Generated tag is mandatory and is a content warning.** It goes on the submission
   form beside the mature-content warnings, and readers can filter on it. The packaging design
   in §3 must treat it as a fixed field, never a variable — a study that varied it would be
   studying the tag, and omitting it would be a rules violation.
2. **No discovery surface excludes AI-tagged work in the written rules**, Rising Stars included.
   What the rules do not say and cannot be established from them is how much a *reader* discount
   the tag carries in practice; the platform's own policy language ("readers will decide")
   invites exactly that discount, and site forum threads on the AI policy show it is contested.
   **That is a population effect with no measurement here and it is not estimated.**
3. **The quality rule is the enforceable one.** "Low-effort text generation" is the named
   prohibition, which puts the burden on exactly the quality goal this project already has. It
   is also the clause with a discretionary human reviewer behind it at submission.
4. **Two operational rails.** The ToS prohibits automated access without permission, so any
   posting path must be a human or an authorised integration, not a scraper; and the General
   Rules prohibit manipulating scores and rankings, which forecloses every "seed the metrics"
   tactic outright.

**None of this changes the value of the repository work.** The measurement programme's target is
whether the prose earns allocation; the platform's policy decides how the finished book is
labelled and where a labelled book is discounted. Those are separate questions and the second
one is the operator's, not this document's.

## 7. Non-negotiables, and what this session did and did not do

**Honoured, each with where it shows.** LLM-only regime — no human reader, label, critique or
diagnostic appears in any proposal here; §3 and §4 elicit no verbal verdict. The verdict channel
stays dead — §2 is behavioural (BCR allocation), §5 is the report channel (E6-located contrasts)
and no design has a preference leg. Everything model-sourced stays advisory until §10.4 promotes
it — nothing here blocks, parks or gates a draft. RS1 — no anchor or contrast text enters or
leaves any module built here, and §5's crossing object is a restated axis. Declared bars —
§2.5's and §4's quantities were checked for range, direction, unit and non-emptiness before
being registered, and §2.5's bar is at 0.15 because 0.10 was computed to be out of budget.
Additive — one new module, one new test file, one new plan doc, one new stage-0 section at the
next free number (verified free across every branch and worktree on 2026-08-21); nothing
renumbered, nothing rewritten. Serial Pilot 1 — read, not touched. GPU — nothing in this session
ran local inference; §2.5's battery is the leg that will, under the duty-cycle governor with the
per-fetch checkpoint the cache already provides.

**Delivered:** this document; stage-0 §104; `research/quality-measurement/platform_priors.py`
(six families, two lanes, certification, book-grain builder, `bcr.Shelf` bridge, free selftest
that recomputes the attainability row); `tests/test_platform_priors.py`; §3, §4 and §5 as
designs; §6 as a verified policy record.

**Not done, deliberately:** no variants generated, no battery run, no frontier study, no edit to
`bcr.py`, no mining, no blurb written, and no change to any drafting directive anywhere in the
repository.

**The next session's order, and nothing in it starts before the one above it:** seat a reader
(§2.7 item 1) → D1 on certified damage → generate and certify variants under §2.6's ceiling →
the six-family screen → the full D1P shape. §3 and §4 are independently gated and can be
sequenced against whatever the operator wants first.
