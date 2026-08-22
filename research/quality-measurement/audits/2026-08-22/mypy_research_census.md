# mypy --strict distance per research module (run by Claude, 2026-08-22)

`uv run mypy --strict --follow-imports=silent --ignore-missing-imports <module>` per file; counts are this run's tally.

| module | lines | errors | top codes |
|---|---:|---:|---|
| b6_benchmark | 269 | 0 |  |
| baseline | 211 | 0 |  |
| cadence_discrimination | 562 | 0 |  |
| corpus_io | 407 | 0 |  |
| determinism_probe | 148 | 0 |  |
| director_distinctness | 321 | 0 |  |
| evaluate | 407 | 0 |  |
| fitness_books | 386 | 0 |  |
| latent_fixtures | 484 | 0 |  |
| latent_support | 244 | 0 |  |
| opening_counters | 242 | 0 |  |
| personas | 516 | 0 |  |
| platform_priors | 1515 | 0 |  |
| reader_defects | 355 | 0 |  |
| reader_repair | 295 | 0 |  |
| refuted_metrics | 187 | 0 |  |
| state_coverage | 284 | 0 |  |
| summary_reliability | 708 | 0 |  |
| taste_calibration | 415 | 0 |  |
| thermal_watch | 252 | 0 |  |
| transmission_chains | 516 | 0 |  |
| verdict_locus | 381 | 0 |  |
| voice_binding | 415 | 0 |  |
| authorship_tells | 342 | 1 | syntax 1 |
| build_craft_profile | 309 | 1 | syntax 1 |
| composite_panel | 349 | 1 | arg-type 1 |
| compression_progress | 979 | 1 | attr-defined 1 |
| corpus_leak_audit | 462 | 1 | var-annotated 1 |
| force_market | 540 | 1 | operator 1 |
| force_remote | 398 | 1 | no-any-return 1 |
| force_report | 232 | 1 | no-any-return 1 |
| latent_probe | 1090 | 1 | syntax 1 |
| promise_kinds | 486 | 1 | no-any-return 1 |
| retention_distance | 566 | 1 | assignment 1 |
| surprisal_field | 370 | 1 | attr-defined 1 |
| writer_distinctness | 360 | 1 | no-any-return 1 |
| writer_g0 | 199 | 1 | no-any-return 1 |
| ablate | 1072 | 2 | type-arg 1, no-untyped-def 1 |
| bcr | 1616 | 2 | operator 1, no-redef 1 |
| feedback_ablation | 597 | 2 | no-any-return 2 |
| force_harness | 1120 | 2 | operator 2 |
| latent_crossfamily | 377 | 2 | arg-type 1, call-overload 1 |
| taste_benchmark | 612 | 2 | misc 1, no-untyped-call 1 |
| world_lexicon | 270 | 2 | arg-type 1, attr-defined 1 |
| writer_states | 624 | 2 | assignment 2 |
| cdg_battery | 356 | 3 | no-any-return 1, misc 1, arg-type 1 |
| payoff_landing | 676 | 3 | dict-item 2, no-any-return 1 |
| register_halflife | 1031 | 3 | no-any-return 3 |
| chapter_endings | 449 | 4 | call-overload 2, type-var 1, arg-type 1 |
| surprisal | 234 | 4 | no-untyped-def 4 |
| comic_beats | 2534 | 5 | no-any-return 4, assignment 1 |
| conversion_separation | 369 | 5 | type-arg 2, operator 2, no-untyped-call 1 |
| elicit | 1468 | 5 | misc 3, arg-type 1, return-value 1 |
| elicitation_study | 1224 | 5 | arg-type 2, no-any-return 1, type-arg 1 |
| force_gpu | 780 | 7 | no-any-return 4, no-untyped-def 2, dict-item 1 |
| repair_generation | 572 | 8 | arg-type 2, misc 2, operator 2 |
| persona_battery | 993 | 22 | attr-defined 13, unused-ignore 4, type-arg 1 |
| axiom_battery | 1194 | 24 | no-untyped-def 10, no-untyped-call 4, var-annotated 2 |

Modules: 58; total errors: 128; modules with <= 10 errors: 56 (b6_benchmark, baseline, cadence_discrimination, corpus_io, determinism_probe, director_distinctness, evaluate, fitness_books, latent_fixtures, latent_support, opening_counters, personas, platform_priors, reader_defects, reader_repair, refuted_metrics, state_coverage, summary_reliability, taste_calibration, thermal_watch, transmission_chains, verdict_locus, voice_binding, authorship_tells, build_craft_profile, composite_panel, compression_progress, corpus_leak_audit, force_market, force_remote, force_report, latent_probe, promise_kinds, retention_distance, surprisal_field, writer_distinctness, writer_g0, ablate, bcr, feedback_ablation, force_harness, latent_crossfamily, taste_benchmark, world_lexicon, writer_states, cdg_battery, payoff_landing, register_halflife, chapter_endings, surprisal, comic_beats, conversion_separation, elicit, elicitation_study, force_gpu, repair_generation)

Most common codes overall: no-any-return 22, attr-defined 18, no-untyped-def 17, arg-type 13, operator 9, misc 8, assignment 7, type-arg 6
