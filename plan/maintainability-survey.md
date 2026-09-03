# Maintainability survey

**Measured 2026-09-03 on `main` at d88114b** by `tools/maintainability_survey.py`; every table
below names the subcommand that regenerates it, and a later session re-runs the command rather
than trusting this page (`PLAN.md` header: the number the project reports about itself is the
one to distrust first). This is deliverable 1 of `plan/handoff-maintainability.md`; the map
it feeds is `docs/system-model.md`, and the changes it licenses are recorded in the stage-0
ledger as they land. It replaces nothing: `CONTRIBUTING.md` still owns the dependency
direction, the suite owns the test count, and the ledger owns decisions.

Two measurements needed the box to itself and were taken in the session's box window after
the survey was first written; they are in §3 and §7, marked with the run they came from.

## 1. Module size and shape

`uv run python tools/maintainability_survey.py sizes --min-lines 800`. Lines are physical
lines; `prose` is the share of docstring and comment-only lines; `public` and `private`
count module-level names; `__all__` is that list's length where the module has one.

| module | lines | code | docstring | comment | prose | public | private | __all__ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cli.py | 6762 | 5103 | 702 | 579 | 19% | 58 | 50 |  |
| domain/extraction.py | 2608 | 1277 | 984 | 168 | 44% | 58 | 24 | 49 |
| domain/gamesystem.py | 2608 | 1522 | 662 | 215 | 34% | 51 | 21 | 49 |
| adapters/sqlite_store.py | 2423 | 1705 | 442 | 117 | 23% | 4 | 6 |  |
| domain/worlds.py | 2045 | 1063 | 435 | 346 | 38% | 102 | 11 | 102 |
| application/planner.py | 1483 | 775 | 237 | 422 | 44% | 8 | 5 | 8 |
| application/outline.py | 1410 | 931 | 236 | 184 | 30% | 13 | 7 | 12 |
| application/handlers.py | 1290 | 772 | 194 | 260 | 35% | 8 | 6 | 3 |
| application/readers.py | 985 | 626 | 167 | 112 | 28% | 32 | 4 | 30 |
| application/editorial.py | 905 | 841 | 9 | 0 | 1% | 18 | 11 | 17 |
| application/repair.py | 877 | 745 | 36 | 42 | 9% | 17 | 5 | 14 |
| application/library.py | 874 | 545 | 160 | 77 | 27% | 24 | 15 | 24 |
| domain/context.py | 862 | 544 | 100 | 160 | 30% | 20 | 3 | 19 |
| domain/integrity.py | 813 | 359 | 272 | 118 | 48% | 22 | 6 | 20 |
| domain/house.py | 803 | 81 | 118 | 590 | 88% | 8 | 0 |  |

95 modules, 52232 lines: 31920 code, 16102 docstring or comment (31%), 4210 blank.
The five largest hold 16446 lines (31% of the package).

**What the five largest hold.** Section markers (`# --- title ---`) and top-level definitions
are listed by `sections --defs`; the reading below is of the code, with line numbers at
d88114b.

- `cli.py` has no section markers, 90 top-level functions, and 47 `add_parser` calls under
  `build_parser`. It is the composition root and every `cmd_*` is a subcommand handler; the
  private helpers `_store`, `_now` and `_stamp` are shared by 26 to 40 handlers each, and
  everything else is used by one or two. It holds two subjects that are not command plumbing:
  the listing loop's constants (`LISTING_COORDINATOR_CEILING`, the one market-derived number
  under `src/`, and the two bounded redraw counts) and the prompt inspector
  (`_prompt_pressure`, `_prompt_row`, `_stored_scene_prompt`). It is not a candidate for a
  seam split under this brief: a handler per subcommand is one subject, and the map points at
  the two constants instead.
- `domain/extraction.py` has no section markers and holds five subjects in sequence, as the
  generality track appended them: the sheet model and its declaration readers
  (`MalformedSheet` through `impossible_fields`, lines 130 to 978, with `render_status_line`
  closing it), the graph-line declaration (`LABEL_WORDS` through `graph_line_for`, 553 to
  751, interleaved with the sheet readers), the writer-facing example lines
  (`progression_target` through `speaks_system_voice`, 1020 to 1267, and
  `system_voice_example` at 1978), subjects and positions (`REGISTRY_VERSION` through
  `stated_position`, 1269 to 1460), extraction proper (`record_id_for` through
  `_already_canon`, 1462 to 1923), the snapshot fold (`_folds_into` through
  `_stands_before`, 2011 to 2203), and the move vocabulary (`Movable` through
  `offered_line`, 2205 to the end). `__all__` sits at line 1925 and the nine public names
  defined after it (`FIELD_KINDS`, `MAX_SUFFIX`, `has_story_vocabulary`,
  `impossible_fields`, `progression_target`, `render_status_line`, `speaks_system_voice`,
  `stated_position`, `system_voice_example`) are not in it, which is the visible trace of
  the appending.
- `domain/gamesystem.py` is marked into eight sections (the vocabulary, what a draw must be,
  the definition, one position in it, drawing a system, advancing a sheet, writing it down,
  reading it back); the cross-section matrix is in §7. Two public names (`LABEL_CHARS`,
  `offered_options`) are outside `__all__`.
- `adapters/sqlite_store.py` is the persistence facade: four public names, the rest are
  `SqliteStore`'s methods delegating to the capability repositories beside it, as
  `CONTRIBUTING.md` asks.
- `domain/worlds.py` is marked into thirteen sections: ten of vocabulary constants (102
  public names, most of them predicates), then the readers, the counters the measurement
  side reads, and the projection. The constants are the hub every later section references,
  and the readers, counters and projection reference each other little (`sections --matrix`
  on it: ten references from the counters to the readers, ten from the projection to the
  readers, one from the counters to the projection).
- `application/planner.py` is 44% prose with eight public names; `render_prompt` alone runs
  from line 269 to 659. One subject (the scene prompt and the plan selector), no seam.

Across the package the docstring-or-comment share is 31%. `domain/house.py` is 88% prose by
design (a rules essay with three constants); `application/editorial.py`, `domain/salience.py`,
`adapters/sqlite_plans.py` and `adapters/sqlite_audience.py` carry under 5%.

## 2. The import graph

`uv run python tools/maintainability_survey.py imports --tests`, resolving imports exactly as
`tests/test_architecture.py::_imports` does.

#### Layer edges (source layer -> target layer, count of module edges)

| from | to | edges |
| --- | --- | --- |
| ('application', 'domain') | 203 |
| ('domain', 'domain') | 84 |
| ('application', 'application') | 57 |
| ('entrypoint', 'domain') | 35 |
| ('adapters', 'domain') | 31 |
| ('entrypoint', 'application') | 27 |
| ('adapters', 'adapters') | 13 |
| ('providers', 'providers') | 7 |
| ('entrypoint', 'adapters') | 4 |
| ('providers', 'domain') | 3 |
| ('entrypoint', 'providers') | 2 |
| ('entrypoint', 'entrypoint') | 1 |

#### Stated directions (CONTRIBUTING.md and the maintainability brief)

| rule | holds |
| --- | --- |
| domain never imports application | yes |
| extraction imports gamesystem | yes |
| gamesystem never imports extraction | yes |
| genre imports extraction | yes |

#### Domain modules by import depth (level 0 imports no other domain module)

| level | modules |
| --- | --- |
| 0 | budget, events, failures, generation, house, litharness.domain, plan_refinement, plans, position, promises, rivals, staging, state, tells, text |
| 1 | directives, editorial, exceptions, jobs, nodes, reviser, voice, worlds |
| 2 | characters, directors, gamesystem, revision |
| 3 | beats, extraction, patch, writers |
| 4 | context, draft, findings, genre, propagation, schema_words, serials, world_brief |
| 5 | policy, salience |
| 6 | integrity, progression |

#### Domain modules: what each imports inside the domain, and who imports it

| module | out | imports | in | imported by (src) |
| --- | --- | --- | --- | --- |
| events | 0 | - | 29 | adapters.sqlite_audience, adapters.sqlite_plans, adapters.sqlite_store, application.conductor, application.directive_planner, application.director, application.editorial, application.evaluation, application.handlers, application.narrative_planner, application.outline, application.plan_refinement, application.planner, application.policy_events, application.ports, application.repair, application.summarize, cli, domain.directives, domain.editorial, domain.exceptions, domain.extraction, domain.findings, domain.gamesystem, domain.jobs, domain.policy, domain.reviser, domain.salience, domain.worlds |
| generation | 0 | - | 21 | application.concept, application.director, application.editorial, application.handlers, application.narrative_planner, application.outline, application.overview, application.ports, application.readers, application.recruiter, application.repair, application.reviser, application.revoice, application.summarize, application.tells_pass, application.titles, application.world_agent, cli, domain.policy, providers.base, providers.registry |
| nodes | 1 | text | 18 | adapters.sqlite_store, application.director, application.editorial, application.evaluation, application.export, application.handlers, application.library, application.model_context, application.outline, application.readers, application.repair, application.summarize, cli, domain.beats, domain.context, domain.draft, domain.patch, domain.revision |
| policy | 4 | draft, events, generation, patch | 18 | adapters.sqlite_audience, adapters.sqlite_plans, adapters.sqlite_roster, adapters.sqlite_store, application.conductor, application.directive_planner, application.editorial, application.exemplars, application.handlers, application.narrative_planner, application.outline, application.plan_refinement, application.policy_events, application.ports, application.repair, cli, domain.integrity, domain.progression |
| revision | 2 | nodes, position | 18 | adapters.sqlite_store, application.director, application.editorial, application.evaluation, application.handlers, application.model_context, application.planner, application.ports, application.readers, application.repair, cli, domain.beats, domain.context, domain.draft, domain.patch, domain.propagation, domain.salience, domain.serials |
| state | 0 | - | 18 | adapters.sqlite_store, application.model_context, application.outline, application.planner, application.repair, application.summarize, application.world, cli, domain.context, domain.extraction, domain.gamesystem, domain.genre, domain.integrity, domain.progression, domain.propagation, domain.salience, domain.world_brief, domain.worlds |
| text | 0 | - | 18 | application.director, application.editorial, application.evaluation, application.handlers, application.narrative_planner, application.outline, application.planner, application.summarize, cli, domain.directors, domain.draft, domain.extraction, domain.nodes, domain.patch, domain.reviser, domain.salience, domain.voice, domain.writers |
| extraction | 6 | events, gamesystem, house, state, text, worlds | 15 | application.handlers, application.model_context, application.outline, application.planner, application.repair, application.status, application.summarize, application.world, cli, domain.context, domain.genre, domain.progression, domain.propagation, domain.schema_words, domain.world_brief |
| jobs | 1 | events | 15 | adapters.sqlite_jobs, adapters.sqlite_store, application.conductor, application.directive_planner, application.director, application.editorial, application.handlers, application.narrative_planner, application.outline, application.planner, application.ports, application.repair, application.status, application.summarize, cli |
| directives | 1 | events | 13 | adapters.sqlite_audience, adapters.sqlite_plans, adapters.sqlite_store, application.conductor, application.directive_planner, application.director, application.editorial, application.narrative_planner, application.planner, application.ports, application.status, cli, domain.directors |
| worlds | 2 | events, state | 13 | application.model_context, application.outline, application.planner, application.repair, application.world, cli, domain.characters, domain.context, domain.extraction, domain.gamesystem, domain.integrity, domain.schema_words, domain.world_brief |
| writers | 4 | directors, house, text, voice | 11 | adapters.sqlite_roster, adapters.sqlite_store, application.concept, application.overview, application.planner, application.recruiter, application.revoice, application.roster, application.titles, application.world_agent, cli |
| findings | 3 | events, patch, promises | 10 | adapters.evaluation_artifact, adapters.sqlite_store, application.evaluation, application.handlers, application.ports, application.repair, application.summarize, application.world, cli, domain.integrity |
| patch | 3 | nodes, revision, text | 10 | adapters.sqlite_store, application.exemplars, application.handlers, application.narrative_planner, application.outline, application.repair, domain.draft, domain.findings, domain.policy, domain.progression |
| budget | 0 | - | 9 | adapters.sqlite_store, application.editorial, application.handlers, application.narrative_planner, application.outline, application.ports, application.repair, application.status, cli |
| directors | 3 | directives, text, voice | 9 | adapters.sqlite_store, application.directive_planner, application.director, application.editorial, application.narrative_planner, application.ports, application.roster, cli, domain.writers |
| plan_refinement | 0 | - | 9 | adapters.sqlite_plans, adapters.sqlite_store, application.directive_planner, application.editorial, application.narrative_planner, application.outline, application.plan_refinement, application.ports, cli |
| promises | 0 | - | 9 | adapters.sqlite_store, application.outline, application.ports, application.summarize, cli, domain.context, domain.findings, domain.integrity, domain.salience |
| voice | 1 | text | 9 | adapters.sqlite_store, adapters.sqlite_voice, application.exemplars, application.revoice, application.roster, cli, domain.directors, domain.draft, domain.writers |
| house | 0 | - | 8 | application.outline, application.planner, application.reviser, application.roster, cli, domain.extraction, domain.schema_words, domain.writers |
| plans | 0 | - | 8 | application.director, application.export, application.narrative_planner, application.outline, application.planner, application.repair, cli, domain.context |
| serials | 2 | beats, revision | 7 | application.editorial, application.handlers, application.outline, application.planner, application.readers, cli, domain.salience |
| beats | 2 | nodes, revision | 6 | application.narrative_planner, application.outline, application.planner, application.summarize, cli, domain.serials |
| editorial | 1 | events | 6 | adapters.sqlite_audience, adapters.sqlite_store, application.editorial, application.handlers, application.ports, cli |
| genre | 3 | extraction, gamesystem, state | 5 | application.outline, application.planner, application.world, cli, domain.progression |
| draft | 5 | nodes, patch, revision, text, voice | 4 | application.handlers, application.planner, cli, domain.policy |
| exceptions | 1 | events | 4 | adapters.sqlite_store, application.conductor, application.ports, cli |
| failures | 0 | - | 4 | application.conductor, application.handlers, cli, providers.base |
| gamesystem | 3 | events, state, worlds | 4 | application.world, cli, domain.extraction, domain.genre |
| integrity | 5 | findings, policy, promises, state, worlds | 4 | application.evaluation, application.handlers, application.world, cli |
| characters | 1 | worlds | 3 | application.model_context, cli, domain.context |
| reviser | 2 | events, text | 3 | adapters.sqlite_store, application.handlers, application.ports |
| schema_words | 3 | extraction, house, worlds | 3 | application.concept, application.world, cli |
| context | 8 | characters, extraction, nodes, plans, promises, revision, state, worlds | 2 | application.planner, cli |
| progression | 5 | extraction, genre, patch, policy, state | 2 | application.handlers, application.planner |
| propagation | 3 | extraction, revision, state | 2 | application.repair, cli |
| staging | 0 | - | 2 | application.outline, application.planner |
| tells | 0 | - | 2 | application.handlers, application.tells_pass |
| world_brief | 3 | extraction, state, worlds | 2 | application.narrative_planner, application.outline |
| position | 0 | - | 1 | domain.revision |
| rivals | 0 | - | 1 | cli |
| salience | 6 | events, promises, revision, serials, state, text | 1 | cli |
| litharness.domain | 0 | - | 0 | - |

#### Test modules importing each package module (top 25)

| module | test modules |
| --- | --- |
| domain | 88 |
| application | 66 |
| adapters | 48 |
| adapters.sqlite_store | 42 |
| domain.revision | 35 |
| domain.house | 24 |
| application.planner | 22 |
| domain.beats | 22 |
| cli | 22 |
| domain.extraction | 21 |
| domain.worlds | 21 |
| domain.nodes | 20 |
| domain.context | 20 |
| domain.writers | 18 |
| domain.jobs | 18 |
| domain.state | 16 |
| domain.policy | 16 |
| adapters.contracts_fixtures | 16 |
| providers | 13 |
| domain.events | 13 |
| domain.generation | 13 |
| domain.draft | 13 |
| domain.text | 12 |
| providers.registry | 11 |
| domain.genre | 11 |

**What `tests/test_architecture.py` enforces, and what it does not.** It enforces the layer
direction (`test_dependencies_only_point_outward_to_inward`), the absence of import cycles
(`test_internal_module_graph_has_no_cycles`), the port the registry must satisfy, and two
prose properties (every backticked symbol resolves, every cited test exists). It does not
enforce any direction *inside* a layer: the 84 domain-to-domain edges and the 57
application-to-application edges are constrained only by acyclicity. The three intra-domain
directions the brief states (`extraction` may import `gamesystem` and never the reverse;
`genre` imports `extraction`) hold today, and one of them is pinned outside the architecture
test: `tests/test_gamesystem.py::test_the_module_hands_out_columns_rather_than_sheet_fields`
reads `gamesystem`'s source and refuses an `extraction` import. Nothing pins the other two,
and nothing under `tools/` or `research/` is in the graph at all (the architecture test walks
`src/litharness` only). The split in §7 adds four domain modules below `extraction`; the
cycle test is what would notice a wrong arrow among them, and the seams are stated in
`docs/system-model.md`.

## 3. Test suite time and structure

### 3a. Durations

*Pending the box window: `uv run pytest --durations=0 --junitxml=FILE`, then
`uv run python tools/maintainability_survey.py durations FILE --top 20`. Recorded below once run.*

### 3b. Which tests touch a store, the filesystem or a subprocess

`uv run python tools/maintainability_survey.py stores --top 25`. A heuristic over each test
function's source (a `SqliteStore`, `sqlite3` or `.db` mention; `tmp_path`, a write or an
`open(`; `subprocess`; a call of the CLI's `main`), and a marker in a module-level fixture or
helper counts for every test in that module, so the counts are an upper bound on the tests
that actually touch the thing and an exact count of the modules that do.

3264 test functions in 161 modules; touching a store: 1004, the filesystem: 313, a subprocess: 328, the CLI's `main`: 89 (a test counts once per kind; a marker in a module-level fixture or helper counts for every test in that module).

| module | tests | store | filesystem | subprocess | cli |
| --- | --- | --- | --- | --- | --- |
| test_ab_redraw | 52 | 52 | 51 | 52 | 1 |
| test_cli | 55 | 55 | 35 | 0 | 3 |
| test_planner | 78 | 78 | 0 | 0 | 0 |
| test_draft | 55 | 55 | 0 | 0 | 0 |
| test_integrity | 48 | 48 | 5 | 0 | 0 |
| test_library | 30 | 30 | 22 | 0 | 2 |
| test_store | 42 | 42 | 10 | 0 | 0 |
| test_outline | 51 | 51 | 0 | 0 | 0 |
| test_promises | 39 | 39 | 0 | 0 | 0 |
| test_reviser | 35 | 35 | 0 | 0 | 0 |
| test_director | 27 | 27 | 5 | 0 | 4 |
| test_genre_floor | 25 | 25 | 5 | 0 | 5 |
| test_state | 30 | 30 | 0 | 0 | 0 |
| test_forensics | 21 | 21 | 4 | 0 | 0 |
| test_export | 20 | 20 | 4 | 0 | 0 |
| test_promise_payoff | 23 | 23 | 0 | 0 | 0 |
| test_concept | 17 | 17 | 4 | 0 | 4 |
| test_dashboard | 13 | 13 | 8 | 0 | 1 |
| test_force_report | 21 | 0 | 21 | 21 | 0 |
| test_opening_shape | 10 | 10 | 10 | 0 | 2 |
| test_world_brief | 18 | 18 | 2 | 0 | 0 |
| test_progression_gate | 18 | 18 | 1 | 0 | 0 |
| test_bt_house_panel | 23 | 2 | 16 | 0 | 4 |
| test_revoice_cli | 13 | 13 | 5 | 0 | 6 |
| test_writer_roster | 18 | 18 | 0 | 0 | 0 |

### 3c. Which test names the ledger cites

`uv run python tools/maintainability_survey.py ledger-tests --uncited`. The ledger cites tests
in two forms, and `tests/test_architecture.py::test_every_test_cited_as_evidence_exists`
checks only the backticked one.

351 distinct `test_` tokens in the ledger: 243 name a test function, 64 name a test module, 44 resolve to nothing. 239 are backticked, which is the form `tests/test_architecture.py` checks.

#### Ledger-cited test functions per test module

| module | cited functions |
| --- | --- |
| test_page_contract | 20 |
| test_reviser | 16 |
| test_planner | 10 |
| test_house_genre_promise | 10 |
| test_world_slots | 9 |
| test_implication_register | 8 |
| test_genre_floor | 7 |
| test_outline | 7 |
| test_ab_redraw | 7 |
| test_packet_order_key_spaces | 6 |
| test_library | 6 |
| test_schema_words | 6 |
| test_packet_register | 5 |
| test_display_names | 5 |
| test_prompt_budget | 5 |
| test_ablate_structure | 5 |
| test_worlds | 5 |
| test_scorecard | 5 |
| test_plain_diction | 5 |
| test_concept | 4 |
| test_draft | 4 |
| test_progression_gate | 4 |
| test_gamesystem | 4 |
| test_sentence_structure | 4 |
| test_providers | 4 |
| test_voice | 4 |
| test_narratorial_gloss | 4 |
| test_seed_completion_bounds | 4 |
| test_status | 3 |
| test_opening_shape | 3 |
| test_latent_probe | 3 |
| test_forensics | 3 |
| test_figure_clarity | 3 |
| test_progression_prompt | 3 |
| test_export | 3 |
| test_exemplars | 2 |
| test_opening_parity | 2 |
| test_integrity | 2 |
| test_choice_points | 2 |
| test_roster_installation | 2 |
| test_architecture | 2 |
| test_blurb_tribunal | 2 |
| test_corpus_leak_audit | 2 |
| test_store | 2 |
| test_listing_coordinator_gate | 2 |
| test_listing_arena_names | 2 |
| test_covers | 1 |
| test_tells_pass | 1 |
| test_serials | 1 |
| test_conductor | 1 |
| test_budget | 1 |
| test_architect_register | 1 |
| test_b6_benchmark | 1 |
| test_domain | 1 |
| test_extraction | 1 |
| test_import | 1 |
| test_roster_refusal | 1 |
| test_world_brief | 1 |
| test_readership_prior_life | 1 |
| test_scene_economy | 1 |
| test_dashboard | 1 |
| test_loop_adversarial | 1 |
| test_cli | 1 |
| test_revoice_cli | 1 |
| test_revoice | 1 |
| test_staging | 1 |

#### Tokens that resolve to no function or module (checked only when backticked)

| token | backticked |
| --- | --- |
| test_a_debt_the_serial_settles_later_is_opened_without_a_due_date | no |
| test_a_declared_protagonist_does_not_poison_its_own_book | no |
| test_a_forge_answer_that_does_not_conform_is_kept_on_disk_and_costed | no |
| test_a_forge_file_written_before_the_width_was_recorded_picks_as_it_always_did | no |
| test_a_forged_bundle_seeds_a_book_with_no_provider_call | no |
| test_a_licensed_judge_selects_through_the_same_pair_machinery | no |
| test_a_machine_written_row_can_never_denominate_a_preference_holdout | no |
| test_a_pick_with_no_scenes_takes_the_width_the_forge_recorded | no |
| test_a_premise_written_in_administration_is_refused | no |
| test_a_rollback_clears_the_lineage_because_it_reads_no_directive | no |
| test_a_rule_asks_what_a_person_would_want_and_puts_it_at_the_top_of_the_ladder | no |
| test_a_rule_says_the_genre_s_own_furniture_is_welcome | no |
| test_a_scene_count_the_directives_were_not_written_for_is_refused | no |
| test_a_scenes_flag_that_disagrees_with_the_forged_width_is_refused_naming_both | no |
| test_a_session_resumes_across_a_restart_because_its_state_is_rows | no |
| test_a_tripped_ceiling_parks_the_session_and_names_which_one | no |
| test_an_empty_feedback_set_is_not_the_same_as_no_feedback_row | no |
| test_architect | no |
| test_blame_json_keeps_an_empty_set_apart_from_no_row | no |
| test_impact | no |
| test_inverting_a_genre_default_is_optional_and_the_ladder_is_still_fenced | no |
| test_machine_rows_still_stale_the_licence_that_bought_them | no |
| test_no_rule_offers_a_debt_as_a_subject_or_a_market_as_an_interface | no |
| test_opening_counters | no |
| test_ordinary_legal_english_is_not_a_borrowed_reference | no |
| test_preference | no |
| test_the_accepted_event_carries_the_provenance_a_policy_record_will_need | no |
| test_the_administration_rate_is_reported_and_nothing_refuses_on_it | no |
| test_the_architect_ranks_nothing_and_cannot_learn_to | no |
| test_the_capability_rule_asks_for_a_declaration_and_never_a_performance | no |
| test_the_cost_rule_says_what_a_cost_is_paid_in | no |
| test_the_domain_is_the_engine_and_its_jargon_never_reaches_the_page | no |
| test_the_forge_records_the_width_it_forged_at | no |
| test_the_inventory_is_a_set_and_the_ladder_is_a_position | no |
| test_the_ladder_is_declared_furniture_rather_than_the_world_it_furnishes | no |
| test_the_named_offsets_are_the_opening_names_with_positions | no |
| test_the_pilot_package_regenerates_the_world_it_was_run_on | no |
| test_the_premise_rule_asks_for_a_pitch_rather_than_prose | no |
| test_the_protagonist_rule_asks_for_a_declaration_and_never_an_outcome | no |
| test_the_report_counts_the_inventory_and_declares_no_bar | no |
| test_the_session_spend_reaches_the_budget_governor | no |
| test_the_stall_detector_stops_the_session_where_the_fixed_path_poisons | no |
| test_the_variation_loop_imports_no_selection_machinery | no |
| test_world_uptake | no |

#### Test modules the ledger never names, by function or by file

test_authorship_tells, test_axiom_battery, test_bcr, test_blurb_rewrite, test_blurb_shelf, test_brief_capability, test_bt_analysis, test_bt_blinding, test_bt_population, test_bt_recognition, test_bt_transport, test_causal_salience, test_characters, test_check_tool, test_composite_panel, test_compression_progress, test_context, test_context_cutoff, test_continuity_evaluator, test_corpus_io, test_directive_planner, test_directives, test_director, test_director_distinctness, test_editorial, test_elicitation_study, test_epistemic_governance, test_exceptions, test_feed_battery, test_force_harness, test_force_remote, test_force_report, test_force_tracks, test_latent_crossfamily, test_listing_length_rail, test_listing_loop, test_loop_critics, test_markup_strip, test_model_context, test_narrative_planner, test_payoff_landing, test_persona_battery, test_personas, test_plan_refinement, test_policy_events, test_promise_kinds, test_promise_payoff, test_promises, test_reader_defects, test_reader_futures, test_reader_transport, test_recruiter, test_register_halflife, test_remote_prompt_transport, test_repair_generation, test_repair_workflow, test_retention_distance, test_roster_cli, test_salience, test_state, test_state_coverage, test_summarize, test_summary_reliability, test_surprisal_field, test_taste_benchmark, test_taste_calibration, test_thermal_watch, test_transmission_chains, test_verdict_locus, test_voice_binding, test_writer_distinctness, test_writer_roster, test_writer_states, test_writers

The 44 tokens that resolve to nothing are all unbackticked, so nothing checks them; most are
the retired Forge's tests (`test_architect`, `test_world_uptake`, the width and pick rules)
and the cut §61 pairwise stack (`test_preference`, `test_impact`), deleted with their modules
and still named in the entries that recorded them. That is the ledger being append-only and
is not a defect to fix here; it is recorded so a reader who greps a test name out of an old
entry knows why it is gone.

## 4. Where the load-bearing numbers live

`uv run python tools/maintainability_survey.py constants`. A "reason" is a `#:` block above the
assignment or a docstring below it; the table shows its first line.

487 module-level UPPER_CASE names in the package; 83 numeric; 321 carry a `#:` block or docstring saying why (56 of the numeric ones).

#### Numeric constants (value and the first line of the reason)

| home | name | value | why (first line) |
| --- | --- | --- | --- |
| adapters/sqlite_store.py:90 | BUSY_TIMEOUT_MS | 5000 | How long a writer waits for a contended database before reporting it locked. An |
| application/concept.py:65 | MAX_OUTPUT_TOKENS | 4000 | (none) |
| application/concept.py:69 | MIN_DEBTS | 2 | How many questions a book opens on purpose. Fewer than two is a book with one thing in it; |
| application/concept.py:70 | MAX_DEBTS | 4 | (none) |
| application/concept.py:73 | MIN_STEPS | 2 | A horizon of one step is no climb. |
| application/covers.py:23 | COVER_WIDTH | 400 | (none) |
| application/covers.py:24 | COVER_HEIGHT | 600 | (none) |
| application/covers.py:25 | DEFAULT_VARIANTS | 4 | (none) |
| application/covers.py:26 | MAX_VARIANTS | 8 | (none) |
| application/director.py:61 | DIRECT_PRIORITY | 400 | Beneath both human direction lanes (1000+ verbatim, 500+ interpretive) and above the draft... |
| application/director.py:67 | DIRECTIVE_EVERY | 6 | How many accepted scenes pass between one piece of machine direction and the next. Six, wh... |
| application/editorial.py:56 | READER_OBSERVE_PRIORITY | 250 | (none) |
| application/editorial.py:57 | EDITORIAL_INTERPRET_PRIORITY | 450 | (none) |
| application/exemplars.py:54 | DEFAULT_LIMIT | 2 | How many exemplars a writer is shown by default. Two, because the operator named two first |
| application/exemplars.py:59 | CHAPTER_WORDS | 2000 | Where an exemplar chapter is cut, in words, extended to the paragraph boundary. The two |
| application/exemplars.py:65 | LEAK_RUN_WORDS | 8 | The longest run of consecutive words a draft may share with a shown exemplar. Eight: `voic... |
| application/handlers.py:198 | _SEED_MODULUS | 2**31 - 1 | Ceiling for the derived seed. Ollama takes a 32-bit signed seed; a Python `int` from a |
| application/library.py:117 | DEFAULT_SCENES_PER_CHAPTER | 1 | One scene per chapter. See the module docstring: no assembly scheme is decided, and this |
| application/library.py:122 | DEFAULT_CHAPTERS_PER_VOLUME | 50 | A release-package boundary, not a story beat. Fifty is the operator's default for the |
| application/narrative_planner.py:68 | MAX_EDITS | 12 | (none) |
| application/outline.py:109 | OUTLINE_PRIORITY | 300 | Ranks above scene drafting (0) and below director direction (500+). A scene drafted before |
| application/outline.py:113 | TARGET_WORDS | 25 | Words per statement, asked for rather than enforced. A statement is an instruction to the |
| application/overview.py:41 | MAX_OUTPUT_TOKENS | 4000 | (none) |
| application/readers.py:58 | RECENT_FULL_CHAPTERS | 2 | (none) |
| application/readers.py:59 | RECALLED_SUMMARY_CHAPTERS | 4 | (none) |
| application/readers.py:73 | BUDGET_CHAPTERS | 2 | What a reader is told they have left. Small on purpose: an unbounded reader continues out ... |
| application/recruiter.py:97 | MAX_OUTPUT_TOKENS | 4000 | Binds nothing on the `claude -p` transport, which never reads it. It is here for a |
| application/repair.py:47 | EVALUATION_PRIORITY | 80 | (none) |
| application/repair.py:56 | SUMMARY_PRIORITY | 40 | Summarising an accepted scene ranks *below* everything, including drafting. |
| application/repair.py:66 | REPAIR_PRIORITY | 100 | Base claim priority for a repair. The finding's severity is added on top, so a critical |
| application/repair.py:67 | MAX_AUTO_REPAIRS | 3 | (none) |
| application/repair.py:71 | MAX_PROPAGATED_EVALUATIONS | 12 | Nodes one accepted repair may queue a re-check of. A six-scene book cannot exceed it; |
| application/reviser.py:92 | MAX_OUTPUT_TOKENS | 4096 | Binds nothing on the `claude -p` transport, which never reads it. Recorded rather than lef... |
| application/reviser.py:96 | TIMEOUT_SECONDS | 600.0 | Longer than a drafting call's, because this call's input is a scene plus the material the |
| application/revoice.py:77 | MAX_OUTPUT_TOKENS | 2000 | Binds nothing on the `claude -p` transport, which never reads it; recorded rather than lef... |
| application/revoice.py:82 | EXEMPLAR_WORDS | 150 | About how long a drawn passage should be. Long enough for a register to be visible in more... |
| application/summarize.py:67 | TARGET_WORDS | 60 | Words. Small on purpose — the whole value of the slot is that a scene costs a fraction of |
| application/tells_pass.py:39 | MAX_OUTPUT_TOKENS | 4000 | (none) |
| application/tells_pass.py:42 | ATTEMPTS | 2 | Two batched tries per family, then what is left stays as drafted: a third is a redraw by |
| application/titles.py:53 | MAX_OUTPUT_TOKENS | 2000 | (none) |
| application/world_agent.py:87 | MAX_OUTPUT_TOKENS | 16000 | (none) |
| application/world_agent.py:91 | SEED_TIMEOUT_SECONDS | 3600.0 | The seed's wall-clock ceiling. Pilot 22's first arm (§197.1) measured a two-system seed |
| cli.py:193 | EXIT_OK | 0 | Exit codes, which are how whatever drives `tick` reads the outcome. See the module |
| cli.py:194 | EXIT_ATTENTION | 1 | (none) |
| cli.py:195 | EXIT_FAULT | 2 | (none) |
| cli.py:198 | SERIAL_POSITION_CAPACITY | 100_000 | (none) |
| cli.py:254 | LISTING_COORDINATOR_CEILING | 5.89 | **The listing loop's first refusing gate, and the only market-derived number under `src/`.... |
| cli.py:259 | LISTING_DRAW_ATTEMPTS | 3 | How many times the listing loop will draw before keeping what it has. Bounded so a writer |
| cli.py:264 | CONCEPT_DRAW_ATTEMPTS | 3 | The concept's own bounded redraw, on the listing's rail and no other: a machinery word use... |
| domain/budget.py:46 | DEFAULT_TAX_TOKENS | 24_000 | What a call is assumed to cost when the provider is unknown. The maximum of the known |
| domain/context.py:126 | SUMMARY_SHARE | 0.25 | The largest share of the packet summaries may claim, so that they can be placed at all. |
| domain/context.py:151 | DEFAULT_TOKEN_BUDGET | 200_000 | **Raised from 6,000 to 200,000 on operator direction, 2026-08-24 (stage-0 §132).** *"6000 |
| domain/context.py:160 | DEFAULT_RESERVED_OUTPUT | 1500 | Held back from the packet for the generation itself. A budget spent entirely on input |
| domain/directors.py:62 | DISTINCTNESS_FLOOR | 3 | How many draws each side of the distinctness comparison needs before it says anything. Thr... |
| domain/directors.py:325 | _GZIP_LEVEL | 9 | Encoded length with the container's first-order overhead removed. **Inlined here when |
| domain/extraction.py:553 | LABEL_WORDS | 3 | What a bracket tag can be. Placed numbers, stated as placed — see `GraphLine.__post_init__... |
| domain/extraction.py:554 | LABEL_CHARS | 24 | (none) |
| domain/extraction.py:557 | PHRASE_WORDS | 6 | What a printed verb phrase can be, between a name and a thing on one line. |
| domain/gamesystem.py:160 | MIN_ABILITIES | 5 | **The floor is what makes it a graph rather than a list, and the ceiling is the width of a |
| domain/gamesystem.py:161 | MAX_ABILITIES | 8 | (none) |
| domain/gamesystem.py:164 | MIN_RANKS | 3 | Three rungs, because a two-rung ladder is a switch and `rung_index`'s number has nowhere t... |
| domain/gamesystem.py:171 | MIN_OPTIONS | 2 | How many ways a fork may offer. **Neither is a bar and neither was arrived at by measuring |
| domain/gamesystem.py:172 | MAX_OPTIONS | 4 | (none) |
| domain/gamesystem.py:177 | MIN_SCALE_MAXIMUM | 2 | A magnitude of 1 is "held", so a maximum of 1 is a system where nothing can deepen and the |
| domain/gamesystem.py:178 | MAX_SCALE_MAXIMUM | 99 | (none) |
| domain/gamesystem.py:192 | LABEL_CHARS | 24 | A label has to fit beside its number on a line somebody reads. |
| domain/genre.py:340 | EVERY | 2 | The operator, minutes after the seventh read, and then again minutes after that: |
| domain/integrity.py:123 | _MIN_SPAN | 8 | didn't know what to say", "for the first time in his life" — and a metric that fires on |
| domain/integrity.py:128 | _SPAN_CAP | 200 | Stop looking once a span is this long. The difference between "180 words repeated" and |
| domain/integrity.py:538 | DUPLICATE_SPAN_WORDS | 120 | Words of verbatim overlap with an earlier accepted scene at which a candidate is refused. |
| domain/position.py:28 | GAP | 10 | (none) |
| domain/position.py:29 | MIN_WIDTH | 3 | (none) |
| domain/rivals.py:51 | MIN_RATING | 4.0 | **Above four stars, and "above" is strict.** The operator's words are *"rated above 4 star... |
| domain/rivals.py:57 | MIN_RATINGS | 20 | **Ratings are a mean and a mean over three votes is not a rating.** A book with one five-s... |
| domain/rivals.py:68 | MIN_DECIMALS | 2 | **The operator's proxy for the count, for the case where the page shows no count.** |
| domain/rivals.py:86 | MIN_FOLLOWERS | 1000 | **The other kind of evidence, and it exists because the first kind is not available.** The |
| domain/serials.py:327 | CONTEXT_WINDOW_CHAPTERS | 2 | How many *chapters* of prior prose a scene's context may draw on, whatever the serial's |
| domain/staging.py:80 | OPENING | 2 | How many scenes at the head of a book carry the bound. **A placed number, and recorded as |
| domain/staging.py:86 | NAMED | 3 | How many people the opening may name on one page. Placed, on the same terms as `OPENING`, |
| domain/tells.py:87 | CHAIN_ANDS | 3 | (none) |
| domain/text.py:88 | STOP_FRACTION | 0.6 | Fraction of a passage's words behind the stop point. **Frozen at §124's value and it is th... |
| domain/voice.py:456 | SHARED_RUN_LIMIT | 6 | How long a run of identical words may be, between a passage and a text rewritten to read l... |
| domain/voice.py:498 | PERSON_MARGIN | 2.0 | How far apart the two counts must be before a text is called one person rather than mixed. |

#### Budgets pinned in the suite

| home | row | value |
| --- | --- | --- |
| tests/test_prompt_budget.py::BUDGET | title writer | 10 |
| tests/test_prompt_budget.py::BUDGET | concept writer | 18 |
| tests/test_prompt_budget.py::BUDGET | tells rewriter | 4 |
| tests/test_prompt_budget.py::BUDGET | architect seed, second system | 48 |
| tests/test_prompt_budget.py::BUDGET | title lookup | 6 |
| tests/test_prompt_budget.py::BUDGET | recruiter, single image | 25 |
| tests/test_prompt_budget.py::BUDGET | recruiter, several with beat | 25 |
| tests/test_prompt_budget.py::BUDGET | recruiter, several no beat | 25 |
| tests/test_prompt_budget.py::BUDGET | listing writer | 18 |
| tests/test_prompt_budget.py::BUDGET | architect seed | 46 |
| tests/test_prompt_budget.py::BUDGET | architect grow | 40 |
| tests/test_prompt_budget.py::BUDGET | scene writer floor | 25 |
| tests/test_prompt_budget.py::BUDGET | scene writer, cast | 29 |
| tests/test_prompt_budget.py::BUDGET | measurement reader | 4 |
| tests/test_prompt_budget.py::BUDGET | steering reader | 4 |
| tests/test_prompt_budget.py::BUDGET | revoice draw | 9 |
| tests/test_prompt_budget.py::BUDGET | revoice rewrite | 14 |
| tests/test_prompt_budget.py::BUDGET | reviser | 31 |
| tests/test_prompt_budget.py::HOUSE_BUDGET |  | 22 |
| tests/test_prompt_budget.py::SCENE_CONDITIONAL_BUDGET | status_example | 4 |
| tests/test_prompt_budget.py::SCENE_CONDITIONAL_BUDGET | progression | 3 |
| tests/test_prompt_budget.py::SCENE_CONDITIONAL_BUDGET | offer_line | 2 |
| tests/test_prompt_budget.py::SCENE_CONDITIONAL_BUDGET | gain_line | 2 |
| tests/test_prompt_budget.py::SCENE_CONDITIONAL_BUDGET | change_line | 2 |
| tests/test_prompt_budget.py::SCENE_CONDITIONAL_BUDGET | exemplars | 1 |
| tests/test_prompt_budget.py::SCENE_CONDITIONAL_BUDGET | standing | 3 |
| tests/test_prompt_budget.py::SCENE_CONDITIONAL_BUDGET | standing_line | 2 |
| tests/test_prompt_budget.py::SCENE_CONDITIONAL_BUDGET | target_words | 3 |
| tests/test_prompt_budget.py::SCENE_CONDITIONAL_BUDGET | criteria | 2 |
| tests/test_prompt_budget.py::SCENE_MAXIMAL_BUDGET |  | 45 |
| tests/test_prompt_budget.py::SCENE_MOVED_DEMANDS |  | 0 |
| tests/conftest.py::PROMOTABLE_FLAGS |  | 17 |

**Of the 83 numeric constants, 27 carry no reason of their own.** Most are the second of a
documented pair (`MAX_ABILITIES` beside `MIN_ABILITIES`, `EXIT_ATTENTION` beside `EXIT_OK`) or
a `MAX_OUTPUT_TOKENS` whose sibling in another module says it binds nothing on the `claude -p`
transport; the ones with no documented neighbour are the cover dimensions and variant counts
in `application/covers.py`, the two editorial priorities, `SERIAL_POSITION_CAPACITY`,
`MAX_EDITS`, the two reader window sizes in `application/readers.py`, `EVALUATION_PRIORITY`,
`MAX_AUTO_REPAIRS`, `GAP` and `MIN_WIDTH` in `domain/position.py`, and `CHAIN_ANDS`. The brief
refuses shortening docstrings; adding a reason is a separate, cheap change and is not made
here because the reason would be this session's guess.

The homes a map should point at, and does (`docs/system-model.md`, last section): the prompt
ceilings in `tests/test_prompt_budget.py`; the draw bounds in `domain/gamesystem.py`; the packet
budget and the summary share in `domain/context.py`; the seed's wall-clock ceiling in
`application/world_agent.py`; the reviser's containment band in `application/reviser.py` and
`domain/reviser.py` (§185, §188.7); the scale bounds `MIN_SCALE_MAXIMUM` and
`MAX_SCALE_MAXIMUM`; the market admission thresholds in `domain/rivals.py`; the exemplar leak
run in `application/exemplars.py`.

## 5. Docstring knowledge that is not findable

`uv run python tools/maintainability_survey.py citations --sample 50 --out FILE`.

1330 citation sites, 217 distinct entries (121 majors, 96 sub-entries). A `§` names either a stage-0 entry or a PLAN.md section, and the text around it says which: 160 entries resolve only in the ledger, 10 only in PLAN.md, 19 in both (ambiguous by number alone). The ledger has 212 numbered entries and 505 numbered sub-entries; PLAN.md has 22 and 17.

#### Cited entries with no heading in either document

| entry | sites | where |
| --- | --- | --- |
| 10.4 | 11 | domain/findings.py:146, domain/integrity.py:110, domain/integrity.py:16, domain/integrity.py:533 ... |
| 2.1 | 10 | application/concept.py:197, application/library.py:147, application/library.py:156, cli.py:4201 ... |
| 2.2 | 5 | application/concept.py:190, cli.py:2829, domain/genre.py:277, domain/genre.py:82 ... |
| 20.3 | 5 | application/handlers.py:24, domain/events.py:29, domain/jobs.py:10, domain/jobs.py:192 ... |
| 10.2 | 4 | application/handlers.py:987, domain/integrity.py:691, domain/integrity.py:703, domain/state.py:84 |
| 3.1 | 4 | application/overview.py:91, cli.py:2274, domain/worlds.py:1336, domain/writers.py:171 |
| 5.1 | 4 | domain/draft.py:203, domain/worlds.py:547, domain/worlds.py:72, domain/worlds.py:81 |
| 0.1 | 3 | domain/context.py:93, domain/worlds.py:22, domain/worlds.py:910 |
| 20.4 | 3 | application/handlers.py:5, application/repair.py:61, domain/jobs.py:18 |
| 6.2 | 3 | domain/worlds.py:33, domain/worlds.py:374, domain/worlds.py:408 |
| 10.6 | 2 | adapters/sqlite_store.py:1412, domain/findings.py:23 |
| 14.1 | 2 | domain/worlds.py:374, domain/worlds.py:6 |
| 14.3 | 2 | domain/extraction.py:1510, domain/extraction.py:583 |
| 20.6 | 2 | application/outline.py:32, domain/beats.py:4 |
| 20.8 | 2 | domain/findings.py:145, domain/policy.py:20 |
| 4.6 | 2 | domain/house.py:354, domain/house.py:46 |
| 10.5 | 1 | domain/policy.py:136 |
| 15.7 | 1 | domain/worlds.py:360 |
| 2.4 | 1 | application/concept.py:206 |
| 20.2 | 1 | adapters/contracts_fixtures.py:26 |
| 3.2 | 1 | application/planner.py:398 |
| 3.4 | 1 | domain/worlds.py:1924 |
| 4.5 | 1 | domain/house.py:399 |
| 4.7 | 1 | domain/revision.py:27 |
| 5.4 | 1 | application/concept.py:4 |
| 6.1 | 1 | application/library.py:99 |
| 7.9 | 1 | domain/worlds.py:413 |
| 8.5 | 1 | domain/worlds.py:7 |

#### Entries whose number exists in both documents (context decides)

§1 (31), §2 (17), §3 (11), §4 (3), §5 (24), §6 (10), §7 (8), §8 (4), §9 (3), §10 (3), §11 (11), §12 (21), §13 (8), §14 (1), §15 (13), §16 (2), §17 (27), §18 (3), §19 (31)

#### Most-cited entries

| entry | sites |
| --- | --- |
| 61 | 46 |
| 4.2 | 45 |
| 138 | 37 |
| 19 | 31 |
| 1 | 31 |
| 97.1 | 29 |
| 154 | 29 |
| 17 | 27 |
| 187 | 25 |
| 5 | 24 |
| 160 | 24 |
| 12 | 21 |
| 210 | 20 |
| 113 | 19 |
| 163 | 19 |

#### Citation sites per module (top)

| module | sites |
| --- | --- |
| domain/house.py | 147 |
| domain/gamesystem.py | 107 |
| cli.py | 104 |
| domain/extraction.py | 81 |
| domain/worlds.py | 70 |
| application/planner.py | 69 |
| application/handlers.py | 68 |
| domain/genre.py | 45 |
| application/overview.py | 43 |
| application/reviser.py | 31 |
| domain/integrity.py | 31 |
| adapters/sqlite_store.py | 29 |
| application/outline.py | 26 |
| application/readers.py | 26 |
| application/world_agent.py | 25 |

The 28 entries with no heading in either document are not broken citations: each names a
numbered section of another planning file (`plan/serial-pilot-14.md` §2.2 and §7,
`plan/serial-pilot-15b.md` §5, `plan/state-model-abilities.md` §0.1 and §5, `plan/director-role.md`
§0, `plan/writer-roster.md` §3.1, `research/progression-generalization.md` §14.3) or a numbered
item under a PLAN.md heading (§20.2 is the second immediate action, §10.4 the fourth item of
the quality-gates section), and the citing text says so. The resolver reads headings only,
which is the right rail for the two documents that promise them; a citation into a plan note
is checked by reading.

**The fifty-site sample, read.** The fifty sites were chosen as every twenty-seventh site in
path order (`--sample 50`, deterministic), each read in its code context against the entry it
cites, by four read-only agents whose reports were then checked against the documents where a
verdict was not MATCH. Result: 43 match, 6 stale, 1 ambiguous, 0 unresolved. Agent prose is
not evidence and none of this is a research claim; every stale verdict below was confirmed by
reading the entry.

| Site | Cites | Says | The entry | Correcting pointer |
| --- | --- | --- | --- | --- |
| `application/handlers.py:243` and `:714` | §187 | the draft goes through the gates first, two ladder runs per revised scene, `_Ladder` is a value; the em-dash strip runs once per ladder run | §187 is the removal of five register clauses from `house`, and §187.5 refuses exactly this work | §188.2 ships the stage order and the `_Ladder` sentence verbatim |
| `application/ports.py:62` | §187 | `pre_revision_drafts` is write-only at the port boundary | same entry, same refusal | §188.4, "The draft is kept, and where" |
| `domain/integrity.py:682` and `:750`, `application/handlers.py:593` and `:744` | PLAN.md §4.2 "ladder step 3" | the integrity gate is step 3 | §4.2 numbers the ladder shape, integrity, craft, budget; integrity is step 2, and the baseline PLAN.md had the same list | none exists; the code's numbering was wrong from the start and is corrected in place in the four comments |
| `domain/house.py:718`, `domain/schema_words.py:96` | §120 | "§120 measured `standing` reaching a chapter" | §120 is the pitch-reader battery on six premises; its one "standing" is the sham pair. The measurement is recorded in §135 item 3, and §146.8, §155.3, §178, §185.5 and §198.1 all repeat the §120 attribution | §135 item 3 (the entry that shipped `house.MACHINERY_WORDS`); §178 for the `schema_words` case |
| `application/readers.py:613` | §87 to §89 | "spent three entries without" an external label | §87.2 ran §79's conversion-labelled pairs, a reader-produced label, and §89.2 reports the same | §87.2 and §79; what is new at the site is a market-admitted rival against our text, not the first external label |
| `domain/gamesystem.py:1323` and 26 other sites | §61(5) | "no model ranks", "no ordering of any other kind" | §61(5) is a multiplicity pre-registration: a headline confidence is divided by the candidate count | ambiguous by the letter and settled by convention: `CLAUDE.md`'s axioms cite §61(5) the same way and pair it with §105.1 and §107.5, which carry the containment rule; left as it is |

The pointers are added as one line each in the citing docstrings (deliverable 6), and the
ledger is not edited: the §120 attribution inside six ledger entries is the ledger's to
correct in place, and is reported to the operator rather than touched.

**Where citations are dense.** `domain/house.py` carries 147 sites in 803 lines, `gamesystem.py`
107, `cli.py` 104, `extraction.py` 81: the four modules a newcomer opens first are the four
where a stale pointer costs most, which is why the sample was spread by path rather than
weighted by module.

## 6. Duplicate test helpers

`uv run python tools/maintainability_survey.py helpers --top 25`.

45 helper or fixture names are defined in 2 or more test modules; 12 of those definitions are byte-for-byte repeats of another (docstrings and layout aside). A name defined several times with distinct bodies is several fixtures sharing a name, not a duplicate.

| name | defs | distinct bodies | identical across | signatures |
| --- | --- | --- | --- | --- |
| store | 27 | 24 | test_integrity, test_state, test_store; test_roster_refusal, test_writer_roster | tmp_path |
| _clause | 7 | 7 | - | (), text |
| _record | 6 | 6 | - | record_id, record_id, subject, predicate, revision, subject, predicate, value, target_slot, named_slot, value |
| _canon | 5 | 5 | - | (), records, subject, predicate, subject, predicate, value, system |
| db | 5 | 4 | test_revoice_cli, test_roster_cli | tmp_path |
| _accepted | 4 | 4 | - | built, record, records |
| _run | 4 | 4 | - | manifest, tmp_path, elicitor, records, store, answers, store, ticks |
| _system | 4 | 4 | - | (), shape |
| a_book | 4 | 4 | - | (), scenes, store, scenes |
| book | 4 | 4 | - | (), tmp_path |
| fake | 4 | 2 | test_listing_loop, test_world_supersession; test_schema_words, test_world_slots | monkeypatch |
| run | 4 | 1 | test_cli, test_export, test_forensics, test_roster_cli | db |
| seeded | 4 | 4 | - | store, store, payload_extra, tmp_path |
| _accept | 3 | 3 | - | returned, store |
| _fiction | 3 | 3 | - | fiction_id, rows, work, author, conversion, views, followers |
| _fixture | 3 | 2 | test_genre_floor, test_staging | store, name |
| _member_text | 3 | 3 | - | chunks, word, marker |
| _row | 3 | 3 | - | (), index, words |
| _seeded | 3 | 3 | - | store, system, character, tmp_path |
| conductor | 3 | 2 | test_conductor, test_directives | store, holder, store, provider |
| record | 3 | 3 | - | record_id, record_id, subject, predicate, value, subject, predicate |
| _beat | 2 | 2 | - | (), revision, ordinal |
| _book | 2 | 2 | - | paragraphs, marker, store, name |
| _book_zero | 2 | 2 | - | store, store, records |
| _capture | 2 | 2 | - | monkeypatch, monkeypatch, module |

**The pruning brief's premise was half right.** `_accepted`, `_canon`, `rec` and `_system`
are re-implemented across modules by name, but `_system` is four different systems (the Weave
with five abilities, the same with a fork, the yard board, and a recruiter shape) whose
docstrings say why each is local, and the five `_canon` and six `_record` homonyms are five
and six different fixtures. The one real family is *make this record canon*
(`dataclasses.replace` to `ACCEPTED_CANON`, or a field-by-field copy doing the same), spread
over `_accepted`, `accepted`, `_canonical` and one `_canon`, in record and list forms. The
byte-identical repeats are the `store` and `db` fixtures (three and two copies), `run`
(four), `fake` (two pairs), `conductor`, `_fixture` and `accepted`. The pruning session owns
the consolidation into `tests/helpers.py` (its message of 2026-09-03 says so), so this brief's
item 3 is not done here; the ledger-cited test names are untouched by it either way, since no
cited name is a helper.

## 7. What the survey settles for the changes

### 7a. `extraction.py` splits cleanly along four seams

`uv run python tools/maintainability_survey.py sections --coupling src/litharness/domain/extraction.py`:

(no `# ---` section markers)

private helpers by number of top-level users:

| helper | users | used by |
| --- | --- | --- |
| _canon_of | 6 | _following, change_example, extract_graph_facts, gain_example, sheet_for, standing_example |
| _LINE | 3 | Sheet, _status_lines, sheet_from_line |
| _printing_system | 3 | _standing_sheet, offered_choice, offered_line |
| _standing_sheet | 3 | change_example, movables, moved_values |
| _counted | 2 | counted_names, movables |
| _edge_key | 2 | extract_graph_facts, promotions |
| _folds_into | 2 | _folded_before, state_as_it_stands |
| _named_moves | 2 | movables, moved_values |
| _LOOSE_PAIR | 1 | sheet_from_line |
| _NUMBERS | 1 | Sheet |
| _TRAILING_NUMBER | 1 | _read_typed |
| _above_zero | 1 | _held |
| _already_canon | 1 | extract_state |
| _compile_graph_pattern | 1 | GraphLine |
| _compile_pattern | 1 | Sheet |
| _folded_before | 1 | extract_state |
| _following | 1 | sheet_for |
| _held | 1 | Sheet |
| _read_typed | 1 | Sheet |
| _render_typed | 1 | Sheet |
| _stands_before | 1 | snapshot_at |
| _status_lines | 1 | extract_state |
| _system_prints_the_line | 1 | _printing_system |
| _the_protagonists | 1 | snapshot_at |

Only three private helpers are used across subjects: `_canon_of` (six users, three subjects),
`_folds_into` (the snapshot fold and `_folded_before` in extraction proper) and
`_status_lines` (defined with the sheet, used by `extract_state`). Everything else stays with
its subject. Two tests reach a private name through the module (`extraction._printing_system`
in `tests/test_two_systems.py`, `extraction._named_moves` in `tests/test_choice_points.py`) and
one cites `extraction._already_canon` in prose; the split keeps all three reachable. The
dependency order that avoids a cycle, checked against the code: `names` (a subject's printed
name) below `sheet` (the model, its declaration readers, the snapshot fold and the printed line,
which needs `display_name`) below `graphline` (whose `MalformedGraphLine` subclasses
`MalformedSheet`) below `moves` (the move vocabulary and the example lines, which need the
fold, the sheet, the graph line and `gamesystem`) below `extraction` (positions, record
identity, `extract_state`, `extract_graph_facts`, `promotions`, and every re-export). Nothing
below imports `extraction`, so the old module stays the top and every import elsewhere is
unchanged.

### 7b. `gamesystem.py` is one hub and a split needs a facade

`uv run python tools/maintainability_survey.py sections --matrix src/litharness/domain/gamesystem.py`:

| section | lines | span | defs | public |
| --- | --- | --- | --- | --- |
| the vocabulary | 108-151 | 44 | 0 | 5 |
| what a draw must be | 152-223 | 72 | 3 | 10 |
| the definition | 224-621 | 398 | 8 | 8 |
| one position in it | 622-808 | 187 | 6 | 6 |
| drawing a system | 809-1183 | 375 | 5 | 2 |
| advancing a sheet | 1184-1650 | 467 | 17 | 10 |
| writing it down | 1651-1907 | 257 | 3 | 2 |
| reading it back | 1908-2608 | 701 | 15 | 8 |

cross-section references (a definition in one section naming one in another):

| from section | to section | refs | examples |
| --- | --- | --- | --- |
| advancing a sheet | one position in it | 32 | offered_options -> CharacterSheet; _needs_met -> CharacterSheet; _unmet -> CharacterSheet; _unpaid -> CharacterSheet ... |
| reading it back | the definition | 13 | systems_of -> Scale; systems_of -> SystemDef; _assemble -> Ability; _assemble -> Rank ... |
| advancing a sheet | the definition | 10 | offered_options -> Choice; offered_options -> Option; _needs_met -> Ability; _unmet -> Need ... |
| drawing a system | what a draw must be | 9 | check_draw -> MAX_ABILITIES; check_draw -> MAX_OPTIONS; check_draw -> MAX_SCALE_MAXIMUM; check_draw -> MIN_ABILITIES ... |
| advancing a sheet | what a draw must be | 6 | _never_a_move -> IllegalAdvance; gain -> IllegalAdvance; deepen -> IllegalAdvance; rise -> IllegalAdvance ... |
| reading it back | the vocabulary | 6 | systems_of -> MAGNITUDE_SCALE; drawn_digests -> SYSTEM_DIGEST; drawn_grants -> SYSTEM_DIGEST; unfinished_systems -> MAGNITUDE_SCALE ... |
| drawing a system | the definition | 5 | _option_material -> Option; check_draw -> SystemDef; _cycle -> SystemDef; _openers -> SystemDef ... |
| the definition | what a draw must be | 2 | Choice -> IllegalAdvance; SystemDef -> IllegalAdvance |
| one position in it | the definition | 2 | CharacterSheet -> SystemDef; Furniture -> Column |
| writing it down | the vocabulary | 2 | records_for -> MAGNITUDE_SCALE; records_for -> SYSTEM_DIGEST |
| writing it down | one position in it | 2 | records_for_sheet -> CharacterSheet; _snapshot_record -> CharacterSheet |
| reading it back | what a draw must be | 2 | completion_records -> MIN_SCALE_MAXIMUM; completion_records -> MalformedSystem |
| reading it back | one position in it | 2 | changes_of -> Change; sheet_of -> CharacterSheet |
| the definition | the vocabulary | 1 | SystemDef -> RANK_KEY |
| the definition | drawing a system | 1 | SystemDef -> _option_material |
| one position in it | the vocabulary | 1 | CharacterSheet -> RANK_KEY |
| drawing a system | the vocabulary | 1 | check_draw -> RANK_KEY |
| drawing a system | one position in it | 1 | starting_sheet -> CharacterSheet |
| advancing a sheet | writing it down | 1 | _advanced -> _snapshot_record |
| writing it down | what a draw must be | 1 | records_for -> MalformedSystem |
| writing it down | the definition | 1 | records_for -> SystemDef |
| writing it down | drawing a system | 1 | records_for -> check_draw |
| reading it back | drawing a system | 1 | growth -> check_draw |
| reading it back | writing it down | 1 | completion_records -> records_for |

The definition section is what every other section references, and it references the drawing
section back (`SystemDef` uses `_option_material`), so the definition and the draw check stay
together at the bottom. Advancing needs `_snapshot_record` from writing; reading needs
`records_for` and `check_draw`; neither advancing nor reading needs the other. A split
therefore has the shape definition-and-draw, records (writing and reading), advancement, with
`gamesystem.py` left as a facade of re-exports, because the bottom module cannot also be the
re-export hub without an import cycle. Three tests read the module as a module:
`tests/test_gamesystem.py` walks `gs.__all__` for banned words twice and reads `gs.__file__` to
refuse an `extraction` import, and `tests/test_choice_points.py` reads `inspect.getsource` of
`gamesystem` for `def best` and its kin. A facade keeps all three green only if its `__all__`
is the union and its file text still contains no `extraction` import, which a facade of
imports does. It is the second split, taken after the first replays clean, and its ledger
entry says what moved.

### 7c. Type coverage outside `src/`

*Pending the box window: `uv run mypy tools/ research/quality-measurement/*.py` against the
`[tool.mypy]` settings, error count per file. Recorded below once run.*

### 7d. The slow lane

Decided on the durations in §3a: the tests marked `slow` and the two lane durations are
recorded there.
