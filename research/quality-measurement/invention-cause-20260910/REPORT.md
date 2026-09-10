# Repeated invention: investigation record

This investigation follows the operator's request to improve debugging tools and find why
fresh books returned to aquatic repair premises. It diagnoses generation, not literary
quality. Raw requests, returned treatments, native traces and logs remain in the ignored
`runs/invention-cause-20260910/` directory. [evidence.json](evidence.json), derived by
[audit.py](audit.py), binds the observations below to first-response receipts and frozen inputs.

## Located stage

The repeated premise already exists in the first invention response, before concept
translation, planning, world management or chapter drafting. The two continuation-baseline
books received byte-equivalent serialized application requests and used distinct ephemeral
native sessions. Both immediately invented the recurring protagonist, mechanic, local
companion, nursery and water-repair setup. There was no preceding book in either request.

The comparison receipts are the baseline's `book-1/calls/002.json` and
`book-2/calls/001.json`; the complete-request digest is
`5c6b252e170ec4bc8ed5675b1fd49111b56bdccb8b833a673061b050e7f5cfdb`.
The historical trace search also finds aquatic Codex inventions at discovery v5, v6 and v7.
Those are unmatched historical cases, not independent controlled model comparisons. They
show that v8 is not the sole origin; they do not establish which older change caused it.

The minimal direct-provider experiments use no book store, writer dossier, library,
previous concept, diagnostic prose or corpus. The captured native system and user strings
contain no recurring names or water-setting requirement. That local data path can reproduce
the phenomenon without downstream production machinery.

## Phase 1: detailed instructions are not necessary

[Registration](registration.json), [protocol](RUNBOOK.md), [runner](run.py).

All eight slots completed and passed `Discovery.from_invention`. Both arms have exactly one
application input and one captured transport input; the only differing input field is the
system string. Configurations match. All eight sessions and output texts are distinct.

Reading all four full treatments found practical structural repair throughout: a violin
repairer, wheelchair mechanic, locksmith and a repair-oriented river crossing. Three have
central water hazards; the third treatment explicitly has a **dry** inland sea. Calling all
four water-world stories would erase that counterexample.

All four minimal treatments name Mara Venn. Three use a railway lost-property clerk, and
the fourth uses an elevator inspector. Two start with central aquatic settings; the other
two center on abandoned dungeons and supernatural weight. Restoration, ownership and
professional expertise recur across the set. Removing the detailed discovery instructions
therefore does not eliminate the broader repetition. It does not prove those instructions
have no influence, or identify a particular sentence as causal.

## Phase 2: changing the requested Codex model does not break the cluster

[Registration](phase2-registration.json), [protocol](PHASE2.md), [runner](phase2.py).

The nine slots completed with no transport stop. Eight inventions passed validation; Opus-1
used the reserved name `standing` and failed that application check. Its first response stays
in the record without a redraw or downstream development. The exact same
application request went to Astra, GPT-5.5 and Opus. The captured effective system, user
prompt and native schema also match across all three routes. Model/native configuration is
the manipulated boundary; the Claude contrast includes a different launcher and default
reasoning behavior. This is not a quality comparison or a ranking of models.

All three Astra controls and all three GPT-5.5 responses name Mara Venn. Astra returns a
railway clerk, lift mechanic and municipal locksmith. GPT-5.5 returns a ferry mechanic,
paramedic and locksmith. Water, repair/restoration and institutional rule conflicts recur,
with non-aquatic counterexamples retained. This refutes an Astra-only explanation on these
draws.

Opus returns three different named protagonists: Theo Varga, Delphine Aroyo and Grigor
Hale. Their premises concern a lifespan-collection apocalypse, a world-transcription boundary
and a tuning apocalypse. They also rely on professional expertise, costly rescue and
institutional or systemic conflict. Opus breaks the exact repeated-name cluster, but it does
not establish that every broader craft/profession motif is unique to Codex.

## Native framing and its evidence limits

The installed catalog has different message templates and transport metadata for Astra and
GPT-5.5. A read-only search of their full catalog entries found none of the literal terms
Mara, Venn, Esh, water, repair, LitRPG or railway. Absence of those words does not establish
absence of an indirect influence.

Codex documents [replacement model instructions and model catalogs](https://learn.chatgpt.com/docs/config-file/config-reference)
and a [debug prompt-input command](https://learn.chatgpt.com/docs/developer-commands?surface=cli).
The local debug command rejects exec's `--ignore-user-config` and `--ignore-rules` flags.
An offline reconstruction instead used an empty unauthenticated state directory with a
copied catalog. It shows differing supplemental instructions, including collaboration and
agent-role framing, but is not a captured request from the controlled completions. Its
command and outputs are retained as `prompt-input-*.json`. No generation occurred in these
offline inspections.

Changing requested model can select different native metadata as well as a different model.
The receipts do not report Codex's backend-resolved model or resolved sampling parameters.
The evidence therefore supports requested-route comparisons, not a claim to have isolated
model weights or a backend temperature. [Phase 3](PHASE3.md) tests the native template prose.

## Debugging tools

[tools/generation_trace.py](../../../tools/generation_trace.py) reads saved files without
opening a store or selecting a provider. It inventories application and transport hashes,
groups shared sessions and repeated outputs, compares fields/configuration separately,
locates literal or regex matches, and explicitly displays complete fields. It understands
legacy discovery traces, prepared requests, completion receipts, native Codex traces and
separately captured Claude launches. Failed stdout can retain useful events despite warning
or truncated lines. Missing transport/configuration remains unknown; marked exemplar inputs
remain withheld even when an explicit display is requested.

```powershell
uv run python tools/generation_trace.py inventory runs
uv run python tools/generation_trace.py search runs --query "water"
uv run python tools/generation_trace.py compare first-call.json second-call.json
uv run python tools/generation_trace.py show first-call.json --field output.text
```

Use `--glob '*.json'` for a directory of call receipts; the default directory pattern selects
`discovery-trace.json`. Search hits locate text, not semantic categories. Equal bytes, shared
sessions and repeated premises answer different questions. The debug-book skill now points
to this workflow. Regression coverage is in
[tests/test_generation_trace.py](../../../tests/test_generation_trace.py).
