# Recovered production baseline and scope correction

The recent 42-unit reconstruction is not the original production writer request. Production
generated the chapter in two scene calls. The original run retained both requests, raw
provider results, published chapter, starting world and the then-uncommitted source snapshot.
The complete source-free audit is retained under the investigation root and hashed in
execution.json. These are provenance findings, not evidence of literary quality.

The first-scene request is runs/ab/chapter-rule-context-20260905/request-4.json, SHA-256
4cb3c1292b764ed9087a43fbbd903f9848688a16e1ec3bf15b2d23802722b13f. It has a 12093-character
system and 34583-character prompt, with a 900-word scene target, writer dossier, house rules,
world/rule context, promises, open threads and scene plan. Its raw output is provider-4.json.
request-8.json is scene two and includes the published, mechanically cleaned first scene.
Replaying request 8 unchanged does not continue a newly generated scene one.

The base object in runs/ab/prose-inputs-reviewed-20260905/manifest.json is exactly request 4
with the two later world-truth/character-knowledge heading corrections. Its file SHA-256 is
eb6fec4ac85a98783e3493660a468b08dc69f6ad52a171e35ea5b10be4fa3418. This permits a future
matched subscription replay without regenerating the world or silently rebuilding context.
Both fresh arms would need the same transport, scene scope and output-cleanup policy. The
original provider's full internal prompt stack and historical argv are not retained.

Earlier prose-inputs manifests pair request 4 with source_scene containing the entire
two-scene published chapter. That is a request/output granularity mismatch. The archive
must not be described as one original whole-chapter production call. The later reconstruction
instead deliberately supplies the complete chapter's extracted facts to one writer.

Inspection of this production fixture's ordinary world/fact values did not locate the
experimental F-ID preservation guards. Production does mix presentation obligations with
story content in concept promises, open threads and the scene plan. Those are different
input roles; a structural change there requires an explicit new treatment. This separation
experiment does not license extracting imaginary editorial clauses from production facts.

Production cleanup is deliberate and tested: src/litharness/application/handlers.py applies
strip_em_dash and strip_prose_emphasis from src/litharness/domain/draft.py. The comparison shows changed
unbracketed display separators and removed emphasis/thought formatting. The repeated
explanatory constructions already exist in raw output. No clear newly introduced factual
or grammatical error was established in the inspected chapter. Globally disabling cleanup
would restore typography; it is not an evidenced cure for the prose pattern. Protection of
unbracketed displays is a narrower, separate fidelity question.

Future work should preserve these stage and scope identities. A new coherent chapter needs
its new first scene advanced through the application state before drafting the second;
possessing two old requests does not substitute for that progression. No production prompt,
cleanup policy or manuscript was changed by this audit.
