> Agent-written digest, 2026-09-27: one of seven read-only surveys behind ../PLAN.md.
> Working notes, not evidence in themselves; each claim points at a primary source
> (a path and line, a commit, or a section of plan/stage-0-decisions.md at legacy/incumbent-2026-09-27).

# surface: Operator-facing surface and the books (commands, export/Royal Road, artifacts, unused features)

The operator works in one loop: a brief, then a cheap overview or listing, then a chapter-one read, then a verdict in chat. There are 20 recorded reads (plan/reader-read-2..20.md) and almost all are chapter one or the listing. Only one read was at book grain: volume 1, which he called "a disaster". He has never written in a shelf NOTES.md (all 42 are the identical template) and no book has ever passed him.

The incumbent has five overlapping "make a book" runners (~6k lines: produce.py, chapter_one.py, volume_run.py, ab_redraw.py, dashboard.py). They sit on a 7,033-line cli.py with about 45 verbs, and production uses about 10 of them. produce.py, the newest start/status/resume wrapper, is still uncommitted (dated 09-26).

Cost:
- Heavy chapter one: 33 calls / 411k tokens.
- A 24-chapter book: 129 calls / 3.59M tokens.
- Lite: 2 calls / 16k tokens.

Operator features that were built and never used:
- release queue: 0 staged rows across 70 DBs
- covers
- dashboard: a casting UI, and the operator called casting "micromanagement"
- roster/recruit/revoice: revoice never drew
- MCP server: dogfooded once, and its default store holds no book
- 50-chapter volumes: no book is longer than 24 chapters

In the 157 commits since 09-10 none of these changed except mcp_server. 89 of those commits are Register/Record research commits, research/ grew by +230k lines, and src/ grew by only about +4k.

The Royal Road export rules (§240) are worth carrying forward: `<p>`, `<hr>`, `<br>`, no title heading, a clean-paste .txt, and `currentColor`-only tables. They have never been checked by a real paste.

Length does not match yet. The operator's target is about 1,500 words per chapter (the RR median is 2,074). Lite's 4,069-word chapter has 4 sections of about 1k words, split by `***`.

No existing book should be continued. The only chapter with a positive signal is Lite's *One Slot, Open Water*, and continuing it is the REPORT's own next step.

Wipe notes:
- The repo is PUBLIC.
- runs/ (12 GB, of which jev-verification is 8.7 GB) and book-library/ (124 MB, including 4 folders of copyrighted commercial chapter-1 exemplars) are gitignored. A git wipe will not archive them, and they must never enter the new repo.
- .mcp.json, the skills and the workflows point at code the wipe removes. Replace them in the same change.

## Learnings
- [high] The operator's real surface is a read loop: brief -> cheap overview/listing -> chapter 1 -> verdict in chat. He reads almost only openings and never uses the on-disk notes channel.
  EVIDENCE: 20 operator reads recorded (plan/reader-read-2.md..reader-read-20.md). Titles show chapter 1 or the listing in nearly every one; the only book-grain read is volume 1 (memory operator-read-volume1-2026-09-07: 'it looks to be a disaster'). All 42 book-library/*/NOTES.md are byte-identical to the template (md5 ed7f96eaa7370baf24cb0761677526a8). Memory avoid-micromanagement-decisions (08-28): 'let's generate an overview first, not overspend on chapters'.
  IMPLICATION: Design for one chapter at a time plus a single reading file a session can send. Keep a cheap pitch/overview step before paying for chapters. Capture his reply as a plain read file, not a shelf template.
- [high] Operator entry points are fragmented and far larger than the path production actually uses.
  EVIDENCE: tools/chapter_one.py 2,656 lines (added 57a13f8, 09-24), tools/ab_redraw.py 1,247, tools/dashboard.py 934, tools/volume_run.py 707, tools/produce.py 444 (untracked, 09-26): 5,988 lines of runners. src/litharness/cli.py is 7,033 lines with 65 add_parser calls (~45 top-level verbs). produce.py:327-380 and chapter_one.py:161-171 use only concept, listing, new, architect seed, world check/accept, tick, extend and export.
  IMPLICATION: One entry point with about 6 verbs (new, next, status, export, compare, plus optional note). Resume should be re-running the same command, not a separate queue/tick surface.
- [high] Heavy cost per chapter is an order of magnitude above Lite. The gated chapter-one lane spent 6 draws without producing a gated chapter.
  EVIDENCE: REPORT.md:143-150: heavy chapter 1 is 33 calls / 411,160 tokens / 33m48s (chapter stage alone 16 calls / 129,661 tokens); Lite is 2 calls / 15,904 tokens / 4m09s. full-book-trial-20260919/RESULTS.md:11-12: 24 chapters took 129 calls, 3,587,274 tokens, 13:32-15:38 UTC. runs/competitive-analysis/usefulness-assessment-2026-09-26.md:46: one heavy scene request is 99,679 chars with 229 source entries. runs/chapter-one/read-21/ledger.jsonl: 6 draws 13:59-15:39 UTC on 09-24 (4 concept-gate fails, 1 listing fail), and draw-6 has no GATE-chapter.md.
  IMPLICATION: Set per-chapter call/token ceilings near Lite's (a few calls per chapter). Print spend in status. Don't rebuild multi-checkpoint gates.
- [high] The coordinator gate misjudges what decides whether the operator reads on, so gates should not sit in the operator path.
  EVIDENCE: plan/reader-read-20.md:29-33: 'The gate was right on structure and wrong on all three things that decide whether he reads on' (the draw had passed C1-C4, L1-L4, W1-W3, H1-H8). Memory avoid-micromanagement-decisions (08-30): the gate was 'FIVE-for-five miscalibrated on sentence feel vs the operator's reads'.
  IMPLICATION: The operator read is the gate. Automated checks (brief literals, money/admin words, digits) should be inert reports next to the chapter, never pass/fail stages.
- [high] The Royal Road export format is well specified and cheap to rebuild, but it has never been checked by a real paste and nothing has ever been posted.
  EVIDENCE: stage-0 §240 (plan/stage-0-decisions.md:24883-24937); src/litharness/application/library.py:348-437 (_units, paste_fragment, paste_plain). Rules: the HTML goes in through the source-code button; <p> per paragraph; <hr> for breaks (any 3+ of *-_~= collapsed, never opening or closing a chapter); <br> for single newlines inside a block; escape only < > &; quotes written literally; no title heading (RR has its own title field); status panels as <table> with inline border/width/text-align/padding/font-* and currentColor as the only colour; a .txt with blank-line paragraphs and '* * *' for clean paste. library.py:429-430: 'this HTML pastes correctly' is not verified by pasting. §240:24904: 0 staged release rows across 70 DBs.
  IMPLICATION: Port these rules as a ~50-line export function with the §240 test cases. The operator's first real paste is the acceptance test, and the .txt fallback should be kept.
- [high] Lite's chapter shape needs export-specific handling and does not match the operator's length target.
  EVIDENCE: Lite lite.py DRAFT prompt: 'one title heading and optional scene breaks'. experiments/2026-09-27-opening/lite/chapter.md has '# One Slot, Open Water' at line 1, '***' at lines 151/371/607 (4 sections of ~1k words) and 21 *italic* spans, 4,069 words. Memory royalroad-chapter-length-target (08-20): about 1,500 words per chapter (sample 1,502 words / 8,329 chars / 21 paragraphs; RR median 2,074), with the condition 'export at it only once a book is good enough'. Heavy chapters delivered about 2,000-2,230 words (The Last Anchorage 53,520 words / 24 chapters; volume 1 25,901 / 12). The heavy DraftPolicy max_chars=8000 (src/litharness/domain/draft.py:47) would refuse a 1,500-word chapter at 5.55 chars/word.
  IMPLICATION: The exporter lifts the title into a separate field and maps *** to <hr>. The italics policy has to be decided: §240:24928-24930 stripped emphasis as a model tic. Either default to about 2,000 words or export one 4k Lite chapter as two RR posts split at a ***. Don't add a char ceiling that refuses the target.
- [high] Most of the operator-facing features were built but never used, or were used once and abandoned.
  EVIDENCE: Release queue (§221, migration 039, application/release.py 153 lines): 0 staged rows (§240), and no release/ folder on any of 47 shelves. Covers (application/covers.py 549 lines): 86 PNGs on 13 shelves, 08-26 to 09-14. Commit d9cce6a: generation was silently broken because 'no cover had been generated since 2026-08-26 16:30', and the operator stopped covers for volume 1. Dashboard (tools/dashboard.py 934 lines + dashboard.cmd, §149, 08-28) is roster accept/refuse, which the operator called 'micromanagement' (memory 08-28); last touched 09-03 for mypy only. Roster/recruit/revoice (roster.py 579, recruiter.py 321, revoice.py 280, migrations 035-037): 12 dossiers minted once on 08-28; revoice's paid arm 'registered, unscheduled' (memory dossier-voice-direction). MCP server (mcp_server.py 2,059 lines): dogfooded once on 09-07 for $1.25, and .mcp.json defaults to root litharness.db (696 KB, last written 09-03), which memory says holds no book. Volumes (50-chapter windows): the longest book is 24 chapters. Since 09-10, git log shows no commit touching covers/library/export/release/roster/revoice/dashboard; mcp_server.py is touched 4 times.
  IMPLICATION: Leave all of these out of v1. Add one back only when a concrete operator task needs it. Covers could later be a single standalone script.
- [high] Recent development effort went to research registration rather than the product.
  EVIDENCE: git log --since=2026-09-10: 157 commits, 47 starting 'Record' and 42 'Register'. numstat: research/ +230,523 lines over 574 file touches; src/ about +3,963 (application +2,469, domain +736, providers +329, cli +310, mcp +114, adapters +5); tests +17,168; tools +3,051. plan/stage-0-decisions.md is 2,001,354 bytes.
  IMPLICATION: Keep research and experiments out of the product tree (a separate experiments/ folder, like Lite's), with no per-change registration ledger.
- [medium] No existing book should be continued by the new system. The only chapter with a positive signal is Lite's.
  EVIDENCE: Memory 08-28: 'i haven't liked any book yet'. Volume 1 *The Order Stays Open*: 'disaster' (09-07). *The Last Anchorage* (24 ch, 53,520 words): coordinator GATE FAIL, 'Not offered to the operator' (book-library/the-last-anchorage/GATE.md). *A Thousand Skills from Home*: 'I would probably stop reading around overview/ beginning' (plan/reader-read-20.md:25). read-21 draw-6 had no chapter gate and lost both blinded reads to Lite (REPORT.md:83). REPORT.md:169-171 names continuing the Lite chapter with a compact canon file as next step 2.
  IMPLICATION: The first serial of the new system should continue *One Slot, Open Water*, with its brief/plan/chapter copied into a new serial folder (the frozen experiment stays unedited). Don't migrate SQLite books.
- [high] Local artifacts are large, gitignored, and partly copyrighted, so a git wipe neither archives nor removes them.
  EVIDENCE: .gitignore:11 (*.db), :14 (exports/), :21 (output/), :66 (book-library*/), :82 (/runs/). du: runs/ 12 GB (runs/jev-verification-20260919 8.7 GB; cost-that-bites-milder 454 MB; model-tiers 435 MB; full-book-trial 126 MB; chapter-one 81 MB; volume1 42 MB; roster 1.5 MB), book-library 124 MB, output 2.3 MB, exports 1.9 MB. book-library/{PrimalHunter,DefianceOfTheFall,RandidlyGhosthound,TheGam3} each hold Chapter1.txt + blurb.txt of commercial books (exemplar shelf; book-library/exemplars.json). The repo is PUBLIC (gh: visibility PUBLIC, diskUsage 62,751 KB). Lite's evidence cites runs/chapter-one/read-21/draw-6 as the heavy baseline source (experiments/2026-09-27-opening/engineering.json).
  IMPLICATION: Before the wipe, move or zip runs/ and book-library/ to an archive outside the repo; the 09-22 precedent is OneDrive\LitHarness-backups with a sha256. Never use git clean -x. The new .gitignore should exclude books and exemplars. Keep read-21/draw-6 where Lite's evidence points, or record where it moved.
- [high] There is uncommitted in-flight work, and several session-facing configs will break when src/ is removed.
  EVIDENCE: git status: 13 modified files (+434/-167: conductor, sqlite_jobs, sqlite_store, cli, README, operator-guide...) plus untracked tools/produce.py, tests/test_produce.py and src/litharness/application/scene_inspection.py, mtimes 2026-09-26 15:30-19:23. main == origin/main at 40f58a2. Tracked session config: .mcp.json (auto-starts litharness-mcp), .claude/skills/debug-book, .claude/skills/litharness-mcp, .claude/workflows/volume-arc-review.js, .github/workflows/ci.yml. The untracked .agents/ is a Codex-app import (memory next-steps: don't commit, don't delete).
  IMPLICATION: Before wiping, preserve the in-flight diff (an archive branch or patch) and tag the heavy tree. In the same change, replace .mcp.json, skills, workflows, CI, CLAUDE.md and AGENTS.md. Then update the memory index, whose links point at plan/ files that will exist only in the archive tag.
- [medium] The 09-08 standalone clean start was retired within a day because its single-call chapter kept the money/number register. That is a precedent for how the Lite could lose support.
  EVIDENCE: docs/clean-start-baseline-20260908.md:3-7 and :41-63 ('The Debt of Salt': ledger counts, account/credit framing, capacity arithmetic contradictions); retired at 917ce1a (2026-09-09). Lite differs in using Codex gpt-6-astra, a plan+draft pair and a matched blinded comparison (REPORT.md:48-51). Crude count on the Lite chapter: 0 hits for debt/ledger/rent/contract/licen/account/credit, 1 digit, vs 8 digits in the heavy baseline.
  IMPLICATION: Attach an inert register report (money/admin words, first-hit position, digits, brief literals such as stated age) to every generated chapter, so a regression is visible before the operator reads it.

## Carry forward
- (code) Royal Road paste rendering rules: resolve units once; breaks to <hr> or '* * *', collapsed and never at the chapter edges; <br> for single newlines; escape only < > &; no title heading; status table with currentColor only; .txt clean-paste twin — This is the one export format the operator asked for (§240), and it is defined by the platform's own guides [src/litharness/application/library.py:348-437 (+ src/litharness/application/statusline.py, 157 lines, only if system panels are kept)] ~60 lines rewritten from ~250
- (test) The §240 regression cases: break line as rule, breaks never doubled or at edges, markdown markers, line-structured blocks, literal quotes, conservative tag subset, panel style properties — Cheap, deterministic protection for the export [plan/stage-0-decisions.md:24920-24926 (test names in tests/test_library*.py)] ~8 small tests
- (idea) Run-folder mechanics: refuse an existing directory; run.json manifest saved atomically with fsync; OS file lock per run; sha256 of saved inputs checked on resume; attempt dirs never reused; exit codes 0 answered / 1 needs a person / 2 fault; resume may raise the chapter target but never lower it; status opens read-only and prints the next command to run — This is what worked in produce.py and Lite for interrupt/resume without a queue [tools/produce.py:41-136, 287-317, 393-440; C:/DEV/LitHarnessLite/lite.py (--resume)] ~80 lines
- (procedure) Two-chapter comparison protocol: blinded A/B with swapped order, an identical-text null, a paragraph-reorder damage control, verbatim quote grounding, and a rubric fixed before generation — This produced the only comparative evidence the rebuild rests on and gives a diagnostic 'compare' verb [C:/DEV/LitHarnessLite/benchmark.py; C:/DEV/LitHarnessLite/experiments/2026-09-27-opening/PROTOCOL.md] ~150 lines
- (doc) The operator's enumerated reading items (exception belongs to one person, no debt/ledger/admin register, fresh premise, numbers go up / sheet renders, early progression, relatable prior life, attention economy, popcorn tone, hook not list-of-facts, no odd diction) — These condense 20 reads into a checklist a session can use before sending a chapter [tools/chapter_one_items.json; plan/reader-read-20.md; book-library/the-last-anchorage/GATE.md (table)] 1 page
- (data) The operator read harvests themselves (verbatim verdicts and located defects) — The only ground-truth signal the project has [plan/reader-read-2.md .. plan/reader-read-20.md] 13 files, ~160 KB
- (idea) An inert register report: rate per 1k words, count in the opening window, and words-to-first-hit for household money, admin and frame word families; digit count; brief-literal presence — Cheap, visible warning for the defect that retired the 09-08 clean start and failed read 20 [research/quality-measurement/register_report.py (1,467 lines; keep the word lists and the first-hit idea only)] ~40 lines
- (data) Chapter length facts: operator target ~1,500 words; RR median 2,074; measured sample 1,502 words / 21 paragraphs — Sets the default --words and export split decision [C:/Users/artem/.claude/projects/C--DEV-LitHarness/memory/royalroad-chapter-length-target.md] 3 numbers
- (procedure) Off-box book backup procedure: zip the run folder to OneDrive\LitHarness-backups with a recorded sha256 — Books are gitignored and the public repo must not hold them; the box has a history of hard shutdowns [C:/Users/artem/.claude/projects/C--DEV-LitHarness/memory/next-steps-assessment-2026-09-22.md] 1 command

## Drop
- Release queue (release stage/approve/record-posted/show/withdraw), domain/release.py, migration 039 — 0 staged rows across 70 DBs and no release/ folder on any shelf; nothing is ever posted [src/litharness/application/release.py]
- Cover generation (`litharness cover`, covers.py) — Cosmetic; broke silently for hours on 08-28 (d9cce6a) with nobody noticing; the operator stopped covers for volume 1; not needed until a book passes him [src/litharness/application/covers.py]
- Operator dashboard (tools/dashboard.py, dashboard.cmd) — A roster accept/refuse UI for casting decisions the operator called micromanagement; unchanged since 09-03 apart from mypy [tools/dashboard.py]
- Writer roster, recruit and revoice (roster.py, recruiter.py, revoice.py, migrations 035-037, runs/roster/roster.db) — Casting is micromanagement per the operator; revoice never drew; Lite won with no writer dossier [src/litharness/application/roster.py]
- litharness-mcp server, .mcp.json, and the litharness-mcp and debug-book skills — 2,059 lines serving a store with no book by default; dogfooded once; plain text run folders are directly readable by any session [src/litharness/mcp_server.py]
- Library volumes (50-chapter windows), the shelf index README, .book.json slug ownership, and the NOTES.md template — No book exceeds 24 chapters; the operator never wrote a NOTES.md (42/42 template) [src/litharness/application/library.py:482-760]
- Operator runners: chapter_one.py, volume_run.py, ab_redraw.py, produce.py, run-loop.ps1, serial-pilot-setup.ps1, schedule-library.ps1 — About 6k lines of overlapping wrappers around the heavy CLI, replaced by one entry point [tools/]
- Queue and recovery operator verbs (tick, jobs, revive, enqueue, directive(s), replan, revert-plan, revert, exceptions, resolve, world declare/accept, architect seed/grow) — They exist to run a job queue and world graph the rebuild does not port (REPORT.md:175) [src/litharness/cli.py]
- Simulated-reader operator verbs (readers, reader-mechanism, reader-evidence-audit, --reader-checkpoints) — Experimental and inert by design; they cannot steer or certify (operator-guide.md:889-963) [src/litharness/application/readers.py]

## Risks
- The wipe loses uncommitted in-flight work: 13 modified files plus produce.py, test_produce.py and scene_inspection.py, dated 09-26 => Commit it to an archive branch, or save it as a patch under the archive tag, before removing anything. Push the branch (never --force).
- A careless cleanup (git clean -fdx or deleting the folder) destroys 12 GB of gitignored runs/ and book-library/, including the only full book and Lite's heavy-baseline source => Move or zip runs/, book-library/, exports/, output/ and *.db to C:/DEV/LitHarness-archive or OneDrive with sha256 before the wipe. Record the new location of runs/chapter-one/read-21/draw-6 cited by Lite's engineering.json.
- Copyrighted exemplar chapters (PrimalHunter, DefianceOfTheFall, RandidlyGhosthound, TheGam3) or generated books end up in the PUBLIC repo => Keep book folders outside the repo or gitignored from the first commit, and add a check that refuses committing book text.
- Sessions break because .mcp.json auto-starts a removed litharness-mcp, skills and workflows reference deleted verbs, and CLAUDE.md/AGENTS.md and the memory index point at deleted paths => Replace .mcp.json, .claude/skills, .claude/workflows, CI, CLAUDE.md and AGENTS.md in the wipe commit. Update MEMORY.md to point at the archive tag for historical plan/ledger files.
- The Royal Road HTML has never been verified by a real paste, so the first real paste could mangle formatting => Keep the .txt clean-paste twin, and treat the operator's first paste as the acceptance check before adding features.
- The rebuild is reverted like the 09-08 clean start if an early chapter shows the money/numbers register => Keep the heavy repo reachable via a tag. Attach an inert register report to every chapter. Make the first serial a short continuation test before the operator read.
- Lite has no transactional state, so a crash between the response and the manifest leaves an ambiguous run (Lite README) => Use atomic tmp+fsync+replace writes and content digests, as in produce.py:41-48 and 122-136. Resume re-derives the stage state from files.

## Numbers
- 20 operator reads recorded, almost all at chapter 1/listing (plan/reader-read-2..20.md); 1 book-grain read (volume 1, 'disaster', 09-07)
- 42/42 book-library NOTES.md byte-identical to the template (md5 ed7f96ea...): the operator never used it
- book-library: 47 shelves (43 generated + 4 commercial exemplar folders), 124 MB; runs/ 12 GB (jev-verification-20260919 8.7 GB); exports 1.9 MB; output 2.3 MB; litharness.db 696 KB (last write 09-03)
- cli.py 7,033 lines, 65 add_parser calls (~45 top-level verbs); production path uses ~10
- Operator runners in tools/: 5,988 lines (chapter_one 2,656, ab_redraw 1,247, dashboard 934, volume_run 707, produce 444)
- Tracked src/ 65,906 lines; tracked tests/ 100,152 lines; plan/stage-0-decisions.md 2,001,354 bytes; PLAN.md 192,992 bytes; RESEARCH.md 97,926 bytes
- Since 2026-09-10: 157 commits (47 'Record', 42 'Register'); research/ +230,523 lines vs src/ about +3,963, tests +17,168, tools +3,051 (git log --numstat)
- Heavy chapter 1: 33 calls, 411,160 tokens, 33m48s; chapter stage 16 calls, 129,661 tokens; Lite 2 calls, 15,904 tokens, 4m09s (REPORT.md:143-150)
- Full 24-chapter book: 129 calls, 3,587,274 tokens, 13:32-15:38 UTC 09-19, 53,520 words, about 2,230 words/chapter (full-book-trial-20260919/RESULTS.md:11-12)
- Heavy scene request: 99,679 characters, 229 source entries (runs/competitive-analysis/usefulness-assessment-2026-09-26.md:46)
- Chapter-one lane 09-24: 6 draws in 1h40m, 4 concept-gate fails, 1 listing fail, no chapter gate recorded (runs/chapter-one/read-21/ledger.jsonl)
- Volume 1: 24 scenes / 12 chapters / 25,901 words / $38 / 2h20m (memory volume1-run-state)
- RR length target about 1,500 words (sample 1,502 words, 8,329 chars, 21 paragraphs); RR median chapter 2,074 words (memory royalroad-chapter-length-target)
- Lite chapter: 4,069 words (+2.7% vs 3,962 target), 1 title heading, 3 '***' breaks, 21 markdown italic spans
- Heavy DraftPolicy max_chars 8000, target_words 900 (src/litharness/domain/draft.py:47,84)
- Release queue: 0 staged rows across 70 DBs (§240, 09-05); 0 release/ folders on 47 shelves
- Covers: 86 PNGs on 13 shelves, 08-26..09-14
- MCP dogfood: 5 tasks, $1.25, 09-07 (memory agent-surface-mcp-server)
- GitHub repo PUBLIC, diskUsage 62,751 KB; LitHarnessLite has no remote
- In-flight uncommitted: 13 files +434/-167, plus 3 untracked source/test files (mtime 2026-09-26)

## Open questions
- Should the wipe keep git history (archive tag + a new commit on main) or start an orphan branch or new repo? Should the repo stay PUBLIC?
- Where should the 12 GB of local artifacts go (C:/DEV/LitHarness-archive vs a OneDrive zip)? Can runs/jev-verification-20260919 (8.7 GB) be deleted rather than archived?
- Should the uncommitted produce.py / queued-only-tick / scene-inspection work be committed to an archive branch or discarded?
- Is continuing Lite's *One Slot, Open Water* the first serial of the new system, and has the operator read that chapter itself or only the REPORT?
- Chapter length: about 2,000-word chapters (RR median), about 1,500 (the operator's number), or 4,000-word generations split into two RR posts at a ***?
- Emphasis in the export: render *italics* as <em>, or keep §240/§180's strip as a model tic?
- Does the operator want a cheap pitch/overview stage before chapter spend (his 08-28 rule)? Lite has none.
- Provider: Codex-only like Lite, or keep a one-setting Claude/Codex switch? Does the claude -p isolation rule (§258) carry over?
- Which external consumers break on the wipe: litharness-contracts dependency, ContinuityEvaluation, MirrorBench, the LRC repo, and the .agents/ Codex import?
- Should the read harvests (plan/reader-read-*.md) be copied into the new repo as docs, or referenced from the archive tag?
