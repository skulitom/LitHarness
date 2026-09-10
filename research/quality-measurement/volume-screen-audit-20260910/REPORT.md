# Historical volume-screen reconciliation

Retrospective, call-free audit on 2026-09-10. The original registration and all original
results and raw caches remain unchanged and untracked where this task found them.
`results.json` owns the per-file hashes, reconciliation checks, and provenance limits.

All eight saved records are internally consistent with the checked feasibility conditions.
The five `CARRIES` records contain three sessions each. Every saved action sequence matches
its raw cache responses, spends the registered budget at the registered prices, and has no
unanswered step or exit note. Reported call counts and usage reconcile with the raw caches.
The three `TOO_SHORT` records report intact text below the registered chunk floor and have
no saved reader sessions. No allocation contrasts were computed or interpreted.

This does not complete provenance verification. The committed registration specifies one
particular three-chapter draw; the saved screens cover several books with different chapter
counts, and no expansion amendment was found. The result files do not retain source-text and
competitor digests, while the raw caches retain request keys rather than complete requests
or acquisition timestamps. Present-day library files cannot silently replace those missing
historical inputs. File modification dates do not establish when an experiment was run.

The admissible conclusion is that the saved session records support their reported operational
feasibility, subject to those provenance gaps. They do not establish reader sensitivity,
literary quality, a current-pipeline result, or a production licence. A new arm must freeze its
own source material and controls before calling a reader. These records are not its null.

Rebuild from the existing local source files:

```powershell
.venv/Scripts/python.exe research/quality-measurement/volume-screen-audit-20260910/audit.py
```

The source records are not available from this audit's committed files alone. The derivation
records that limitation explicitly and does not stage another session's original work.
