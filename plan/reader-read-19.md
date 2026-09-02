# The nineteenth operator read — pilot 24 in third person, two decisions, and the tells

**Status: DEFECT HARVEST, 2026-09-02. Not data (§95).** The operator read pilot 24's pair
(`plan/serial-pilot-24.md` §4 and §5), decided the person, asked for readers that recognise
order and meaning, named five items on *The Ratchet Counts Down*, and asked what it would take
to fix the tells. His words verbatim, the analysis ours.

## 1. The two decisions

> *Let's go with third person going forward.*

Recorded as the operator's position, replacing read 4 §3's first person (§195.2 shipped that
as a position, never a finding). Every draw from here is created without `--person first`,
which is the book as it was before that flag existed; the listing is asked in the third person.

> *We really need to fix the recognition of order of sentences and meaning for our readers.*

The readership's story-sensitivity: §195.5's finding was that the panel preferred a
paragraph-shuffled copy of ours over an anchor at the ordered copy's rate, and pilot 24's
`readers` lane carried on four of four on both chapters with no control beside it. The work is
registered instrument work (§3.2 below), not a prompt.

## 2. The five items

> *"for a hobby nobody understood" - ai tell (x nobody y) pattern*

> *"in front of everybody, and it had landed badly. He said it gentler now, which was his way
> of taking it back without taking it back." - ai tell, (x without x) pattern*

> *"Then the floor let go of the sound." - meaningless*

> *"Tull stopped anyway and looked, the way he always stopped and looked." - ai tell (x the
> way he/she/they always x)*

> *"hollows under the city" - wtf are hollows?*

> *We are still having lots of the same issues. What do you think we have to do to fix the
> tells? make it read more natural?*

### 2.1 Routed

- **Definition by absence** (*nobody understood*): the family every read since draw 1 of
  pilot 21 has counted, under four writers and both persons. Its clause (§179) was measured
  not to move it and left the floor in §187.
- **The paradox** (*taking it back without taking it back*): a new-named family, the same
  word repeated around *without*, a sentence that turns on itself; the *turned last line* of
  read 15's family in a smaller form.
- **A figure that fails a literal read** (*the floor let go of the sound*): read 15's F1
  family (*three shifts a day have walked flat*); a metaphor no reader can cash.
- **The located habit** (*the way he always stopped and looked*): §194's family, the manner
  gloss told where an act would show, named by reads 13 and 14 and given a clause on the
  reviser that is off.
- **The unmet term** (*hollows*): the world's own word for what it counts (the sheet prints
  *HOLLOWS SURVEYED*), used with no gloss in passing; read 16's E2 family from the world's
  side rather than the idiom's.

### 2.2 What nineteen reads say about the tells, together

Four of the five are regular. They have a shape a counter can find: a clause built on
*nobody / nothing / never*; the same word repeated around *without* or *not*; *the way* + a
person + *always*; a phrase repeated within one sentence; three *and*s chaining one sentence.
Every prompt-side lever has been pulled at them — five clauses on the house floor (§176 to
§181), measured by the agent-impact audit as moving no sentence metric and removed (§187);
three exemplars (§196), which moved the system's voice and the similes and not these; four
dossiers, which moved the frame and not these; the person flip, which removed the
first-person families and not these. They are the model's defaults and they survive
instruction. What has removed a tell in this house is code: the em-dash strip and the markup
strip took two tells off every page deterministically, and the listing's two rails redraw on a
counter. The tells that remain are one level up from a character: they need a sentence
rewritten, not deleted.

**So the fix is a located rewrite, and the counter is the whole mechanism** (§3.1): code finds
each sentence of a regular family, the shelf's own chapters set the ceiling per family (the
anchors carry these shapes at some rate, and that rate is the market's), a model is asked to
rewrite only the located sentence, code verifies the shape is gone and the sentence is still
there, and the decision row records what moved. Nothing in it asks a model whether a sentence
is good; nothing in it is a rule about prose in general.

The fifth item and the unmet term are not regular. *The floor let go of the sound* and
*hollows* need a reader who reads meaning, which is the operator's first sentence today; until
that reader exists (§3.2), they are counted.

## 3. What is built, in this order

### 3.1 The tells strip

`domain/tells.py`: the regular families as frozen patterns, a locator over sentences, a
per-thousand-words density per family, and the ceiling read off the shelf's chapters
(§196's operator-placed openings), so the number is the market's and moves when the shelf does.
A surgical pass on the drafting ladder beside the em-dash and markup strips: each located
sentence of a family over the shelf's ceiling is rewritten alone, verified by the same
locator, and left as drafted when two rewrites do not clear it; the acceptance event carries
the counts before and after. A gate that reports and never blocks. Measured by the next
third-person draw under pilot 24's concept and listing, the pass on, one change.

### 3.2 The readers' story-sensitivity control

Registered before spend: the `readers` lanes on one chapter, ordered against a
paragraph-shuffled and a sentence-shuffled copy, with §195.5's decision table; the measurement
lane's carry-on rate and the steering lane's expectations scored by code against the actual
continuation (the anticipation probe's frame, §124). A lane that carries on at the same rate
and predicts as well from a shuffled copy reads surface, and its verdicts stay a reading until
an instrument passes.

## 4. Anti-scope

No clause on the house floor or the scene prompt (§187). Nothing quoted here becomes prompt
text (§97.1): the families are patterns in code with the operator's items as test fixtures,
and the rewrite ask names a sentence and not a rule. No bar; the shelf's ceilings are
distributions before they are anything else.
