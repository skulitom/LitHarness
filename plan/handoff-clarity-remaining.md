# Handoff: finish the clarity work — the premise becomes prose, the screen becomes the gate, and the ledger gets the entry

You are an Opus 5 session working in `C:\DEV\LitHarness`. Read `CONTRIBUTING.md`, then
`plan/handoff-clarity-first.md` — its eight boundaries bind everything here and are not
restated (boundary 3 was amended in place: no craft word list survives in any form, in-prompt
or post-hoc). Then `plan/clarity-audit-2026-08-24.md`, the T1 table this work executes. When
this document and the repo disagree, the repo wins.

## State of play (what already landed, so you do not redo it)

- **T1** — the audit table: `plan/clarity-audit-2026-08-24.md` (commit 8f9a8a8).
- **T2** — the purge (commit 243a39a): all six never-explain sites deleted; the forge's
  `tone_note` channel closed and its surviving directive kinds routed through
  `directors.legal_brief` with refusals named in `report()["directives_refused"]`; the
  administration scan, the schema-word ban and the domain-vocabulary ban deleted with their
  causes; `tests/test_clarity_constitution.py` enforces the constitution by construction.
- **T5** — the context census (commit 1be3ac3):
  `research/quality-measurement/context-audit-2026-08-24.md` plus `"context": "cold_read"`
  labels in the six unregistered cold-and-silent instruments.
- **Boundary 8** — the book-generation session's second clarity pass is absorbed into
  `domain/house.py` on main (commit 85adedf). Their worktree
  (`.claude/worktrees/persona-reader-feedback-ca03cd`) still holds it uncommitted; do not
  touch that worktree, and expect them to resync against main.
- **The baseline** (commit b20a229): the four operator-refused premises of 2026-08-24
  (`reader-book-forge-a/forge.json`, `reader-book-forge-b/forge.json`) and their
  comprehension screens
  (`research/quality-measurement/results/comprehension-reader-book.json`): readers confused
  0/4 (The Post-Caller), 2/4 (The Cold Hour), 1/4 (The Second Heat), 4/4 (The Root Decides);
  undefined terms 0, 6, 2, 12.

## Remaining task 1 — T3+T4, the split and the gate

The full implementation brief is below, verbatim as authored (it was written for a delegated
agent; execute it yourself or delegate it, but gate it independently either way — targeted
pytest, ruff, `git diff --check`, LF bytes, and a full read of the diff before any commit).
Work in a fresh worktree cut from current main; `uv sync --all-extras` first or pytest
silently uses a global install.

---

Two connected pieces: the premise leaves the world call and becomes its own prose call
(**the split**), and every premise is screened by four readers before anyone sees it
(**the gate**). The operator's words, which the handoff quotes: *"We need the comprehension
to be wired. We need Opus 5 to produce and understand the premises."*

### Piece 1 — the split (`src/litharness/application/architect.py`, `src/litharness/cli.py`)

1. **The world schema stops carrying reader-facing prose.** In `_WORLD`, remove `"premise"`
   from both `required` and `properties`.
2. **The premise essay leaves `_RULES`.** In the protagonist rule, delete everything from
   `Write the \`premise\` as that person's situation` to the end of that string (it ends
   `…another name that owes a gloss.`). The rule now ends at `…that shape lists their id in
   its \`except\`.` Fix the grammar of the join if needed; read the whole rule after the cut.
3. **`worlds_from` stops checking the premise.** Remove the `("premise", …)` entry from the
   per-world emptiness checks and the `("premise", …)` axis from the distinctness loop
   (`domain` and `geometry` stay).
4. **`premise_names_protagonist`** keeps its name (grep `plan/` before touching any public
   name) and gains the text as a parameter: `premise_names_protagonist(candidate, premise:
   str) -> bool`, reading the paragraph from the argument instead of `candidate.raw`. In
   `_protagonist_complaints`, remove the premise-names check (it moves into
   `premise_complaints`); the other three checks stay.
5. **New: `PREMISE_PROFILE = "architect.premise.v0"`** and
   `render_premise_request(candidate: Candidate) -> CompletionRequest`:
   - `system = house.with_house_rules("You are pitching one novel to a reader deciding what "
     "to read next. You write one paragraph of plain prose and nothing else: no headings, "
     "no lists, no JSON.")`
   - `prompt` = the line `THE WORLD, as its own record declares it:` followed by
     `json.dumps(dict(candidate.raw), ensure_ascii=False, sort_keys=True, indent=1)`,
     followed by two newlines and: "Write the pitch for this book: one paragraph of plain
     modern English, about 200 words, in the order things happen, the way one person tells a
     friend what a book is about. Who this person was before, what happened to them, what
     they can do here that nobody else can, what it costs, and what they are heading toward.
     Name them. Every word the paragraph uses that a stranger has not met is explained in
     the paragraph itself. Nothing but the paragraph."
   - No `schema`. `max_output_tokens=8000` (the pinned provider counts thinking against the
     budget). `profile=PREMISE_PROFILE`, `call_class="generation"`, default timeout.
6. **New: `premise_complaints(premise: str, candidate: Candidate) -> tuple[str, ...]`** —
   deterministic, in the gate register the module already uses: empty/whitespace text; the
   paragraph does not name the protagonist (`premise_names_protagonist`); `_BORROWED`
   matches the paragraph (containment, RS1/C3). Nothing else — no word lists, no length
   refusal (boundary 3 as amended).
7. **`bundle_for` gains a keyword-only `premise: str` parameter** and writes it as
   `"premise": premise.strip()` instead of reading `candidate.raw`.
8. **`cmd_forge` (cli.py): the premise stage runs after `worlds_from` succeeds**, per
   candidate: `budget_check` (same shape as the world call's), `registry.complete(
   render_premise_request(candidate))`, take `result.text.strip()`, run
   `premise_complaints`. On complaints: ONE fresh retry of the byte-identical request —
   with a code comment stating that no gate or reader finding may enter the prompt
   (stage-0 §97.1) — then, still failing, the candidate is carried with its complaints and
   marked unusable (see the gate for how that is recorded). Premise-call spend across the
   forge is recorded as its own `PolicyDecision` (profile `PREMISE_PROFILE`, non-blocking
   per-candidate `GateOutcome`s, summed usage/cost).

### Piece 2 — the gate (new `src/litharness/application/comprehension.py`, wired in `cmd_forge`)

New module. Docstring: what it is (the production comprehension screen: four genre readers
restate a premise and quote every word they were never given; pass = zero undefined words
across all four; open questions are reported and never gated), why the readers carry no
named works (§97.3 — a generation-side module may not carry named published works; the
research panel's anchors do, so these are title-free derivations of its four roles), and
that `research/quality-measurement/comprehension_battery.py` is untouched as the research
measuring stick.

1. **Four frozen readers** (a small frozen dataclass with `reader_id`, `name`, `reads_for`,
   `drops_on`, and a `system()` method returning
   `f"You are {name}. You read for {reads_for}. You stop reading on {drops_on}. You answer "
   "questions about what you read in your own words, as yourself."`):
   - `climber`, "the progression and cultivation reader", reads_for "a climb with rules —
     what the next rung costs, and what it lets somebody do that they could not do before",
     drops_on "figures that move without changing what anyone can do. I start a lot of
     serials and drop most of them inside three chapters".
   - `stranger`, "the isekai and portal reader", reads_for "somebody dropped into a world
     whose rules they have to work out, using what they already knew how to do", drops_on
     "terms and ranks used as if I already knew them, or a newcomer who arrives fluent. Most
     portal stories lose me in the first chapter and I stop there".
   - `regular`, "the cozy, academy and slow-burn reader", reads_for "a place worth coming
     back to, and people who get better at something slowly enough that I see it happen",
     drops_on "grimness for its own sake, or a story that skips the years it told me
     mattered. I abandon more books than I finish and I do it without guilt".
   - `mechanism`, "the science-fiction and superhero reader", reads_for "powers with a
     mechanism under them, and consequences that follow from the mechanism rather than from
     what the scene needs", drops_on "hand-waving where the rule should be, or an ability
     that does whatever is convenient. I read the first chapter of most things and go no
     further".
2. **`ANSWER_SCHEMA`**: copy verbatim from
   `research/quality-measurement/comprehension_battery.py` (the four properties `can_do`,
   `in_the_way`, `expect_next`, `undefined_words`, `open_questions` with their
   descriptions), with a comment naming the source and the rule: the research module is the
   frozen measuring stick; this copy is the production screen; a change to one is not a
   change to the other.
3. **`render_reader_request(reader, premise) -> CompletionRequest`**: system = the reader's
   `system()` — deliberately NOT `with_house_rules` (a reader is not writing prose; say so
   in a comment); prompt = the premise, then `\n\n---\n\n`, then "That is the back-cover
   copy of a book you just picked up. Answer in your own words, as if telling a friend — do
   not quote the text back." (the research battery's own wording, kept for comparability);
   `schema=ANSWER_SCHEMA`, `max_output_tokens=1500`, `profile = SCREEN_PROFILE =
   "architect.screen.v0"`, `call_class="generation"`.
4. **`ScreenResult`** (frozen dataclass, `to_jsonable()`): per-reader parsed answers,
   `undefined_by_reader`, `open_questions_by_reader`, `readers_confused` (count with any
   undefined word), `undefined_total`, `conformed` (all four parsed), and
   `passed = conformed and undefined_total == 0`. A non-conforming reader answer means the
   attempt did not pass; it never crashes the forge.
5. **Wiring in `cmd_forge`**, after a candidate's premise clears `premise_complaints`:
   budget-check then run the four reader calls; on `passed`, done. On not passed: ONE fresh
   premise regeneration (`render_premise_request` again — the same §97.1 comment: no reader
   quote, no finding, nothing derived from the failure enters the prompt) →
   `premise_complaints` → re-screen once. Still failing: the candidate is marked. Every
   bundle gains `"screen"`: the `ScreenResult.to_jsonable()` of the LAST attempt (or
   `{"passed": false, "reason": "<premise_complaints or 'no screen run'>"}` where the
   premise stage itself failed), and `usable` in the forge summary means: no gate
   complaints AND screen passed. Screen spend is a `PolicyDecision` with profile
   `SCREEN_PROFILE`, same shape as the premise decision. Per-candidate stdout lines say
   `screen: passed (0 undefined, N open questions)` or `screen: FAILED — N undefined across
   M reader(s)`.
6. **`--pick` refuses a screen-failed candidate**: if the chosen bundle carries a `"screen"`
   key and `screen["passed"]` is false, print why (naming the screen and the handoff's rule
   that a failed premise is re-forged, never hand-patched) and return `EXIT_FAULT`. A
   bundle with NO `"screen"` key (forged before the gate existed) picks exactly as before —
   absence keeps old behaviour, the repo's standing pattern. There is NO flag to skip the
   screen; do not add one.

### Tests

Find the repository's existing fake-provider/fake-registry pattern (grep tests/) and follow
it. New `tests/test_comprehension.py` (hermetic — the registry refuses billing providers
under `LITHARNESS_ENV=test`): zero undefined across four conforming readers passes; one
undefined word in one reader fails; open questions alone never fail a screen; a
non-conforming reader answer fails the attempt; `to_jsonable` round-trips;
`render_reader_request` carries the reader's system, the premise, and the schema, and its
system does NOT contain the house rules. Update `tests/test_architect.py` for the split
(`worlds_from` without premise; the new `premise_names_protagonist` signature; each
`premise_complaints` branch; `render_premise_request` — house rules in system, world JSON
in prompt, no schema). Grep `plan/` and `tests/test_architecture.py` before renaming ANY
public name or test; ledger-cited names survive on their replacements with docstrings.

Gate: `uv run pytest tests/test_architect.py tests/test_comprehension.py
tests/test_clarity_constitution.py tests/test_architecture.py -q` and
`uv run ruff check src/litharness tests/test_comprehension.py`.

---

## Remaining task 2 — T6, the re-forge and the record

1. With T3+T4 merged: `uv run pytest`, `uv run ruff check .`, `uv run mypy`,
   `git diff --check` (the full gate, per CONTRIBUTING — check the process list first; no
   other sustained job may be running on this box).
2. Re-forge under the new pipeline: `litharness --database reader-book.db forge --k 2
   --shape direct --out reader-book-forge-c` (and a `-d` forge for a second pair if the
   first yields fewer than two screen-passed candidates). K=2, never higher — K=6 overran
   the schema at 84k output tokens on 2026-08-24. The `--max-cost-usd-per-day 10` guard
   stands. The screen runs inside the forge now; every candidate comes out with its
   `screen` block.
3. The after-measurement: run the RESEARCH battery (unchanged, the measuring stick) over
   the new forges — `uv run python research/quality-measurement/comprehension_battery.py
   --forge reader-book-forge-c/forge.json …` — and compare against the committed baseline
   (0/4, 2/4, 1/4, 4/4 readers confused; 0, 6, 2, 12 undefined terms). Both instruments'
   numbers go in the entry: the production screen's (opus readers) and the research
   battery's (its own frozen panel/model), labelled as different instruments.
4. The stage-0 entry, house form, claiming the next free § number (run the cross-worktree
   check in CLAUDE.md at claim time and again at commit time). It must name, beyond the
   audit rows: the `_CAPABILITY.manifests_as` never-clause the audit had not listed (caught
   by the construction test — a fourth instance of the family); the em-dash inheritance
   (`directors.legal_brief`'s pattern matches a literal `—` anywhere, so a forge constraint
   containing one is dropped and named in `directives_refused` — the Director rail's
   existing breadth, now shared, acceptable because refusals are visible); and the
   before/after numbers with the four attainability checks observed before declaring
   anything a bar (declare none — report the distribution).
5. Present only screen-passed premises to the operator for the pick; the operator's chosen
   world then flows `--pick` → `new` → the book. That pick is the operator's own act; no
   model orders the candidates.

## Small leftovers (one line each)

- `tests/test_outline.py::test_costs_count_as_progression`'s docstring still opens with a
  debt-story justification; the assertion is fine. Reword the docstring when touching that
  file.
- The `reader-book-forge/` directory (untracked) holds the refused K=6 overrun
  (`refused.txt`); leave it or fold its lesson into the T6 entry — do not commit it whole.
- After T3+T4 merges, remove the two spent worktrees
  (`.claude/worktrees/ox-clarity_purge-7f3a21`, `ox-context_sweep-7f3a21`) with
  `git worktree remove`.

## Delegation notes

The Ox/cline free tier hit its daily cap at 14:09 on 2026-08-24 ("try again in 5h 23m" —
so usable again from ~19:35 local). The recipe, if delegating there: write the brief to a
file, then from inside a fresh worktree run
`cline "$(cat <brief>)" -c <worktree-abs-path> -P cline -m stealth/ox-alpha --json -t 1800
--retries 6 > run.jsonl 2>&1`. `INFERENCE_CAP_ERROR` in the JSONL is the cap;
"Model returned empty response" is transient — relaunch. Gate independently regardless of
who executed. Claude subagents against the same brief are the proven fallback (T2 and T5
above were executed that way).
