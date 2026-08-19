# The revision loop: reward-guided revision under composite scoring

**Status: specified, not funded, and not runnable.** No arm here may be bought until a *licensed*
axis exists — one an external human verdict has anchored (§80's batch, class B or class E) — and
§82's standing rule is the reason: no machine measurement upgrades a licence, so a loop that
optimises a machine score with no anchored axis under it is optimising our own vocabulary. This
document exists so that on the day an axis is licensed, the loop that gets built is the one the
measurements already argue for rather than the one that is easiest to write.

Written 2026-08-19 under stage-0 §89, on §87.1's oracle bound and §86's T3 design.

## 1. Why revision and not selection, with the number that decides it

Selection is the obvious loop: draw N, keep the best. §87.1 measured its ceiling and the ceiling is
low. For any axis, `E[best of N]` under an **oracle** selector is an order statistic of the
generator's own draws — no panel, probe or human can beat an oracle — so the curve is an upper
bound on every selector that will ever exist, computed by enumeration over §83's four-deep pool:

    axis                  E[best of 1..4] minus sober          oracle gain   one certified revision
    interiority (up)      +0.167 +0.524 +0.661 +0.711            +0.544       +1.608   (34%)
    prose em dash (down)  +0.296 -0.724 -1.305 -1.625            -1.921       -3.534   (54%)

**An oracle over four draws reaches a third of one certified revision on interiority and about half
of one on em dashes** — so a single certified revision is worth roughly 2.9x and 1.9x an oracle
best-of-4 on the two axes a human reader actually named. The increments decelerate hard (+0.357,
+0.137, +0.050), and the pool is four deep, so nothing is claimed about N=8..32; §87.4 priced that
extension at $59.30 and recorded it as the least informative purchase per dollar available, because
extending a ceiling refines it rather than moving it.

**The bound is on reach, not on value.** These axes are surface proxies, and an oracle over a proxy
is not an oracle over prose. What the table licenses is a *design* decision — put the budget in
revision rather than in draws — and not a claim that revised prose is better prose. That claim
needs §80.

## 2. The architecture

    draft
      -> composite score (§89 Track A2')          <- layer 1 counters, layer 2 frozen readout,
      -> select the worst-scoring licensed axis      layer 3 verdict protocol if one survived
      -> apply that axis's certified operator      <- single-variable, certificate-checked
      -> re-certify: reject the revision if the certificate fails
      -> re-score; keep if the target axis improved and no off-target axis degraded past budget
      -> repeat until no licensed axis is below threshold, or the Goodhart budget is spent

Three properties, each of which exists because something already went wrong without it.

**Single-variable operators.** Each operator moves one axis and is defined in terms of the quantity
that axis is measured by. §85 built three and certified them: em-dash removal by rewrite,
interiority addition, and a typo-fix placebo that came back byte-identical on all eight scenes. A
multi-variable rewrite cannot be attributed, and an unattributable improvement cannot be read
against a per-axis human anchor — which is the entire deliverable of §80's batch.

**Certificates, checked per revision and not per run.** §85's on-axis certificate is the model:
8 of 8 scenes had every prose em dash removed at word-similarity ≥ 0.978, growth ≤ 3.4%, and every
protected span byte-intact. A revision that fails its certificate is **rejected, not scored** — the
loop must never be able to buy an improvement by rewriting more than it was asked to.

**The placebo runs in the loop, not beside it.** §85's typo-fix returned byte-identical text, which
made its containment band zero-width and its compliance read 3/8 on deltas of one word's worth.
That defect is instructive rather than embarrassing: an inert operator is the loop's floor, and a
loop that "improves" a text under an inert instruction is measuring its own scorer's noise. The
placebo therefore takes a slot in every iteration's schedule.

## 3. The Goodhart budget, instrumented from iteration one

§86's T3 is the design and its honesty is the part to keep: with one reachable lineage, "held out"
degrades to a different tier of the same lineage, and a within-lineage T3 bounds **protocol
exploitation** while saying nothing about taste exploitation shared across the lineage. The loop
does not fix that. What it does is refuse to accumulate un-instrumented iterations.

Recorded at every iteration, from the first:

| measure | what it catches | independent of the scorer? |
| --- | --- | --- |
| the target axis's counter | did the operator do its job | yes — deterministic |
| every *other* B6 counter | single-variable violation | yes — deterministic |
| the axiom battery (§86.7) | drift into ties, length, format | **yes — it is not a judge** |
| word-count ratio, layout identity, protected spans | the §78 confound, below | yes — deterministic |
| the composite's own score | on-target progress | no, by construction |

**The axiom battery is the one fully independent off-target measure**, because it is not a judge: a
text optimised to please a scorer while drifting into ties, length or format is caught by it
whatever any judge thinks. It runs every iteration, not at the end.

**The confound this loop must separate in the same pass, because the ledger predicts it.**
Off-target scores can fall because the optimiser drifted length or layout rather than because it
exploited taste — §78 measured a 96–100% preference produced by layout alone, and §87's own
`rewhitespace_sham` is the same hazard in fixture form. So **an iteration that drifts the
deterministic certificate is reported as drift, never as exploitation**, and the two are never
summed into one number.

**One implication is checkable the day the budget lands and costs nothing.** `plan_search` runs K=3
candidates. If the measured budget is "divergence begins at N=2", the search this project already
ships is over budget on arrival. The comparison must be made in the same units — best-of-N against
a tournament of K — and stated in the entry that reports it.

## 4. Scoring, and the layer that may not exist

The loop scores with §89's composite, and its three layers are not interchangeable:

- **Layer 1, counters.** Deterministic, and they decide their own axes. An operator's target axis is
  always scored here, because the counter is what the operator is defined against.
- **Layer 2, the frozen readout.** `FROZEN_READOUT` (text_mean, layer 17), BEHAVIOUR-class evidence
  only, used to rank where counters are silent. It may never decide a preference: §82 classes it as
  behaviour at STORY grain and preference stays definitionally human.
- **Layer 3, verdicts.** Whichever elicitation protocol survived §89's Track E, if any. **If none
  survived, this layer does not exist and preference routes to the operator or to §80's batch** —
  which is §84 §6.4's floor and was always the fallback, not a failure state.

A loop running with no layer 3 is still a loop: it optimises named axes against counters with the
battery watching, and it declines to have an opinion about preference. That is a narrower machine
than the one this project wanted and it is the one the measurements support.

## 5. Kill conditions, declared before the first funded iteration

1. **No licensed axis** → the loop does not run. Not "runs on machine-licensed axes"; does not run.
2. **The certificate rejection rate exceeds 50% on any operator** → that operator is not
   single-variable on this material and is withdrawn, not re-tuned against the rate that withdrew it.
3. **The axiom battery degrades at any iteration** → the loop stops at the previous iteration and
   the entry reports the drift, per §86.7's both-readings rule.
4. **Divergence at N=2** → revision under this composite has no usable budget, `plan_search`'s K=3
   is over budget on arrival, and both facts are reported together.
5. **On-target rises only when the certificate drifts** → the gain is layout or length, §78's
   finding recurring, and the axis is reported as unoptimisable under this operator.

## 6. What it waits on

- [ ] One axis licensed by external human agreement (§80 class B, or class E's frontier).
- [ ] Panel v2 frozen and signed (§84), so the composite the loop scores with is fixed before the
      human numbers arrive and cannot be re-selected after them.
- [ ] §89's Track E verdict, which decides whether layer 3 exists at all.
- [ ] A T3 pressure budget measured in the same units as `plan_search`'s K.

Nothing here authorises a generation. The first funded iteration is an operator act.
