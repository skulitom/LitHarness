# Handoff: the listing loop, and the two artifacts nobody has measured

Written 2026-08-25 at the end of a long session. Read the boundaries before the tasks.

## Boundaries

1. **A rule may say what fails. It may not enumerate what succeeds.** This is now written into
   `domain/house.py`'s own docstring and it was learned five times in one day, then measured
   four ways on one clause (§138). Permission-only was **six times worse than prohibition-only
   and worse than saying nothing**. If you add a clause anywhere and it comes back as a phrase
   in the prose, this is why.
2. **Before you add a clause, run `uv run litharness prompts`.** Every role's assembled prompt
   has a size and a declared ceiling (`tests/test_prompt_budget.py`). Crossing a ceiling fails a
   test that prints the numbered list of demands. Raise the number on purpose and write down
   why, or take something out. The listing prompt reached **sixteen demands for a hundred-word
   artifact** before anybody could see the total, and the model met them by compressing four
   clauses into one 79-word sentence.
3. **The inputs cost more than the rules.** §136: two words of brief — `progression fantasy`,
   rendered under *"What this book is to be about"* — outweighed every rule in the prompt. A
   brief is a story, a situation or a constraint somebody cares about, or nothing. It is not a
   shelf label.
4. **One rule, two artifacts, two densities.** Number density and `house.ACCUMULATION` were both
   right for a scene and wrong for a listing. Before moving a clause between call sites, ask
   what the artifact is.
5. **Nothing here says whether a book is good.** Every number below is a distribution against
   the market's, never a bar. §137 is why: the distinctness statistic that gates any writer
   comparison has no resolution — two 400-word drafts of one scene by one writer sit closer
   together than a legal contract sits to source code.

## What is built and works

`uv run litharness library` publishes `book-library/<slug>/`: a reading copy in Markdown and
styled HTML, `overview.txt`, and per-chapter pastable files as an HTML fragment plus `.txt`.
Every tick republishes without being asked. **The pastable fragments carry no classes, ids or
styles on purpose** — that is the subset every rich-text editor preserves, and the reading copy
is the only artifact with a `<head>`. Do not style them.

`uv run litharness world` is the Architect's tool suite over the triple store — `vocabulary`,
`summary`, `show`, `rules`, `ladders`, `abilities`, `cast`, `threads`, `presence`, `check`,
`declare`, `accept`. `uv run litharness architect seed|grow` runs the Architect as an agent
holding `Bash(litharness world:*)` and nothing else; everything it declares is `PROPOSED` until
`world accept` carries it with a decision row.

`application/overview.py` writes a listing and a title. `application/readers.py` holds the two
disjoint reader pools. A book is seeded without the forge: `new "Title" --scenes N --premise
"<listing>"`, then `architect seed`, then `world accept`.

## Where the listing got to, and how it is measured

Eleven rounds, every change traced to a measured cause, against ten RoyalRoad listings the
operator supplied as the target. `research/quality-measurement/platform_priors.panel` is the
counter set — frozen under §104 for a different arm, never fitted to anything written here.

| | round 1 | now | the market |
| --- | --- | --- | --- |
| the genre's own nouns per listing | 0.1 | 2.4-3.1 | 3.8 |
| number tokens per 1k words | 43.2 | 6.0-7.0 | 7.2 |
| floor and rank positions | — | 0 of 8 | 0 of 10 |
| em dashes per 1k | 11.8 | 0.0 | 0.0 |
| words | 207-257 | 101-111 | 40-146, median 100 |
| second person as protagonist | 2-3 of 8 | 0 of 8 | 0 of 10 |

Operator reading: **20/100 at round one, 45-70 per writer now.**

## Tasks

### 1. Chapter output has never been looked at

The whole session went into the listing. **No chapter has been drafted since every one of these
changes landed**, and the scene path carries a different prompt: `house.HOUSE_RULES` in full
(25 demands), plus `status_example`, `progression`, `criteria`, `standing`, `chapter`,
`point_of_view`, `scene_plan` and the packet, each appended conditionally. `litharness prompts
--role scene` shows the floor at 28 demands *before* any of that.

The cramming arithmetic that broke the listing has never been run on a scene. Draft one, count
its longest sentence, and read it. `serial4.db` holds an eight-scene book; a fresh book from a
current listing is the better test.

### 2. Titles are unknown quality

Eight exist, from `render_title_request`. Read with their listings by the four measurement
readers they scored **1/4, 2/4, 3/4, 3/4, 4/4, 4/4, 4/4, 3/4** — pooled 24/32.

**That spread is the interesting part and it needs a controlled look before anybody believes
it.** The browsing pool returned 15/16, 16/16 and 16/16 in three earlier rounds and was written
off as saturated (§134's ceiling, three times over). It discriminated here. Two things changed
at once — the artifact gained a title, and the listings got better — so which unstuck it is
unknown. The cheap test: read the same eight listings **without** their titles.

The readers' reasons on the 1/4 are the first defect this session that an instrument found
rather than the operator: *"every beat here is one I've read a dozen times — corporate guy, menu
in the eyes, climb the tower"*, *"a kill-count mark that pays back power is just an XP bar with a
wrist strap"*. **Genre-cliché fatigue**, and nothing counts it.

Also: nothing carries a generated title into a book. `new` still takes it positionally, so the
loop produces titles a person has to move by hand. `library.slugify` consumes the title for the
folder name and every chapter filename, which is why `overview.clean_title` exists.

### 3. A title has to be free to use, and nothing checks

Operator direction: *"for titles especially we need some sort of search agent to make sure the
title is permissable to be used"*. A serial platform will not take a title that collides with a
running book, and a title colliding with a well-known one is worse than a bad title.

The shape that fits what is already here: the Architect is an agent with a narrow tool allowance
(`world_agent.ALLOWED_TOOLS`, `CompletionRequest.allowed_tools`, `providers/cli.py` renders it).
A title check is the same pattern with a different tool. **What it must not become**: a model
asked whether a title is *good*. §61(5) and §105.1 — no model ranks or selects without
containment, and the refutation ledger is twenty dead proxies long. Availability is a lookup
with an answer; desirability is not.

## What was tried and did not work, so it is not tried again

- **Continuation and browsing saturate.** 13/16, 15/16, 15/16, 16/16, 16/16 across four rounds.
  §134: continuation cannot rank candidates drawn from one prompt. Do not buy a preference
  number from a saturated instrument; §138's counters are what moved.
- **`writer_distinctness` cannot answer G1 at scene length.** §137. Its verdict was
  `DISTINCT_BUT_ORDER_BLIND` and the calibration makes both halves empty.
- **A fifth rule against one complaint does not work.** §127, and §138 is the sixth. What worked
  was subtraction and a gate.
- **The comprehension screen over-flags a listing.** About a third of what it quotes as
  uncashable, the same reader also files as a hook. Calibration unproven for blurbs.
