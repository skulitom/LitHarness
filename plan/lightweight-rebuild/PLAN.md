# LitHarness lightweight rebuild plan

2026-09-27. Status: **proposal for the operator's approval. Nothing has been executed, no code has been
written, and no model was called.**

Evidence: `evidence/*.md` beside this file holds seven digests written by read-only agents over this repository,
its memory and `C:/DEV/LitHarnessLite`. They are working notes, not evidence in themselves; each claim in them
points at a primary source (a file and line, a commit, or a section of `plan/stage-0-decisions.md`, called § here).
Three independent designs, two judges and three adversarial reviews (data safety, fidelity to evidence, scope)
produced this version, and two verifiers checked it. [M] marks a measured fact and [I] an inference. Paths outside
`experiments/` and `C:/DEV/LitHarnessLite` refer to the incumbent tree, kept at the tag `legacy/incumbent-2026-09-27`
after cutover.

## 1. Decision in brief

1. Main is **replaced in place** by a stdlib-only package of about 1,000 lines grown from LitHarnessLite, with
   a hard cap of 1,300. There is no database, queue, MCP server or third-party dependency. Git history is kept.
   The incumbent stays reachable at the tag `legacy/incumbent-2026-09-27` and the branch `legacy/main`.
2. A serial is a folder of plain files outside the repo. A **pitch** call (one per serial) writes a short bible
   that you glance at before any chapter money is spent. Each ~1,500-word Royal Road chapter then costs **2
   Codex calls** (plan, then draft), plus a located tells rewrite on most chapters: about 21-27k tokens, or
   14-18k per 1,000 words. The incumbent's chapter stage used ~33k per 1,000 words and its full-book trial ~67k [M].
3. Code owns "numbers go up". The character opens his status on the page as `[Label: value]` lines, and code
   reads those lines back into the sheet. Every chapter plans one rise, and code checks that it is printed.
4. Eight deterministic checks, each tied to your reads, can redraw a stage (at most 3 draws, "draw k of n"
   shown). Everything else is an inert report. **Your read is the only quality gate**; no model judges or selects.
5. The work splits into two phases. **Phase A** builds the new tree on a branch, spends no money, takes no
   lock and blocks nothing. **Phase B** is one short sitting: it moves ignored data into an archive (never
   deleting it) and fast-forwards main. Phase B waits on one thing that only you can do (§10 Q1).
6. Lite's win is one pair judged by the generator's own model family, and you have read neither chapter.
   Nothing here claims quality; the loop is built to find out.

## 2. What we learned (the lessons this design rests on)

1. [M] The incumbent's slowness is its call graph, not its Python. Of 16 chapter-stage calls (129,661 tokens),
   8 were "Reply with the single word OK." probes (27% of wall time). One outline planned 24 scenes to draft 4,
   and 3 more calls compressed scenes that were drafted blind to each other. Python overhead was ~11 s.
   (`evidence/pipeline.md`; Lite `experiments/2026-09-27-opening/baseline-metadata.json`)
2. [M] Lite's 2 calls (15,904 tokens) beat that chapter in both blinded orders. The evidence is thin: one pair,
   a same-family judge, the damage control run in one orientation, and an identical-text null that the judge's
   prompt primes. (Lite `REPORT.md`; `benchmark.py:24-25,126`)
3. [M] Our words become story, **and** the model brings a money frame on its own. 4 of the 5 failed read-21
   draws had a located cause in our text (§263-§265, §267), and read 20's rent line came from READER_LIFE
   (§262). But draws 1, 2 and 4 also carried money wording that no recorded request contained (§266), and
   Lite's plan made the hero "a council drainage worker on probation after falsifying a safety inspection"
   (`lite/plan.md:7`). So we need a lint over what we send **and** an output check with a bounded redraw.
4. [M] Clauses are signed and lists get recited. A permission clause gave 47.2 number tokens per 1k words
   against 7.0 for a prohibition (§138). A six-pressure list became every arc: "water" 66/16/8 mentions, "fight"
   0 (§263). A checklist in the listing task returned a list-shaped listing (§261, read 20).
5. [M] Machinery fixed every defect family that the reads stopped naming: 14 refusals, $7.33, no false
   positives across the incumbent's deterministic gates. No register clause moved a sentence metric in ten
   chapters, and you ordered them removed at read 13. (`plan/agent-impact/REPORT.md:14-46`; §187)
6. [M] Fact packets turn into minutiae. 65% of the scene-1 prompt was facts, and 23 of 37 "page-image" facts
   shared wording with the page (§182; baseline trace 0021).
7. [M] The sheet machinery (6,653 lines, 38 ledger sections) mostly fixed its own defects, and printed gains never
   reached the sheet reader (§234, §236). "Ranks are the numbers" stands (§113). A status that "came up randomly"
   read as noise; you want the character to open it and weigh his options (read 10, `plan/serial-pilot-15b.md:601-641`).
8. [M] You want progress "as soon as possible" and "constant and regular" (read 7; `plan/house-genre-constraint.md:84`).
   The market prints much less (51% of LitRPG chapters have no progression event, §155), so this is your
   recorded departure from the market median, not a market norm.
9. [M] The hook fields (a first use in chapter 1, the threat and where it first reaches him, the prize in his
   pre-System words, the System's look) reached the page in the coordinator's read of pilot 25 (§198). **No read
   of yours has confirmed them**, and read 20 still failed the hook.
10. [M] Long books fail between chapters: the only currency was spent twice and a culled man came back (§242).
    Volume 1 was "a disaster" (memory, 2026-09-07).
11. [M] Neither LLM gates nor simulated readers predict your verdict. The gate passed material you then failed at
    reads 9-13 and 20; at read 17 the coordinator's own hand read had praised 3 of the 9 items you named. A
    shuffled opening of ours beat The Primal Hunter 20/20 (§195.5), and the production readers continued 4/4 on
    shuffled copies (§199.1).
12. [M] Judges have measured failure modes: gemma answered "A" 106/106 and the pick-a-side channel was void
    while "name the difference" discriminated (§89); the draft is the unit of variance (§133, §134); a one-call
    locator has reliability 0.54 (`research/quality-measurement/comic-beats-results.md:18`).
13. [M] The regular AI tells ran 3-10x the shelf rate. A located, counter-verified rewrite cut chained "and" from
    6.0 to 1.0 per 1k, but it can make a sentence worse where the counter cannot see ("like a bar of soap
    goes"). The reviser, a different stage, introduced glosses and was dropped. (§199; §185; §196)
14. [M] Transport isolation carries weight. From inside a repo, `claude -p` leaked an untracked filename or the
    working directory in about 2 of 5 calls (§258). CLAUDE.md leaked without the flags (§109), and `--bare` logs
    the subscription out. The hardening has drifted across 23 call sites (`evidence/operations.md`).
15. [M] Bloat grows back without an enforced limit. The 34% cut in 530f40e regrew in 5.2 days. Deleting what
    "advances no story" removed 35,780 lines, while reference-counted pruning (§214) removed 1,041. The repo is
    47 days old: src grew from 6k to 66k lines, tests to 96k and research code to 101k. (`evidence/bloat.md`)
16. [M] Verification was slow because tests were tied to prose and to research. The slowest test (45-59 s)
    resolves symbols named in prose. 410 test names are frozen by ledger citations. About 32k test lines exercise
    one-off research. Windows CI takes 10-14 minutes, and 9 of the last 20 runs were cancelled by newer pushes.
17. [M] A side prototype dies. The 09-08 clean start was retired within a day. Its one chapter kept the money
    and number register, it had no matched comparison, and its transport was ported into the incumbent (c69e5ad,
    +2,439 lines; 917ce1a). The incumbent then grew through 177 more commits in 18 days. [I] The rebuild must
    replace the incumbent, not sit beside it.
18. [M] Lite's own REPORT advised keeping the incumbent as a runnable reference until the clean version shows
    continuity over several chapters (`REPORT.md:7-10`). Your wipe instruction overrides that. The legacy tag
    plus the archived, junction-linked baseline draw keep a matched comparison possible.

## 3. Target architecture

### 3.1 Repo tree (main after cutover)

```
README.md AGENTS.md CLAUDE.md LEARNINGS.md DECISIONS.md     line caps in §5 (docs)
.gitignore .gitattributes .github/workflows/ci.yml          (<=40 lines of YAML)
litharness/  __init__.py __main__.py transport.py files.py serial.py
             prompts.py sheet.py checks.py tells.py         (§3.2)
briefs/slot.txt               Lite's brief, verbatim
reads/CHECKLIST.md            your enumerable items, IDs kept from tools/chapter_one_items.json; never model-facing
reads/NN.md                   one per operator read from 21 on: your words, located cause, what it became
tests/  __init__.py  test_*.py  fixtures.json  test_zz_time.py
experiments/2026-09-27-opening/        Lite's frozen evidence, byte for byte (90 files, 1.93 MB, no third-party text)
experiments/2026-09-27-rebuild-plan/   this plan and its evidence digests, frozen
```

There is no pyproject, uv.lock, src/ layout, migration, `.mcp.json`, skill or workflow. It needs Python 3.11 or
later and a signed-in Codex CLI. `.gitignore`: `runs/ serials/ shelf/ book-library*/ research/ derived/
corpora/ exports/ output/ dist/ *.db* .venv/ .agents/ .claude/worktrees/ __pycache__/ *.pyc *_cache/
.hypothesis/ .coverage* *.egg-info/ build/ htmlcov/`. `.gitattributes` is Lite's, including
`experiments/** -text -whitespace`.

### 3.2 Modules and line budgets (physical lines; runtime cap 1,300; any file <=350)

| Module | Job | M0 | M1a | M1b | M2 |
|---|---|---|---|---|---|
| `__main__.py` | argparse, verbs, exit codes 0 done / 1 needs a person / 2 fault | 40 | 60 | 100 | 100 |
| `transport.py` | the only place a CLI is spawned: codex(), receipts, isolation, canary | 150 | 150 | 180 | 180 |
| `files.py` | byte writes, hashes, manifest, serial and box locks, PID liveness | 80 | 80 | 100 | 100 |
| `serial.py` | stages, context assembly, redraw rule, resume, usage totals | 90 | 90 | 200 | 240 |
| `prompts.py` | every model-facing string | 40 | 40 | 70 | 80 |
| `sheet.py` | status-line parse, ladder index, sheet update, rise/zero/fall | 0 | 70 | 70 | 70 |
| `checks.py` | lexicons, hard checks, reports, `report.md` | 0 | 180 | 180 | 180 |
| `tells.py` | narration-only tell counter, ported from legacy `domain/tells.py` | 0 | 120 | 120 | 120 |
| **Total** | | **400** | **790** | **1,020** | **1,070** |

That leaves 230 lines under the cap for triggered admissions (§4), whose budgets total 270 if all six fire. When
a file or the reserve runs out, reports are cut first (in the order `address`, `cast`, `digits`) before any cap
moves. Raising a cap is its own one-line commit that names the case.

### 3.3 Serial folder and state

The data root is `$LITHARNESS_HOME` (default `~/LitHarness-data`), outside every git tree. `serials/<slug>/`
holds `serial.json` (words, model, effort, repo sha, CLI version), `brief.md`, `manifest.json` (per stage: the sha256
of each input, meaning brief, bible, sheet, state, plan, previous chapter and the rendered template text; output
sha256; draw k of n; call directory), `lock`, `ch00/` (the pitch), `chNN/`, and `attempts/<utc>/`
for anything `redraw` moved aside. Nothing is ever deleted. Each call writes `calls/<stage>-d<k>/` with the
request, system prompt, events, stderr, `final.md` and `receipt.json`.

| File | Written by | When | Cap | Seen by |
|---|---|---|---|---|
| `brief.md` | you or the coordinator | before `new` | <=150 words | pitch, plan, draft |
| `ch00/bible.md` | pitch call | `new` | <=900 words | plan and draft (whole) |
| `chNN/sheet.txt` | **code** | ch00 from `Start:` lines; chNN after chapter N | <=12 lines | plan, draft |
| `chNN/state.md` | plan call N | from state N-1 and chapter N-1 | <=600 words | plan N+1; draft N |
| `chNN/plan.md` | plan call N | same response | <=400 words | draft N |
| `chNN/final.md` | draft call N | raw output; its hash equals the receipt's | none | nobody |
| `chNN/chapter.md` | code (normalized `final.md`) | after the draft | length check | plan and draft N+1, you |
| `chNN/report.md` | code | after checks | none | you and the coordinator, never a model |

**Bible** (pitch output, parsed by heading): `# Title`; `## Listing` (2-3 sentences); `## Person` (name, `Age:`
20-29, what he was doing when the System arrived, what he was good at before it, what he wants in his own words);
`## Exception` (what he alone has, and which world rule it breaks); `## First use` (the first time it works in
chapter 1 and what it wins him); `## Threat` (what can kill him, where it first reaches him); `## Prize` (what the
next rank gets him, in his pre-System words); `## System` (look and voice; `Ladder:` at least 3 rank names,
lowest first; `Start:` 1-6 `[Label: value]` lines, each above zero); `## People` (up to 3: name, want, how they
talk); `## Limits` (what using the exception takes from his body or his time, or the risk it puts him in). The
Person field asks what he was doing and good at, never "life" or "job", because the model's money prior comes in
through that door ("rents a room", read-21 draw 4).

**Plan call output**: `=== STATE ===` with `## Where` (each named person: place, condition, want), `## Held`
(counted things he carries), `## Open` (<=8 plain lines, no ids, no due dates) and `## So far` (<=150 words,
rewritten each time). Then `=== PLAN ===` with `Title:`, `## Opening`, `## Movements` (three, each a cause, his
choice and its consequence: Lite's spine), `Rise:` (`Label: old -> new | movement k | the on-page act that earns
it`, required in every chapter, and movement 1 in chapter 1), `## Options` (the choices on offer and what each
would give him, or `none`), `## People` (<=4 named on the page) and `## Ending` (what he holds at the end that he
did not hold at the start, and what comes for it next). In chapter 1 the plan call writes the first state from
the bible.

**Sheet.** A status line is a line that is entirely `[...]`. `[Label: value]` is a field. A value is a whole
number, a Ladder name (mapped to its 1-based index, so bronze = 1 and gold = 3) or a pool `n/m`. Any other bracket
line is a System notice. After chapter N, code sets each label to its last printed value, and a new label counts
as an acquisition. Pools are compared by m, and n may fall to 0. Nothing is extracted from prose. The counted
possessions in `## Held` are model-written; they are checked only by the coordinator's between-chapter read.

### 3.4 Per-chapter calls (sizes include the measured ~3.7k-token Codex floor per call)

| Call | Context | In | Out |
|---|---|---|---|
| pitch (once) | SYSTEM + PITCH, brief | ~4.2k | ~1.5k |
| plan N | SYSTEM + PLAN, brief, bible, sheet N-1, state N-1, chapter N-1 in full | ~8.5k | ~1.5k |
| draft N | SYSTEM + DRAFT, brief, bible, sheet N-1, state N, plan N, chapter N-1 in full | ~9k | ~2.2k |
| tells rewrite N (only when triggered, §3.6) | located sentences with one sentence of context each | ~5k | ~0.5k |

- First draw: 2 calls and about 21k tokens per chapter, or 3 calls and about 27k with the tells rewrite, with
  context flat in chapter count. A 24-chapter book is about 48-72 calls and 0.5-0.65M tokens (36k words); the
  incumbent's full-book trial took 129 calls and 3.59M tokens for 53.5k words [M].
- The writer sees the whole bible. At 900 words or fewer it is not a §182-sized packet, and it removes the
  section-selection code. If your read names starvation or minutiae, that is the trigger to change it.
- A transport fault gets at most 2 identical retries before any answer is read, and a retry never counts as a
  draw. An assembled request over 32,000 characters is refused (exit 2), never truncated.

### 3.5 Prompt policy

1. All model-facing text lives in `prompts.py` (SYSTEM, PITCH, PLAN, DRAFT, REWRITE), at most 700 words in total.
   DRAFT is Lite's winning text adapted from "opening chapter" to chapter N, plus the target length, "no title or
   headings; `***` for a scene break", and one format sentence: "When he opens his status or the System speaks,
   put each of its lines on its own line in square brackets, fields as `[Label: value]` with the labels on the
   sheet." Printing is diegetic only; there is no "print when a value changes" rule, because read 10 called that
   noise.
2. PLAN carries one structural sentence every chapter: "A status value rises in this chapter, earned on the page."
3. No register or sentence-craft clauses, examples, example lives, operator quotes or permission-form quantity
   rules. Output headings are allowed; lists of content (pressures, lives, options to include) are not. A banned
   word never appears, not even negated. The one story rule is stated positively and has no money word ("takes
   from his body or his time, or puts him at risk"). (§138, §262-§267, read 13)
4. Model-written text is forwarded only after it passes `money`; `leak` applies to chapter text and titles only.
   Reports, reads, CHECKLIST.md and fixtures never reach a model.
5. Prompts are versioned by git. Receipts record the sha256 of every prompt and input. No test pins prompt bytes.
6. When you name a new defect, the fix is the cheapest class that works: delete prompt text, then a bible or plan
   field, then a check that can redraw, then a mechanical transform. A clause comes last, only as a prohibition of
   the specific thing, and only with a failing fixture.

### 3.6 Checks (`checks.py`, `sheet.py`, `tells.py`)

Check IDs are words, so they never collide with CHECKLIST.md's IDs (C1-C4, L1-L6, W1-W3, H1-H8) or Lite's four
defects (called Lite-1 to Lite-4).

**The redraw rule** (§266). Before redrawing on a `money` hit, code searches the assembled request (templates,
brief, and the body text of forwarded files) for the offending word. If it is there, no redraw: exit 1 with
"located in our request: <file>:<line>". A `leak` hit is never located, because the headings and field labels
it flags are carried by format; it always redraws. Otherwise the same stage is redrawn with nothing changed, at
most 3 draws.
The manifest stores each stage's input sha256s and its draw count. Re-running after 3 failed draws exits 1
without a call unless an input changed; a changed input opens draws 4-6, numbered on. A draft stage that exhausts
its draws never re-plans by itself; `redraw --from N` does that.

**Hard checks** (redraw):

| Check | Stage | What fails | Evidence |
|---|---|---|---|
| `money` | whole words with listed inflections, never prefixes (so "Owen" is not "owe"). Pitch: the money words plus institutional words (court, clerk, council, probation, inspect/inspection/inspector, paperwork, permit, contract, deed, tax, money, currency, obligation, unpaid). Plan and chapter: money words only (rent/rents/rented/renting/rental, landlord, tenant, lease, mortgage, bills, wages and the noun "wage", salary, paycheck, payday, payment, debt, owe/owes/owed/owing, loan, ledger, invoice, overdraft, budget, repay, creditor, licence/license, unpaid, obligation, currency), including dialogue | the longest-lived premise defect | §116; §262; §266; read 20; Lite `plan.md:7` |
| `leak` | chapter, titles | a `#` heading, `===`, `Chapter N`/`Scene N`, our field labels at line start; Ladder, Rung, Sheet, Standing, Listing, Prize or Exception used as a name | read 11; §198.1; baseline "due by s000024" |
| `person` | chapter | first-person narration above 2 per 1k words, counted on the raw draft outside speech, italics and bracket lines | read 19; pilot 24 |
| `rise` | chapter | the plan's Rise label is not printed at its new value; in chapter 1, no status line or first rise after the word midpoint | reads 2, 4, 7, 10, 18 |
| `fields` | chapter, pitch | an unparseable field for a sheet label; a whole-number or Ladder field at 0; a pool with m < 1 or n > m; new labels that would take the sheet past 12 lines | §201; read-21 refusals |
| `pitch-shape` | pitch | an empty section; Age outside 20-29; Ladder < 3; Start not 1-6 lines; People > 3; Listing > 3 sentences or any over 27 words; bible > 900 words | target readership; reads 10, 17 |
| `plan-shape` | plan | markers or headings missing; caps exceeded; Rise missing, `none`, unparseable or lacking its act; chapter 1 Rise not in movement 1 | reads 2, 4, 7, 10 |
| `length` | chapter | under 0.6x or over 1.8x the target words | Lite's 4,069 words against a 1,500 target; memory royalroad-chapter-length-target |

**Normalizers** (applied to `chapter.md`, counted in the report; `final.md` keeps the raw text): em and en dashes
become ", "; a leading `# ` title line is lifted out; 3 or more of `*-_~=` on a line becomes `***`, collapsed and
never at an edge; UTF-8 with LF, written as bytes. Italic markers stay (the person check uses them to find direct
thought); §240 stripped them as a model tic, and they are stripped again if your read names them.

**Reports** (`report.md`; they never block and are never shown to a model):

| Report | Contents |
|---|---|
| `len-band` | length outside 0.8x-4/3x target (1,200-2,000 words at 1,500) |
| `admin` | plan and chapter institutional words (court, clerk, council, inspection, probation, paperwork, permit, contract, deed, tax, paid, price, coin, cash, bank, money): rate per 1k, first hit, sentences. "Darren paid out rope." (Lite `chapter.md:254`) is why these only report |
| `tells` | narration-only rates per 1k against the shelf ceilings (absence 2.6, paradox 0, "the way" 0.6, echo 1.0, chained "and" 0.5), sentences over 35 words, median sentence length and the share under 4 words (shelf median 10-16), each located |
| `digits` | digits and number words outside status lines per 1k, with sentences |
| `cast` | named people (capitalized, not sentence-initial, 2 or more hits); flag above 5 |
| `literals` | chapter 1: name, age, first use present on the page (Lite-1: the age was never stated) |
| `sheet` | falls, acquisitions not in Rise, word index of the first rise, a label spelled two ways, generic HP/MP/Gold/XP labels, chapters with no status line |
| `address` | "you" outside speech, italics per 1k, present-tense narration rate |
| `usage` | draws k of n, calls, tokens (cached, uncached, unknown), seconds; over 30k tokens per chapter flagged |

**Located tells rewrite** (M2, one call). Reads 1-19 already named the gloss, mechanics and absence families
(8, 6 and 3 reads), so you are not asked to name them again. When `tells` shows 2 or more families over ceiling
in a chapter, one call rewrites only the located sentences. Each rewrite must clear the counter and the `money`,
`leak` and `person` checks, or the original sentence is kept. `report.md` is written after the rewrite and lists
every rewrite beside its original. "like a bar of soap goes" is a fixture.

Every check ID has one positive and one negative fixture. Lexicon words are covered by a loop that builds one
sentence per word. Document-level checks (`length`, `len-band`, `pitch-shape`, `plan-shape`, `rise`, `sheet`,
`usage`) build their two fixtures in test code from `experiments/2026-09-27-opening/` files. `fixtures.json` holds
only located sentences from reads and chapters, with "Owen Price" (`baseline/chapter-one.md:166`) and "Darren paid
out rope." among the negatives. A single observed false
positive moves a word from `money` to `admin` in a one-line commit. Items no counter can catch (literal figures,
diction, glosses beyond the counted families, standalone sense, hook grip, power in hand, relatable life, popcorn
tone, iceberg, Lite-3's unestablished helmet, Lite-4's convenient device) go in `reads/CHECKLIST.md`. The
coordinator hand-reads every chapter against it, line by line, never delegated, and records **residuals only,
never a pass**, because that hand read has also misjudged.

### 3.7 Transport (`transport.py`; the only module that spawns a CLI)

- **codex()**: Lite's `complete()` and `parse_result()` flag for flag (`lite.py:52-65, 99-123, 140-162`): `exec
  --ignore-user-config --ignore-rules --ephemeral --skip-git-repo-check --sandbox read-only --cd <empty temp> --json
  --color never --output-last-message <file> -`, `project_doc_max_bytes=0`, web search off, every `features.*`
  false, `history.persistence=none`, the 30-key environment allow-list (no API keys), the native exe resolved
  from the npm shim, wrapper scripts refused. It refuses tool items, anything other than one `turn.completed`, a
  final file that differs from the last message, and malformed usage. Added from the incumbent: `codex login
  status` must print "Logged in using ChatGPT" (once per process), `codex --version` is recorded, and "Reconnecting"
  and WebSocket-fallback notices are tolerated within one turn (legacy `providers/codex_cli.py:218-246, 464-517`).
- A fresh TemporaryDirectory that has no `.git` ancestor (asserted); the seven `GIT_*` location variables stripped;
  a 900 s timeout with no outer wrapper; a receipt written as `running` before the call and completed after it;
  an injectable runner, so no unit test spawns a CLI.
- **Canary pin**: `canary` runs from a temporary git repo that holds marker `AGENTS.md`/`CLAUDE.md` nonces and an
  untracked `GIT_CONTEXT_LEAKED_<nonce>` file, and asks for any nonce it can see, or NONE. A pass records
  `{codex: {version, passed_utc}}` in `$LITHARNESS_HOME/canary.json`. `new` and `next` exit 1 when the installed
  version differs from the recorded one. The canary uses codex()'s argv with `--cd` set to its temporary git repo;
  it is the only caller exempt from the no-`.git` assertion.
- **claude()** exists only if the on-request bench (§4) is built: the full legacy isolation argv (`-p --safe-mode
  --output-format json --tools '' --strict-mcp-config --mcp-config '{"mcpServers":{}}' --no-session-persistence
  --permission-mode manual --setting-sources user --settings '{"claudeMdExcludes":[...],"autoMemoryEnabled":false}'
  --system-prompt`, prompt on stdin, UTF-8, never `--bare`) and its own canary entry. It is never used for generation.

### 3.8 CLI (`python -m litharness`); resuming means re-running the same command

| Verb | Does | Calls |
|---|---|---|
| `new <slug> --brief F [--words 1500]` | creates the serial, runs the pitch and its checks, stops for your glance | 1 (<=3) |
| `next <slug> [-n K]` (K <= 10) | plan, draft, normalize, checks, sheet, optional tells rewrite, report, per chapter | 2-3 per chapter |
| `status [<slug>]` | read-only: chapters, words, draws, failing checks with quotes, tokens, hand-edited files, lock holder, next command | 0 |
| `redraw <slug> --from N` | moves chN and later aside to `attempts/<utc>/` (N = 0 redraws the pitch) | 0 |
| `check <file.md> [--stage pitch\|plan\|chapter] [--serial <slug>]` | every deterministic check on any text (default stage: chapter) | 0 |
| `canary` | live isolation canary and CLI version pin | 1 small |

Without `--serial`, `check` treats the file as chapter 1 with no plan or bible: `rise` fails only on zero status
lines or a first rise after the midpoint, `plan-shape` skips the chapter-1 movement rule, and `literals` is
skipped. The defaults are Codex `gpt-6-astra` at medium effort, close third person and past tense. Hand edits to the brief,
bible, state or plan are recorded (status flags them; receipts record the sha that was sent), never refused.
Chapter text is never hand-edited; redraw instead. A completed receipt whose `final.md` hash matches is adopted
on resume without spending again. Writes go to a temp file, then fsync, then `os.replace`, with a bounded retry on a
Windows `PermissionError`; hashes are taken of the stored bytes (this fixes Lite's CRLF hash mismatch).

**Locks.** `new`, `next` and `canary` hold the box lock: the existing convention, `mkdir runs/box.lock` in the main
checkout plus a `holder` file. The main checkout is found from the `.git` entry above the package, without
spawning git: a worktree's `.git` file names its gitdir, whose common directory sits in the main checkout. Our holder line is `litharness
pid=<pid> start=<process creation time> <verb> <slug> <utc>`. The runtime clears a lock by itself only when the
holder is in exactly that form and the process is provably gone (ctypes `OpenProcess` plus `GetExitCodeProcess` on
Windows, never `os.kill(pid, 0)`, which terminates the process there). Any other holder means exit 1 with "box
held by: <line>". The per-serial lock uses the same rule.

## 4. Not built, and the admission rule

**Not built**: SQLite, migrations, queue, conductor, ports and adapters, litharness-contracts, the MCP server and
`.mcp.json`, skills, workflows, pyproject and uv.lock; health probes, provider registry, routing tiers, fallback,
a Claude generation path; the Architect world graph and tool loops, the three-call concept pipeline, listing
panels and simulated readers, arc outlines, per-scene drafting and scene summaries, the promise ledger,
extraction, advancement and ladder engines, the reviser, repair, the editorial controller, roster, dossiers,
director, recruit and revoice; covers, dashboard, release queue, volumes, NOTES templates; research/, the stage-0
ledger, PLAN.md, RESEARCH.md, claim states and registration ceremony; tests that read documents or pin prompt
bytes, coverage floors, xdist, check lanes, mypy strict, the 4-job CI matrix and the history-wide corpus audit;
runtime feature flags with control arms; Lite's `benchmark.py`, `analyze.py` and `test_benchmark.py` (after
`totals()` moves into `serial.py`; all stay at `legacy/lite-2026-09-27`).

**Built only when its trigger fires** (runtime budgets come from the 230 reserved lines; they total 270, so a
sixth admission first cuts reports per §3.2):

| Component | Trigger | Budget |
|---|---|---|
| Royal Road export (`<p>`, `<hr>`, `<br>`, only `< > &` escaped, no title heading, `currentColor` status table, `.txt` twin; the §240 cases as tests) | you say a chapter is ready to post; your first real paste is the acceptance test | 60 |
| Bench (`bench.py` at the root, outside the runtime: both orders for every pair including damage, sibling-draft null, k=4 drafts x 3 briefs, E6 located differences first, quotes verified, Codex plus a Claude cross-family judge) | you ask for a comparison | bench <=300; claude() 50 |
| Exemplar shelf (operator-placed under `$LITHARNESS_HOME/shelf`, draft call only, a shared 8-word run redraws) | you say so; it re-applies your §196 approval | 60 |
| Separate state call | a between-chapter contradiction traced to the combined plan call | 40 |
| Arc field in the bible | plan drift in a chapter 5-10 run; enumerated arc lists stay refused (§261, §263) | 40 |
| Quoted-conflicts field in the plan output | a between-chapter contradiction reaches your read after the coordinator's read missed it | 20 |

**Admission rule** (AGENTS.md; all five apply):
1. The trigger is a named failure on a real chapter from this system: an item from your read or a
   between-chapter contradiction. It is committed first as a failing fixture.
2. The fix is the cheapest class that works (§3.5.6). A register clause never qualifies.
3. The commit message states the net lines, and the budgets still pass.
4. A change that adds a call or changes what the writer sees is judged by your read of the redrawn chapter. A bench
   report may be attached as description; it never decides.
5. Deletion rule (530f40e): code that is not on the chapter path and not exercised by a fixture is deleted.
   Citations never keep code alive.

## 5. Guardrails (`tests/test_guards.py` <=120 lines; each guard <=25 lines; no allowlists, no exception dicts)

| Guard | Rule |
|---|---|
| `size` | `litharness/*.py` <=1,300 physical lines; any `.py` <=350; `bench.py` <=300; `tests/*.py` <= runtime lines; no `§` in any `.py` |
| `stdlib` | every import in `litharness/` and `bench.py` is in `sys.stdlib_module_names` or is `litharness` (AST) |
| `prompts` | templates <=700 words; no `money` or `admin` word; no negation of one; no 6-word run shared with any fixture |
| `transport` | in `litharness/*.py` and `bench.py`, `subprocess` is imported only by `transport.py` |
| `tracked` | every tracked file <=512 KB (the largest Lite trace is 470,671 bytes); nothing tracked under `runs serials shelf book-library research` or matching `*.db*`; no tracked `.md/.txt/.json` shares a 12-word run with any `.txt` under `$LITHARNESS_HOME/shelf` or the four archived exemplar folders (`C:\DEV\LitHarness-archive\tree\book-library\{PrimalHunter,DefianceOfTheFall,RandidlyGhosthound,TheGam3}`) when they exist locally (skipped in CI) |
| `docs` | line counts only: README 80, AGENTS 80, CLAUDE 40, LEARNINGS 150, DECISIONS 80, reads/CHECKLIST 40, each reads/NN 60 |
| `fixtures` | `fixtures.json` <=60 entries, each <=40 words |
| `time` | `tests/__init__.py` stamps the start; `test_zz_time.py` fails above 15 s (target 3 s) |
| `spend` | at most 3 draws per stage per input set, 2 transport retries, requests over 32,000 characters refused, K <= 10 per `next` (constants in `serial.py` with behaviour tests) |

## 6. Wipe and cutover procedure

PowerShell 5.1 on this host. `$R='C:\DEV\LitHarness'`, `$A='C:\DEV\LitHarness-archive'` (same volume, not a
git tree), `$W='C:\DEV\LitHarness-rebuild'`. This plan folder is committed on main before Phase A starts, so it is
part of `$T`. Every git command uses `git -C`. Rules for the whole track: never
`--force`, never `git clean`, never `git branch -D`, never `git gc --prune=now` or `git reflog expire`; never
delete or push `refs/codex/*` or `refs/cline/*` (they hold the only other copy of the uncommitted work); other
sessions' worktrees are left in place (one holds an ignored 18 MB copy of the fitness corpus).

### Phase A: build (no lock, no spend, not blocked by §10 Q1)

- **A1 Freeze and back up refs.** `git -C $R fetch origin`; `$T = git -C $R rev-parse origin/main` (40f58a2 today)
  and record it. Push the two local-only branches by name: `git -C $R push origin claude/ox-alpha-trial-7f3a21
  merge/r3`. Then list any other local-only branch (`git -C $R rev-list --count <b> --not --remotes` not 0); if one
  exists, stop and show its added files before pushing anything.
- **A2 Legacy refs** (all new, so no force): `git -C $R branch legacy/main $T`; `git -C $R tag -a
  legacy/incumbent-2026-09-27 $T -m "Incumbent before the lightweight rebuild"`; `git -C $R fetch
  C:/DEV/LitHarnessLite main:import/lite`; `git -C $R tag -a legacy/lite-2026-09-27 import/lite -m "LitHarnessLite
  and the frozen opening comparison"`; `git -C $R push origin legacy/main legacy/incumbent-2026-09-27
  legacy/lite-2026-09-27`. *Verify*: `git -C $R ls-remote --refs origin 'legacy/*'` shows three refs;
  `import/lite` is 79c476f.
- **A3 Build tree.** `git -C $R worktree add $W -b rebuild/lite $T`. Commit 1: `git -C $W rm -r -q -- .`, "Retire
  the incumbent; it remains at legacy/incumbent-2026-09-27". Commit 2: `git -C $W merge --allow-unrelated-histories
  --no-ff import/lite` (an empty tree, so no conflicts; Lite's `.gitignore` and `.gitattributes` arrive here).
  Then the M0 commits (§7). This plan's folder comes back from `$T`: `git -C $W restore --source=$T --staged
  --worktree -- plan/lightweight-rebuild`, then `git -C $W mv plan/lightweight-rebuild
  experiments/2026-09-27-rebuild-plan`. Before each commit, `git -C $W diff --cached --name-only --diff-filter=A` must list only expected paths.
- **A4 Scripts for Phase B.** Write `experiments/2026-09-27-rebuild-plan/move-ignored.ps1` (the B5 loop below),
  ASCII only, because PowerShell 5.1 reads BOM-less UTF-8 as ANSI. Run it in list-only mode against `$R` and
  review the printed plan.
- **A5 Publish the branch.** `git -C $W push -u origin rebuild/lite`; CI green on both jobs. Main is untouched.

### Phase B: cutover (one sitting, after §10 Q1; box lock held throughout)

- **B0 Preconditions and lock.** (a) Q1 is resolved and the Codex thread has stopped. (b) `git -C $R fetch
  origin`; `git -C $R rev-list --count origin/main..main` prints 0. Quiet check: `git -C $R log -1 --format=%ci
  origin/main` and the newest epoch-milliseconds field in the `refs/codex/turn-diffs` ref names (`(git -C $R
  for-each-ref --format='%(refname)' refs/codex/turn-diffs | % { [int64]$_.Split('/')[6] } | Measure-Object
  -Maximum).Maximum`) are both more than 2 hours old. (c) Process check: `Get-CimInstance Win32_Process | ? {
  $_.Name -in 'codex.exe','ChatGPT.exe' -or ($_.Name -notin 'powershell.exe','bash.exe','cmd.exe','conhost.exe'
  -and $_.CommandLine -match 'claude(\.exe)?"?\s+-p|pytest|mypy|litharness|\\\.venv\\Scripts\\python|thermal_watch|MirrorBench|Haltere') }
  | select ProcessId,ParentProcessId,Name,CommandLine`. Expected: the litharness-mcp processes (B3); the Codex app
  itself, for which you confirm that no Codex thread is working in `$R`; and standing MCP or editor processes
  (AgentUI `mcp.js`, `anode.exe mcp`, `Code.exe`, `git-bash.exe`). Anything else (a Haltere or MirrorBench job, a
  test run, a model call) means wait. (d) `New-Item -ItemType Directory "$R\runs\box.lock" -ErrorAction Stop`,
  write a holder line, announce the start.
- **B1 Other sessions' work.** Route (a), the default: the Codex thread has pushed its WIP to a `wip/*` branch and
  its files are gone from the tree. Route (b), only on your yes, preserves it on a pushed branch instead:
  `New-Item -ItemType Directory -Force "$A\wip"`; `git -C $R diff --binary HEAD --output="$A\wip\primary-0926.patch"`
  (git writes the file, so PowerShell cannot re-encode it); `git -C $R worktree add --detach "$A\wip\check" HEAD`;
  `git -C "$A\wip\check" apply "$A\wip\primary-0926.patch"`; copy the three untracked source files in; for each of
  the 16 paths assert `(git -C "$A\wip\check" hash-object -- $f) -eq (git -C $R hash-object -- $f)`; then in the
  check worktree `switch -c wip/codex-0926`, `add -A`, commit "Codex thread WIP, archived at cutover", `push origin
  wip/codex-0926`, and `git -C $R worktree remove "$A\wip\check"` (clean, so no force). Only then `git -C $R
  restore --staged --worktree -- <13 files>`, and move the 3 untracked source files to `$A\wip\files\<same path>`.
  Record the patch base sha, and that Codex checkpoint tree 90ecc99 holds the same bytes (local only, never
  pushed), in `$A\MANIFEST.tsv`. In both routes, the 13 untracked 09-04 volume-screen results and 3 `run.log` files (the reader-sims track's, our own
  generated data) move to `$A\wip\files\<same path>` under the manifest. *Verify*: `git -C $R status --porcelain`
  prints exactly `?? .agents/`.
- **B2 If main moved past T**, meaning `(git -C $R rev-parse origin/main) -ne $T` after B0's fetch. `git -C $R
  tag -a legacy/incumbent-2026-09-27b origin/main -m "Incumbent tip at cutover"` (a second pass uses the suffix
  `c`); `git -C $R push origin legacy/incumbent-2026-09-27b origin/main:refs/heads/legacy/main` (a
  fast-forward of the legacy branch); `git -C $R fetch origin legacy/main:legacy/main`; in the build tree `$pre = git -C $W rev-parse HEAD; git -C $W merge -s ours
  origin/main -m "Record incumbent commits after the freeze"`; `git -C $W diff --stat $pre HEAD` must print
  nothing. Push `rebuild/lite` and wait for green.
- **B3 Stop the holders of `litharness.db`.** Preferred: disable the litharness MCP connector in the session that
  owns it (`/mcp`), so the process exits. Otherwise `$p = Get-CimInstance Win32_Process | ? { $_.Name -in
  'uv.exe','litharness-mcp.exe','python.exe' -and $_.CommandLine -match 'litharness-mcp' }` and `Stop-Process -Id
  $p.ProcessId -Confirm:$false`. Never stop `claude.exe`, `$PID` or its ancestors. *Verify*: none remain, and a
  re-query just before B5 is still empty.
- **B4 Memory backup.** `Copy-Item -Recurse -LiteralPath
  "$env:USERPROFILE\.claude\projects\C--DEV-LitHarness\memory" "$A\memory-2026-09-27"` and add it to the manifest.
- **B5 Move ignored state** (`move-ignored.ps1`). Build the candidate list once with `git -C $R ls-files --others
  --ignored --exclude-standard --directory`; drop any path whose ancestor is already listed; group each SQLite
  file with its `-wal` and `-shm`. Keep in place: `.venv/`, `.hypothesis/`, ignored `.claude/` entries,
  `runs/box.lock`, and every `__pycache__/` and `*_cache/` wherever it is, including under `research/`. B5 first
  copies `move-ignored.ps1` to `$A\` so the reverse loop survives a rollback. Order: every ignored path under `research/` first (the 1.96 GB fictions
  file, `derived/` 343 MB, corpora, results), then each child of `runs/` except `box.lock` (12 GB), `book-library/`
  (including the four commercial exemplar folders), `litharness.db*`, `exports/`, `output/`, `dist/`,
  `dashboard.html`, `.coverage`. Each row is written to `$A\MANIFEST.tsv` as `planned` with bytes and file count (a
  sha256 only for `*.db*`), then `$d = Join-Path "$A\tree" $p; if (Test-Path -LiteralPath $d) { throw "exists: $d"
  }; New-Item -ItemType Directory -Force (Split-Path $d) | Out-Null; Move-Item -LiteralPath (Join-Path $R $p)
  -Destination $d -ErrorAction Stop` (a same-volume rename), then marked `moved`. The forward loop treats a row as
  done when its `$A\tree` destination exists, and the reverse loop when its source path exists again, so either
  can be re-run. Then `New-Item -ItemType Junction -Path
  "$R\runs\chapter-one\read-21\draw-6" -Target "$A\tree\runs\chapter-one\read-21\draw-6"` (after creating its
  parents) keeps Lite's baseline paths and the draw's frozen runtime valid. Finally, `Compress-Archive` the
  generated books (runs/chapter-one, runs/volume1, the full-book trial, `litharness.db*`, generated book-library
  shelves; no exemplars, no corpora, not the 8.5 GB model) plus `$A\memory-2026-09-27` to
  `$env:OneDrive\LitHarness-backups\2026-09-27-books.zip`, and record its sha256. *Verify*: `git -C $R status
  --porcelain --ignored` lists only the keep-set, `runs/` (holding `box.lock` and the junction) and `?? .agents/`.
- **B6 Cutover.** Preconditions: A5 is green, and B1 and B5 still verify. `git -C $W push origin HEAD:main`. The
  server accepts only a fast-forward; if main moved, `git -C $R fetch origin`, redo B2 and retry, never with
  force. Only after that push
  succeeds: `git -C $R fetch origin; git -C $R merge --ff-only origin/main`. *Verify*: `main` and `origin/main`
  equal the rebuild tip; `git -C $R status --porcelain` prints nothing (the new `.gitignore` covers `.agents/`);
  `python -m litharness --help` works in `$R`. Directories left holding only ignored `__pycache__/` are harmless.
- **B7 Close.** Remove our box lock and announce the end. `git -C $R worktree remove $W`; `git -C $R branch -d
  rebuild/lite import/lite`; `git -C $R push origin --delete rebuild/lite`. Memory consolidation follows (§11).

**Rollback.** Always first remove the junction with `cmd /c rmdir "$R\runs\chapter-one\read-21\draw-6"` (never
`Remove-Item`, which follows a junction into its target in PowerShell 5.1), then the empty parents it needed, then
replay the manifest in reverse with `$A\move-ignored.ps1`. Before B6 that is all, because main was never touched.
After B6, also: `git -C $R restore --source=legacy/incumbent-2026-09-27 --staged --worktree :/` (the latest
suffixed tag if B2 ran), commit "Restore the incumbent tree", push (an ordinary commit); if route (b) ran, `git -C
$R apply "$A\wip\primary-0926.patch"` and move the three untracked sources back; restore memory from
`$A\memory-2026-09-27`.

## 7. Milestones

Acceptance criteria are properties of the code. A stage that needs more than 3 draws produces a finding, not a
failed milestone.

| M | Scope | Acceptance | Net lines | You see | Calls |
|---|---|---|---|---|---|
| **M0 Cutover** | Phase A and B. Lite split into modules with its behaviour unchanged, exposed as one verb, `python -m litharness opening --brief F [--words N] [--resume]`, which writes to `$LITHARNESS_HOME`. Byte writes (CRLF fix); atomic writes; locks; Lite's `test_lite.py` ported; guards; CI; the five docs and CHECKLIST.md; plan folder frozen | legacy refs and both local-only branches on origin; manifest complete, all rows `moved`; main is the rebuild tip with history kept and no force; CI green in under 2 minutes on both jobs; suite under 3 s; runtime <=400; the six `experiments/` entries of `freeze.json` match the tree byte for byte, and `lite.py` and `benchmark.py` match `git show legacy/lite-2026-09-27:<path>`; MEMORY.md <=30 lines | runtime +400, tests +250, docs +300; 1,782 tracked files removed | a 5-line note: the tag, the archive path, the backup sha, the README link | 0 |
| **M1a Checks, offline** | `sheet.py`, `checks.py`, `tells.py`, the prompt lint, fixtures, the `check` verb | `check` on `experiments/2026-09-27-opening/lite/chapter.md` reports `rise` failed (0 status lines), `length` failed (4,069 words), `admin` inspection x4 and council x3, `cast` over 5; with a test serial whose bible gives `Elias Venn` and `Age: 26` (from `lite/plan.md:7`), `literals` reports the age missing; on `baseline/chapter-one.md` it runs and `rise` fails (its status lines are not the v1 format); Lite's `plan.md:7` line fails pitch-stage `money`; "Darren paid out rope." passes `money`; every fixture lands in its class | runtime +390, tests +350 | nothing | 0 |
| **M1b Serial core and pitch** | prompts, stages, the redraw rule, resume and receipt adoption, `new`/`next`/`status`/`redraw`/`canary`, login preflight, reconnect tolerance, version pin; the `opening` verb is deleted | offline with a fake transport: 3 failed draws exit 1 with quotes; an unchanged re-run spends nothing; a changed input opens draw 4; a kill at every stage resumes without re-spending; hand edits recorded; `final.md` hash equals the receipt. Live: canary answers NONE; the Slot pitch either passes its hard checks or exits with located quotes | runtime +230 (1,020), tests +300 | the pitch (title, listing, person, exception, first use, threat, prize, System, start sheet) as one short file. Chapter spend waits for your reply | 2-4 |
| **M2 Chapters 1-3** | `next -n 3`; the tells rewrite enabled when triggered | each stage passed its hard checks or exited 1 and was resolved by a located change; usage reported; the coordinator's hand-read residuals listed | runtime +50 (1,070), tests +80 | chapters 1-3 in one reading file with a 5-line report and any tells rewrites listed. Your verdict becomes `reads/21.md`; each item becomes a fixture or a field, then a redraw | 6-9, plus redraws |
| **M3 Chapters 4-10** (after chapters 1-3 survive your read) | no new code unless a failure is named | tokens per chapter and state size reported; every break the coordinator's between-chapter read finds (a resource spent twice, a dead or absent person back, a rank falling without cause, an ability used before it was acquired) is recorded as a fixture and resolved by a located change | about 0 | a book-grain read when you choose | 14-21 |
| **On trigger** | §4's table | a failing fixture before, passing after; budgets hold | <=60 each in the runtime; `bench.py` <=300 outside it | the redrawn chapter or the posted chapter | per item |

For scale: the incumbent's chapter 1 took 33 calls and 411,160 tokens.

## 8. Verification

- **One command**: `python -m unittest -q`, serial, stdlib only, target 3 s locally (the `time` guard fails at 15
  s). No xdist, markers, lanes or coverage floor. The unit suite is not sustained load and takes no box lock.
- **Tests**: `test_transport` (argv flags present, environment allow-list, refusal cases, reconnect tolerance,
  no-git working directory, `GIT_*` stripped); `test_files` (atomic writes, stored hash equals receipt hash on
  Windows, lock liveness and holder format, `PermissionError` retry); `test_serial` (fake-transport runs: the draw
  cap, located-in-request refusal, resume, adoption, redraw, hand edits, context caps); `test_sheet`; `test_checks`
  (every fixture's class, the lexicon loop); `test_guards`; `test_zz_time`.
- **Never tested**: prompt wording or hashes, anything a `.md` file says (the `docs` guard only counts lines), and
  experiments.
- **CI** (<=40 lines): ubuntu-latest with Python 3.13 and windows-latest with 3.11, `fetch-depth: 1`, actions
  pinned by SHA, `contents: read`, cancel-in-progress, `timeout-minutes: 5`, steps checkout, setup-python and
  unittest. There is nothing to install. Measured setup overhead is ~10 s on Ubuntu and ~28 s on Windows, so a push
  gets a result in under 2 minutes, against 10-14 minutes today. Windows stays because the box is Windows.
- **Live, opt-in, never in CI**: `python -m litharness canary` after every Codex CLI upgrade (the version pin
  enforces it).

## 9. Risks the design does not already answer

| Risk | Mitigation |
|---|---|
| The model's money prior uses up all 3 pitch draws | Exit 1 with located phrases, never a silent fourth draw. The Person field avoids "life" and "job", the cost rule is positive, ambiguous words only report. Measure the `money` hit rate with `check` on the read-21 concepts at M1a before relying on a rate |
| The combined plan-and-state call is overloaded | `plan-shape` failures and the coordinator's between-chapter read are watched through M3; the separate state call is pre-budgeted in §4 |
| A Codex thread keeps working in `$R` after cutover and pushes incumbent files back | Q1 asks you to stop it; the B0 quiet check; CLAUDE.md and AGENTS.md say the incumbent lives only at the tag |
| Continuity breaks by chapters 5-10 (§242) | The code-owned sheet, the previous chapter in full, and the M3 between-chapter read; each break becomes a fixture |
| You reject chapter 1 (no book has passed you yet) | That is the loop: locate each item in our text or the model's, apply the cheapest fix class, redraw for ~21k tokens. Never present a chapter as a success |

## 10. Decisions taken on your behalf, and questions

§1 and §3 are the decisions. `DECISIONS.md` is seeded from them. Four deserve a line here:
- **Simulated readers no longer measure the objective (§126).** They continued 4/4 on shuffled copies and preferred
  a shuffled opening of ours over The Primal Hunter 20/20. Your read, and household reads you relay (§148), is the
  gate.
- The first serial is a **fresh draw on Lite's Slot brief**, verbatim. Lite's chapter is not continued, because it
  fails v1 checks (no status lines, 4,069 words, an institutional premise).
- One chapter is one Royal Road post of **1,500 words**, flagged outside 1,200-2,000 and redrawn only below 900 or
  above 2,700 (bands scale with `--words`).
- **Export, the bench and the exemplar shelf wait for you to ask** (§4). The first two would be spend or code
  with no consumer yet.

Questions only you can answer:
1. **Blocking Phase B only.** A Codex app thread working in this checkout committed and pushed to main three times
   today (955f6f5, f5b26c0, 40f58a2), and it holds uncommitted work: a `tools/produce.py` start/status/resume
   runner, job-recovery changes and `why --html` (13 modified files, 3 new). A Claude session cannot reach it. In
   the Codex app, please have that thread push its work to a `wip/` branch, or tell me I may archive it myself
   (B1 route b: a hash-verified copy pushed as `wip/codex-0926`). In either case, stop or archive that thread
   before Phase B, so that it cannot push incumbent files back after cutover.
2. **Non-blocking.** May the archived 8.5 GB downloaded model (`runs/jev-verification-20260919`) be deleted later,
   and may the 32 stale `litharness-cover` trust entries in `~/.codex/config.toml` be pruned? Both stay as they are
   until you say.

## 11. After cutover

**Docs** (rewritten when they go stale, never appended; line caps in §5):
- README: what LitHarness is, requirements, the verbs and one example flow, exit codes, the data root, the Royal
  Road AI-Generated tag, the OneDrive backup command, and where the incumbent lives.
- AGENTS.md: the loop (you read; each item is located in our text or the model's; one fixture plus one check or
  field; redraw); the admission and deletion rules; the budgets; test rules; the experiment rule (frozen protocol,
  receipts and report under `experiments/<date>-<name>/`, never imported, code deleted when concluded); the
  coordinator's hand read against CHECKLIST.md (residuals only, never delegated); git flow (one writer at a time,
  a topic branch that lives under a day, `--ff-only` to main, push, remove the worktree; `legacy/*` refs are
  permanent; never `--force`).
- CLAUDE.md: read AGENTS.md; every model call goes through `litharness.transport`; run `canary` after a CLI
  upgrade; the box rules (process check plus `runs/box.lock`, one sustained job, kill by PID and verify); data
  outside the tree and third-party prose never inside it; your read is the only gate; subagents on Opus with capped
  fan-out, logging what was dropped; push after every green commit.
- LEARNINGS.md: the §2 lessons; the dead-instrument table (22 static proxies, pick-a-side verdicts, persona panels,
  anticipation, CDG); judge-bias and saturation numbers; the defect catalogue (13 families with their read
  numbers); market reference numbers (§155, §202) as descriptions, not bars; the costed-reader result (the one
  mechanism that replicated, at about $50 and 2 hours per arm); pointers into the legacy tag.
- DECISIONS.md: seeded from §10; entries of at most 5 lines keyed `YYYY-MM-DD slug`; superseded entries are
  rewritten.

**Memory consolidation** (same day; B4's copy makes it reversible). Move the ~52 notes that cite incumbent paths
into `memory/legacy/` unchanged. Notes that need new wording (product objective, LLM-only regime, numbers go up,
house rules) keep their originals in `legacy/` and get new files: the objective note keeps the audience definition
and the no-human-data rule and records that the simulated-reader channel closed with the rebuild; house rules
become the transport rule, the unittest command and no ledger. MEMORY.md is rewritten at 30 lines or fewer. Its
first line names the rebuild date, the legacy tag and the archive path, followed by about 18 active notes and a new
`rebuild-state` note.

**Lite's repository**: its history reaches origin through main and `legacy/lite-2026-09-27`, and its experiment
folder is frozen in the tree. `C:\DEV\LitHarnessLite` stays as it is; removing it is your call whenever you like.
