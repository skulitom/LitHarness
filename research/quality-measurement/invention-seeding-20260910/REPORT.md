# Creative seeding trial

The seed controls an authored brief, not the native sampler. The initial trial found useful
control of premise ingredients, with substantial repetition still present in how powers were
used. An opaque identifier alone did not escape the aquatic repair premise in these examples.

## Initial comparison

The [registered protocol](RUNBOOK.md) compared three empty briefs, three opaque identifiers,
and three ingredient packets repeated twice. Every first response was retained. The
[audit record](evidence.json) records twelve successful calls, twelve distinct native sessions,
twelve different output hashes, matching prepared requests, no frozen-file drift and 71,291
recorded tokens. All passed `Discovery.from_invention`; that is structural validation, not
quality evaluation. Each repeated packet reached the transport with identical inputs and
configuration. The system, schema and non-prompt parameters matched across conditions.

These are whole-treatment observations, with source locations under
`runs/invention-seeding-20260910/calls/`. Every item is retained in call order in the local
[treatments file](../../../runs/invention-seeding-20260910/TREATMENTS.md).

| Calls | Protagonist and situation | First useful magic and continuing pattern |
| --- | --- | --- |
| control-1 | Maintenance worker Mara rescues her brother and dog among living shells. | Load-sharing supports a rescue; hidden nursery damage requires a different anchor. |
| control-2 | Bridge inspector Mara rescues her brother from a drifting landing on a shellback sea. | Load perception and shared bearing support the rescue after a breathing-fold repair. |
| control-3 | Furniture restorer Nessa follows her separated sister through a rising-tide basin. | A wheel repair earns a strain-transfer skill used on a ferryman's body and steering. |
| nonce-1 | Bicycle mechanic Mara rescues her brother from a cage in inhabited reservoirs. | Joining a fractured crank threatens a linked nursery gate; overload requires another route. |
| nonce-2 | Boatyard repairer Mara retrieves her brother in a sea of moving tides. | Hull repair earns trim control; limited buoyancy forces her to discard belongings. |
| nonce-3 | Boat repairer Nessa rescues her father in a broken canal network. | A bypass repair earns tension-routing magic; a weak anchor changes the rescue. |
| ingredients-0-a | Exiled dragon Keshet contests a moving-island inheritance and seeks companion Mara on his sister's fleet. | A torn wing earns strain hearing; he uses it to traverse moorings, then diagnose an engine support. |
| ingredients-0-b | Exiled dragon Talren seeks companion Sere during his sister's island siege and inheritance claim. | A crushed leg earns rigid load-bearing; he props a hatch and anchors against pump currents. |
| ingredients-1-a | Pilgrim Mara Venn robs a memory broker while her holy destination hunts her through nightmare markets. | A burned eye reveals crossing-light trails, exposing a chapel anchor she removes with a lever. |
| ingredients-1-b | Pilgrim Mara Venn tries a memory theft and takes a counteroffer against her pursuing holy destination. | A crushed ankle earns backward threshold crossing, used to steal the collector's warrant. |
| ingredients-2-a | An unnamed duelist wearing Captain Saren Voss's identity seeks an erased revenge warrant during a siege. | A stolen shadow attacks him under its owner's orders; negotiated manifestation braces rubble and an escape gate. |
| ingredients-2-b | Sera Venn wears Captain Iven Rusk's stolen shadow to recover an execution record during a siege. | A solid shadow hand braces rubble and operates seals and a sluice; the owner's voice takes control. |

The `world`, `opening` and `growth` fields in each named receipt contain the complete source.
The search offsets in the audit locate literal vocabulary; they do not classify a treatment.
In particular, the island ingredient explicitly supplies an aquatic setting, so its retention
is input adherence, not evidence that a non-aquatic instruction was ignored.

All three empty-brief and all three identifier-only responses retain aquatic settings,
practical repairers, structural magic and family rescue. Names and local mechanics vary.
The three ingredient pairs preserve recognizably different protagonist types, settings,
central pursuits and specified power constraints. They therefore show useful premise control.
However, the dragon powers become strain hearing or load-bearing, and both shadow duelists'
early rewards support damaged structures. The two nightmare pilgrims are both named Mara Venn.
Across conditions, nursery communities, threatened passages and negotiated rescue recur.
The input method has not demonstrated freedom from this broader family of model choices.

The [first-use follow-up](action-followup/RUNBOOK.md) adds a specified combat success to the
shadow-duelist packet. It is a separate, post-hoc two-response test of a more prescriptive
author brief. Its registration precedes its calls; it does not replace the initial results.

## Use and limits

`tools/invention_seed.py` creates reproducible briefs without a model call:

```bash
uv run python tools/invention_seed.py --seed my-series --count 3 --out runs/my-seeds
```

Pass a generated brief through the existing `concept --brief-file` option. Increment `--start`
to take new positions from the same seed's finite deck. Distinct positions have distinct
ingredient combinations; different labels can overlap. The same label and index reproduce
the input, not necessarily the model's story. The authored eight-option axes are an explicit
constraint of this experimental tool, not a representative sample of fiction.

The initial comparison is not length-matched, uses one requested model and contains only
three packet combinations. Native receipts do not disclose every backend instruction or the
resolved sampler. Input adherence does not establish reader appeal, global originality or
distance from a training distribution. No response was ranked, selected or developed into
a book; production generation defaults remain unchanged.
