# Generalizing fictional progression

**Status:** research report  
**Date:** 2026-08-21  
**Source brief:** `plan/research-progression-generalization.md`  
**Purpose:** provide an implementation-independent ontology for capability change in fiction,
including worlds with several progression systems, worlds with non-combat progression, and worlds
with no declared progression system at all.

---

## Executive conclusion

The core abstraction should not be a ladder, character sheet, ability list, or resource ledger. It
should be a **contextual transition system over a qualified state graph**.

The decisive definition is:

\[
\operatorname{Reach}(x,W)=
\{(a,y,c)\mid a\text{ is possible and authorized for }x
\text{ against target }y\text{ in context }c\text{ under world state }W\}.
\]

Progression is a narratively significant change in one or more of:

1. the subject's reachable actions;
2. the constraints or costs on those actions;
3. how an authority evaluates or recognizes the subject;
4. what the subject, other characters, or the reader understands about that state.

This admits upward, downward, lateral, cyclical, transferred, collective, involuntary, and
misrepresented progression without making any one of them a special case.

It also gives the following reductions:

- An **ability** is an affordance, or a named bundle of affordances, not an intrinsic scalar.
- A **rank** is an evaluation result under a criterion, not an intrinsic property of a person.
- A **cost** is an adverse effect of a change, not necessarily a currency.
- A **carrier** is an entity whose possession changes action preconditions.
- A **bond** is a composite subject whose capabilities need not be the union of its members'.
- An **agency** is an ordinary entity occupying roles such as authorizer, validator, grantor, or
  narrator.
- An analytic **progression regime** is a named bundle of rules, criteria, changes, and views. It
  need not correspond to a diegetic System.
- A game-like System lying about reality is a **view over another regime**, not a second causal
  engine.

The existing LitHarness record shape can carry this model through reified relation and event
records. The important implementation work is semantic: active-state projection, scoped
cardinality, comparison functions, and the separation of truth, belief, disclosure, and operational
visibility.

---

## 1. Falsification: where the proposed core stops

This section comes first because arbitrary JSON can make an ontology appear universal. Putting an
uninterpreted description in `value` is storage, not modelling. The small core proposed in this
report cannot **checkably** express the following systems.

| Real system | What the core cannot express | What it would cost to admit |
|---|---|---|
| Bayesian Knowledge Tracing | It can store `P(mastery)=0.72`, but it cannot represent conditional dependence, guessing, slipping, or posterior updates. | A probabilistic factor layer, update semantics, and an inference backend. |
| Factorio's production network | It can represent technologies and unlock events, but cannot derive them from continuous concurrent flows, unit conversion, or conservation. | Typed quantities, units, flow graphs, and a simulator. |
| Roguelike and time-loop histories | A single scalar story order cannot distinguish local reset time, persistent meta-time, and incompatible prior cycles. | Explicit context or branch identity, a partial temporal order, and cross-context persistence rules. |
| [Nomic][nomic] | Rule records can say that a rule changed, but a fixed evaluator cannot safely interpret rules that rewrite the rule-changing and evaluation semantics themselves. | Versioned executable meta-rules, precedence strata, and paradox/conflict handling. |
| Institutional or biological fission and fusion | Stable subject IDs do not decide whether a merged guild, divided sect, rebuilt ship, or successor lineage is the same progressor. | Temporal mereology and an explicit identity-continuity policy. |
| Tacit craft and conceptual depth | The graph can record a claimed breakthrough and its consequences, but cannot reliably decide from prose alone that the claim is genuine new understanding rather than paraphrase. | Semantic entailment and prediction probes, probably advisory rather than blocking. |
| Latent expertise versus public rating | FIDE rating movement is expressible; underlying chess ability is not directly observable or identical to the rating. | A measurement model separating observations, estimates, uncertainty, and latent state. |
| Continuous embodied transformation | Snapshots can describe training and bodily change, but cannot reproduce continuous physiology, fatigue, injury recovery, or chaotic sensitivity. | A hybrid dynamical system or domain simulator, far outside a prose continuity store. |

These are deliberate limits. The recommendation is not to enlarge the first implementation to
absorb them. The progression model should record their narratively established states while openly
refusing simulation or inference claims it cannot support.

---

## 2. Method and evidence base

The survey used five kinds of evidence:

1. **Formal game rules**, because they make advancement procedures explicit and reveal competing
   definitions of what counts as growth.
2. **Video and board-game systems**, because they expose access gating, collection, reset loops,
   technology graphs, and possession-based capability.
3. **Real credential, rank, and rating systems**, because they separate competence, recognition,
   legal authorization, office, and public estimates.
4. **Learning and expertise research**, because it supplies non-fictional accounts of depth,
   representation change, latent mastery, practice, failure, and breakthrough.
5. **Published fiction**, including works without a diegetic progression interface, to check that
   the resulting model is useful for prose rather than only for formal games.

The matrix axes were derived after comparing the cases. They were not treated as starting
assumptions.

### 2.1 Survey axes

- **Subject:** individual, composite, collective, institution, place, or world.
- **Geometry:** chain, vector, graph, threshold, cycle, estimate, or conceptual rewrite.
- **Operator:** add, unlock, replace, reset, revoke, transfer, revise, or re-estimate.
- **Authorization:** automatic rule, choice, use or failure, peer judgment, inference, or
  institution.
- **Direction:** monotone, reversible, cyclical, declining, or a trade among incomparable values.
- **Capability locus:** intrinsic, relational, possessed, recognized, collective, legal, or latent.
- **Cost:** resource, effort, opportunity, loss, maintenance, risk, or none made explicit.
- **Persistence and legibility:** stable, conditional, renewable, run-local, hidden, inferred,
  observable, or public.

---

## 3. Survey matrix

Codes used below: `I` individual, `C` composite or collective, `W` world or place; `↑` monotone,
`↕` reversible, `↻` cycle, and `⇄` trade or reconfiguration.

### 3.1 Tabletop role-playing games

| System | Subject | Geometry | Main operator | Authorization | Direction | Capability locus | Cost or trade | Persistence / legibility |
|---|---:|---|---|---|---:|---|---|---|
| D&D advancement | I | Chain plus branches | Accumulate and unlock | XP threshold or milestone | ↑ | Intrinsic | Branch opportunity | Stable, exact and public |
| Basic Roleplaying | I | Skill vector | Use, train, and research | Experience test or teacher | ↕ | Intrinsic | Time and risk; bad teaching can reduce skill | Stable, exact |
| Fate Core | I+W | Partial order and reconfiguration | Replace or add | Story milestone plus choice | ⇄/↑ | Intrinsic and relational | Refresh and opportunity | Stable, public |
| Blades in the Dark | I+C | Tracks, vector, and crew tier | Add and unlock | Risk and identity triggers | ↑ with scars | Intrinsic and collective | Stress, trauma, and vice | Persistent, public |
| Dungeon World | I+C | Level chain plus move choices | Unlock and replace bonds | Failure and session review | ↑/⇄ | Intrinsic and relational | Risk and failure | Stable, public |
| Year Zero Engine | I | Skill vector and specialties | Purchase after use or teaching | GM, success, or teacher | ↑/⇄ | Intrinsic | XP, time, and teacher | Stable, public |

The formal contrasts are visible in the published rules: [D&D levels][dnd], [Fate milestones and
equivalent reconfiguration][fate], [BRP use and training][brp], [Blades character and crew
advancement][blades], [Dungeon World advancement][dungeon-world], and the [Year Zero Engine
SRD][yze].

### 3.2 Video and board games

| System | Subject | Geometry | Main operator | Authorization | Direction | Capability locus | Cost or trade | Persistence / legibility |
|---|---:|---|---|---|---:|---|---|---|
| Factorio | C/force | Technology DAG plus infinite tails | Research and unlock | Resource consumption or trigger | ↑ | Collective and world access | Material, time, and opportunity | Stable, public |
| Metroid Dread | I+W | Access graph | Acquire and unlock | Discovery or defeat | ↑ | Relational to environment | Exploration and opportunity | Stable, experiential |
| Slay the Spire | I/run | Cycle plus deck vector | Add, remove, and reset | Reward choice and run end | ↻/⇄ | Possessed | HP, deck dilution, and opportunity | Run-local plus persistent unlocks |
| Dominion | I/deck | Cyclic multiset | Buy, trash, and reconfigure | Player choice | ⇄ | Possessed | Opportunity and draw dilution | Game-local, public |
| Gloomhaven | I+C+W | Levels, unlock graph, and succession | Advance, retire, and inherit | XP and personal quest | ↑/reset | Intrinsic and campaign-level | Loss of character and opportunity | Campaign-persistent, partly hidden |
| Civilization VI | C/W | Technology and civic DAGs | Research, boost, and unlock | Accumulation plus eurekas | ↑ | Collective and world | Research opportunity | Stable; optionally concealed |

These cases are documented by the [Factorio technology rules][factorio], [Metroid Dread's
access-gating description][metroid], [Slay the Spire][slay], [Dominion rules][dominion],
[Gloomhaven][gloomhaven], and [Civilization VI's shuffled and concealed technology-tree
rules][civ].

### 3.3 Real institutions, ratings, and credentials

| System | Subject | Geometry | Main operator | Authorization | Direction | Capability locus | Cost or trade | Persistence / legibility |
|---|---:|---|---|---|---:|---|---|---|
| FIDE rating | I | Numeric estimate | Re-estimate | Recorded results and formula | ↕ | Recognized estimate | Competitive risk | Public, continuously updated |
| English apprenticeship | I+institution | Competence threshold | Train, assess, and credential | Employer, assessor, awarding body | ↑/retry | Intrinsic target plus recognition | Time and effort | Public credential |
| UK higher-education qualification | I+institution | Named ordinal thresholds | Assess and award | Degree-awarding body | ↑ | Recognized, partly competence | Time, cost, and opportunity | Stable award |
| GMC licence to practise | I+institution | Renewable threshold and cycle | Revalidate, defer, or withdraw | Appraiser, responsible officer, GMC | ↕/↻ | Legal authorization | Maintenance and evidence | Conditional, public |
| British Judo grades | I+institution | Ordered grades plus syllabus | Examine and promote | Authorized examiner | ↑ | Skill plus recognition | Training and examination | Stable, visibly legible |
| British Army officer promotion | I+institution | Rank chain with selection | Appoint and promote | Selection board and command | ↑/conditional | Office and authority | Vacancy, time, and competition | Public rank |

These cases matter because they refuse a common fictional conflation. A person may become more
competent without being recognized, receive an office without yet being competent in it, retain
skill while losing legal authorization, or receive a rating update without any instantaneous
change to latent ability. Sources are [FIDE][fide], [apprenticeship assessment guidance][apprentice],
the [QAA qualifications framework][qaa], [GMC revalidation][gmc], [British Judo grading][judo],
and [Army promotion regulations][army].

### 3.4 Learning and expertise research

| System or theory | Subject | Geometry | Main operator | Authorization | Direction | Capability locus | Cost or trade | Persistence / legibility |
|---|---:|---|---|---|---:|---|---|---|
| Deliberate practice | I | Vector and learning curve | Targeted repetition and feedback | Performance evidence | ↑ with plateaus | Latent and intrinsic | Effort, fatigue, and motivation | Behaviourally inferred |
| Expert chunking | I | Representation rewrite | Reorganize perceived patterns | Practice and exposure | ⇄/depth | Latent | Time and practice | Inferred through tasks |
| Conceptual change | I/group | Concept graph rewrite | Replace, reconcile, and reorganize | Evidence, intelligibility, plausibility | ⇄ | Latent and relational | Cognitive conflict | Inferred from explanation |
| Threshold concepts | I | Threshold and depth | Integrate and reframe | Understanding | ↑, often treated as irreversible | Latent | Liminal difficulty | Inferred |
| Bayesian Knowledge Tracing | I | Latent-state posterior | Probabilistic update | Inference from answers | Model-↑ | Latent estimate | Practice | Hidden and probabilistic |
| Retrieval practice | I | Retention curve | Retrieve and test | Performance evidence | Short-term cost, long-term ↑ | Latent | Effort and failure | Inferred from later recall |

These rows draw on [deliberate practice][ericsson], [chess chunking][chase-simon], [conceptual
change][posner], [threshold concepts][thresholds], [knowledge tracing][bkt], and [retrieval
practice][retrieval]. The important finding is that expertise is often a change in representation,
selection, or prediction rather than a larger stored quantity.

### 3.5 Prose stress tests

These works are used as structural examples, not stylistic anchors.

| Work | Mechanism that stresses the model | Finding |
|---|---|---|
| Will Wight, *Cradle* | Named tiers, specialized Paths, sects, resources, and breakthroughs | Tier ladders are useful presentations but insufficient as the general geometry. |
| Brandon Sanderson, *The Stormlight Archive* | Oath stages, bonds, externally granted capability, ideals, and possible revocation | Bond capability belongs to a composite relation; advancement can be authorized by enacted commitments. |
| Domagoj Kurmaic, *Mother of Learning* | Repeating local history with persistent learning and changing knowledge | A loop needs local time, meta-time, and cross-context persistence. A scalar story position is insufficient. |
| J. R. R. Tolkien, *The Lord of the Rings* | A transferable carrier grants capability while imposing corruption and loss | Possession, capability, cost, and identity change are distinct relations; acquisition is not unqualified improvement. |
| Ursula K. Le Guin, *A Wizard of Earthsea* | Names, restraint, balance, and deepening understanding | Depth and judgment can matter more than breadth; greater capability may produce greater refusal to act. |
| Susanna Clarke, *Jonathan Strange & Mr Norrell* | Scholarly reconstruction, competing theories, performance, and institutional recognition | Knowledge, practice, authority, and recognition progress on different schedules. |
| Walter Tevis, *The Queen's Gambit* | Practice, chess performance, reputation, competition, and psychological cost | Skill, rating, public recognition, and momentary performance must remain separate. |
| Katherine Addison, *The Goblin Emperor* | Office is acquired immediately while social and political competence develops slowly | Rank can change before capability; institutional authority is an affordance granted by a relation. |

Two conclusions follow from prose. First, the analytic model must not require the story to have a
diegetic System. Second, a capability model must include socially and legally authorized actions,
not only physical or magical actions.

---

## 4. Formal model

### 4.1 Qualified active state

Let `Record` have the required form:

```text
(subject, predicate, object, value, story-position, authority, visibility)
```

Let \(W_t^c\) be the active canon at story position \(t\) in story-world context \(c\). It is the
set of accepted or author-locked records after applying:

- story-world validity intervals;
- supersession and retraction effects;
- context or branch scope;
- truth authority;
- but **not** character knowledge or reader disclosure.

The current LitHarness `story_position` records where a fact was established or an event occurred.
It is not sufficient by itself to say for how long a state remains true.

### 4.2 Progression regime

An analytic progression regime is:

\[
P=(Q,T,C,\mathcal E,O)
\]

where:

- \(Q\) selects the state facts governed by the regime;
- \(T\) is a set of change schemas and recorded change occurrences;
- \(C\) is a set of constraints;
- \(\mathcal E\) is a set of evaluation criteria and comparison relations;
- \(O\) is an optional set of views or interfaces from substrate state into claims.

A regime is an analytic scope, not necessarily a fictional entity. A cabinetmaker's learning can
be modelled as a regime even though the story contains no System, magic, or explicit rules screen.

A world with no progression declares no such bundle. Ordinary story facts remain ordinary facts.

### 4.3 Evaluation and direction

For criterion \(q\):

\[
\phi_q(x,W_t)\in D_q,
\]

where \(D_q\) may be:

- an ordered set of named ranks;
- a real or integer estimate;
- a set of reachable actions;
- a credential or authorization state;
- a concept graph;
- a vector of competing values;
- or a posterior estimate.

The comparison relation \(\succeq_q\) is normally a preorder and may be partial. Strict progress
under that criterion is:

\[
\phi_q(x,W_{t_2}) \succ_q \phi_q(x,W_{t_1}).
\]

The model does not require every progression arc to be monotone. It instead records an ordered path
of changes:

\[
W_0 \xrightarrow{e_1} W_1 \xrightarrow{e_2} \cdots \xrightarrow{e_n} W_n.
\]

The path is narratively progressive if relevant reachability, evaluation, cost, identity, or
understanding changes. Which changes count as desirable remains criterion-relative.

### 4.4 Capability as reachability

\[
\operatorname{Reach}(x,W)=
\{(a,y,c)\mid
\operatorname{pre}(a,x,y,c,W)\land
\operatorname{authorized}(a,x,y,c,W)\}.
\]

This single definition handles:

- **access gating:** an ability makes a door or region reachable;
- **legal authority:** a licence makes prescribing authorized even if physical skill is unchanged;
- **office:** a rank makes commands institutionally effective;
- **possession:** a tool or card satisfies an action precondition;
- **bonding:** the actor is a composite entity;
- **team competence:** the action requires a set of roles rather than one individual;
- **decline:** previously reachable actions disappear or become more costly;
- **specialization:** some actions appear while alternatives disappear;
- **understanding:** the subject can make a prediction, explanation, or distinction previously
  unavailable.

### 4.5 Change

A recorded change occurrence is:

\[
e=(participants,roles,preconditions,effects,authorized\_by,validated\_by,recognized\_by).
\]

Effects may:

- assert or retract a state;
- enable or disable an action;
- transfer possession or knowledge;
- consume or produce a resource;
- change an evaluation;
- disclose or conceal a claim;
- supersede a prior assertion.

A cost is not a separate primitive. It is an effect evaluated negatively under at least one
criterion. This catches costs paid by someone other than the beneficiary and costs that are
qualitative, delayed, or permanent.

### 4.6 Truth, belief, disclosure, and operational visibility

At least five layers must remain separate:

1. **substrate truth:** what canon says is true in context;
2. **character knowledge:** what a particular character knows;
3. **character belief:** what a character believes, including false content;
4. **reader disclosure:** what the narration has made available to the reader;
5. **operational visibility:** what the drafting pipeline may put into a particular packet.

The current `pov_visibility` is useful for layer 5. It should not be treated as a complete model of
layers 2–4.

A false belief is canon as a belief relation:

```text
(mara, believes, claim-17, ..., s4, accepted-canon, ...)
```

The content of `claim-17` need not be substrate truth. Likewise, a hidden system personality is a
truth claim that has not yet been disclosed, not a fact that is invented at reveal time.

---

## 5. Minimal primitive set

The existing qualified record and referenceable subject are the substrate. Above it, only four
first-class patterns are recommended.

| Primitive | A case that requires it | A case that works without an explicit instance | How prose makes it legible |
|---|---|---|---|
| **Change** | Gloomhaven retirement simultaneously removes a character, unlocks content, and advances campaign prosperity. The conjunction needs one occurrence identity. | A FIDE rating history can be represented as successive evaluations derived from recorded games. | A causal before-and-after episode. |
| **Constraint** | Fate's skill columns, Metroid's environmental gates, licences, exclusions, and possession limits. | A descriptive history of chess ratings needs no declared prerequisite rules. | A failed attempt, threshold, prohibition, prerequisite, or exception. |
| **Criterion** | FIDE rating order; Fate's distinction between equivalent reconfiguration and greater capability. | Metroid acquisitions can be stored directly as changed access relations without printing a rank scale. | New tasks, changed treatment, improved predictions, or foreclosed alternatives. |
| **View** | A lying System, concealed magic, reader/character knowledge gaps, and latent mastery estimates. | Factorio's ordinary technology interface can be treated as a faithful public display. | Misunderstanding, concealment, interface output, dramatic irony, or reveal. |

### 5.1 Candidate reduction and cut log

| Candidate primitive | Decision | Reduction |
|---|---|---|
| System | Cut as a primitive | A named bundle or scope over ordinary records. |
| Ability | Cut | A named affordance or set of reachable actions. |
| Rank | Cut | An evaluation result under a criterion. |
| Ladder | Cut | An ordered criterion domain; many criteria are not total orders. |
| Tier | Cut | An ordinal result plus a presentation or recognition pattern. |
| Depth rung | Cut | A claim plus a non-entailment and consequence relation to earlier claims. |
| Cost | Cut | An adverse change effect under some criterion. |
| Resource | Cut | A state quantity constrained by production, consumption, or conservation rules. |
| Carrier | Cut | An entity plus possession and affordance-precondition relations. |
| Collection | Cut | Set membership plus a completeness criterion. |
| Bond | Cut | A composite subject with member relations and emergent rules. |
| Agency | Cut | An ordinary entity playing causal, authorizing, validating, or recognizing roles. |
| Credential | Cut | A recognition or authorization state issued by an institution. |
| Breakthrough | Cut | A change satisfying a hurdle and altering an evaluation or reachability set. |
| Hurdle | Cut | A promised or active precondition not yet satisfied. |
| Appearance | Cut | Evidence or presentation attached to an evaluated state. |
| Personality/aesthetic | Cut | Optional state of an agency that may shape rules or granted affordances. |

The cuts matter. A palette of named fictional objects would be easy to use for one serial and hard
to generalize. The four retained patterns describe what those objects do.

---

## 6. Relation vocabulary and arity

### 6.1 Why global predicate arity is wrong

The earlier hypothesis proposed that `held_by`, `holds_rank`, and `bonded_with` were globally
functional. That solves the immediate contradiction bug but does not generalize.

- An exclusive magic card may have one holder.
- A workshop can be jointly owned.
- Shares can have fractional owners.
- A subject can have one rank per ladder but several ranks across ladders or jurisdictions.
- A bond may be unique in one world and plural in another.

Correct cardinality is scoped:

\[
\operatorname{count}
\{o\mid (s,p,o)\in W_t
\land \operatorname{scope}(s)
\land \pi_K(record)=k\}
\le m.
\]

It depends on:

- a predicate or role;
- a world, regime, or subject-type scope;
- a grouping key;
- a validity context and overlapping interval;
- a minimum or maximum count.

There should therefore be two layers:

1. fixed structural arity for ontology record kinds;
2. world-declared scoped cardinality for fictional facts.

This follows the mature ontology pattern of reifying relations that need roles or qualifiers and
expressing cardinality through explicit shapes. See the W3C [n-ary relation pattern][nary] and
[SHACL cardinality constraints][shacl].

### 6.2 Vocabulary

| Relation | Arity | Meaning of violation |
|---|---:|---|
| `bundle_member` | Multi | None; regimes contain many rules and a record can belong to several analytic bundles. |
| `member_of` | Multi | None; entities may belong to several compounds, sets, or institutions. |
| `participant` | Multi | None; changes can be collective. |
| `actor` | Multi | None; collaboration is ordinary. |
| `beneficiary` | Multi | None; one event can benefit several subjects. |
| `authorized_by` | Multi | None; joint or layered authorization is valid. |
| `validated_by` | Multi | None; several parties may attest the same result. |
| `recognized_by` | Multi | None; institutions may disagree. |
| `caused_by` | Multi | None; causal contribution is not assumed exclusive. |
| `precondition` | Multi | None; conjunction or alternative grouping must be explicit. |
| `effect` | Multi | None; changes normally have several effects. |
| `consumes` / `produces` | Multi | None; conservation is a separate constraint. |
| `transfer_leg.source` | Functional | Multiple sources require separate legs or an explicitly aggregated source entity. |
| `transfer_leg.target` | Functional | Multiple targets require separate legs or a distribution entity. |
| `evaluation.subject` | Functional | Two subjects make the evaluation malformed; use separate evaluations or a composite subject. |
| `evaluation.criterion` | Functional | A composite criterion must be represented by one criterion node. |
| `evaluation.result` | Functional | Two results in one context and interval are contradictory or an unresolved estimate. |
| `claim.content` | Functional | Multiple contents make claim identity ambiguous. |
| `claim.held_by` | Multi | Shared belief or knowledge is ordinary. |
| `claim.disclosed_to` | Multi | The same claim may be disclosed to several audiences. |
| `view.substrate` | Multi | An interface may aggregate several underlying regimes. |
| `view.mapping` | Multi | A view normally contains many correspondences. |
| `constraint.predicate` | Functional | Compound formulae should be separate formula nodes. |
| `constraint.minimum` / `maximum` | Functional | Multiple bounds need reconciliation before enforcement. |
| `constraint.group_key` | Functional | Ambiguous grouping makes cardinality findings non-reproducible. |
| `possessed_by` | Multi by default | Exclusivity is enforced only by a scoped maximum-count rule. |
| `bonded_with` | Multi by default | Unique bonds are world rules, not ontology truths. |
| `supersedes` | Multi | Merges and corrections may supersede several assertions. |

Minimum counts require a closed-world decision. Under open-world semantics, a missing value is
unknown rather than necessarily false. The OWL distinction between open- and closed-world
assumptions is directly relevant here: [absence in an OWL graph may mean missing, not false][owl].

---

## 7. Interaction rules for multi-system worlds

For regime \(P_i\), let \(R_i\) be the predicates it reads and \(W_i\) the predicates it changes.

### 7.1 Independent product

\[
W_i\cap(R_j\cup W_j)=\varnothing
\quad\text{and}\quad
W_j\cap(R_i\cup W_i)=\varnothing.
\]

The regimes' changes commute. Magic and professional reputation might coexist without
interaction.

### 7.2 Coupling

One regime reads or changes another's domain. Body cultivation might reduce the cost of magic
without granting magical techniques.

### 7.3 Interference

A change in one regime invalidates a precondition in another. Using one magic might make the body
temporarily unable to cultivate.

### 7.4 Exclusivity

A declared constraint makes the joint state unsatisfiable. Exclusivity must never be inferred only
because two regimes have different aesthetics, vocabularies, or agencies.

### 7.5 Conversion

A mapping \(f_{ij}:D_i\rightarrow D_j\) converts state or resources. It must specify:

- what is conserved;
- what is lost;
- whether conversion is reversible;
- which authority recognizes the result;
- whether the conversion changes substrate capability or only its evaluation.

### 7.6 Dominance or override

When rules conflict, a declared priority, jurisdiction, or authority resolves the conflict. There
is no default rule that the numerically stronger or older system wins.

### 7.7 Composition

A new composite subject receives emergent rules. A bonded pair, crew, sect, institution, or ship is
not merely the union of member sheets.

### 7.8 Recognition

One regime evaluates another without causing it. A licence, belt, military rank, school grade, or
reputation may diverge from underlying competence.

### 7.9 View, mask, or lie

Let substrate regime \(H\) have actual state \(s\). An interface displays:

\[
i=h(s,history).
\]

The mapping may be faithful, delayed, lossy, many-to-one, selectively concealed, fabricated, or
causally misrepresented.

Rules for the lie-about-another case:

1. Effects happen once, on the substrate.
2. Interface changes without substrate changes are presentation or interpretation changes.
3. Equal labels across regimes have no shared meaning without an explicit mapping.
4. A reveal changes disclosure, not past truth.
5. A false causal claim about the interface is represented separately from the interface itself.
6. Several interfaces may project the same substrate.
7. A displayed level-up is not progression if neither substrate reachability nor a relevant
   evaluation changed.
8. An interface may influence behaviour and thereby indirectly cause later substrate changes, but
   that causal path must be recorded.

This is the cleanest treatment of a System that claims to grant powers but is actually measuring,
compressing, or manipulating a different process.

---

## 8. Record-shape compatibility

Everything above can be expressed through records of the required shape by making relation,
evaluation, claim, constraint, and change occurrences referenceable subjects.

### 8.1 N-ary change

```text
(change-17, type, change, null, s17, accepted-canon, all)
(change-17, actor, arden, null, s17, accepted-canon, all)
(change-17, authorized_by, oath-agency, null, s17, accepted-canon, restricted)
(change-17, precondition, claim-44, null, s17, accepted-canon, all)
(change-17, effect, claim-45, assert, s17, accepted-canon, all)
```

### 8.2 Scoped cardinality

```text
(exclusive-card-holder, type, cardinality-constraint, null, null, author-locked, all)
(exclusive-card-holder, predicate, possessed_by, null, null, author-locked, all)
(exclusive-card-holder, scope, exclusive-carrier, null, null, author-locked, all)
(exclusive-card-holder, group_key, carrier-and-valid-interval, null, null, author-locked, all)
(exclusive-card-holder, maximum, null, 1, null, author-locked, all)
```

### 8.3 Evaluation

```text
(eval-9, evaluation.subject, arden, null, s9, accepted-canon, all)
(eval-9, evaluation.criterion, guard-rank, null, s9, accepted-canon, all)
(eval-9, evaluation.result, silver, null, s9, accepted-canon, all)
(eval-9, recognized_by, guard-guild, null, s9, accepted-canon, all)
```

### 8.4 Claim and disclosure

```text
(claim-17, claim.content, null, "the interface creates the powers", s2, accepted-canon, all)
(mara, believes, claim-17, null, s2, accepted-canon, all)
(reveal-22, disclosed_to, reader, claim-17-is-false, s22, accepted-canon, all)
```

### 8.5 Findings about the current shape

- `authority` should remain workflow authority: proposed, accepted canon, or author-locked. It
  must not double as a story-world authorizer.
- Story-world authority needs `authorized_by`, `validated_by`, and `recognized_by` relations.
- `visibility` should remain operational packet access. It must not double as truth, belief, or
  reader disclosure.
- `story-position` records establishment or occurrence. Story-world validity needs
  `valid_during`, `supersedes`, or change effects.
- Manuscript retraction is not the same as a state ceasing to be true inside the story.
- N-ary relations fit through reification; no new tuple field is required.
- The existing `record_id` is load-bearing because claims and relation occurrences must be
  referenceable.

No database migration appears necessary for the ontology itself because `record_json` already
carries the full record. The missing capability is interpretation.

---

## 9. Worked encodings

The examples abbreviate authority as `canon`. `all` and `[x]` describe operational visibility.

### 9.1 Combat-driven: a bonded guard advances at a permanent cost

| Subject | Predicate | Object | Value | Position | Authority | Visibility |
|---|---|---|---|---|---|---|
| `guard-rank` | `type` | `criterion` | — | — | canon | all |
| `guard-rank` | `comparator` | — | `ordinal` | — | canon | all |
| `bronze` | `precedes` | `silver` | — | — | canon | all |
| `eval-before` | `evaluation.subject` | `arden` | — | s1 | canon | all |
| `eval-before` | `evaluation.criterion` | `guard-rank` | — | s1 | canon | all |
| `eval-before` | `evaluation.result` | `bronze` | — | s1 | canon | all |
| `arden-fox-bond` | `member` | `arden` | — | s1 | canon | all |
| `arden-fox-bond` | `member` | `ember-fox` | — | s1 | canon | all |
| `change-19` | `actor` | `arden-fox-bond` | — | s19 | canon | all |
| `change-19` | `precondition` | `protected-squad-without-killing` | — | s19 | canon | all |
| `change-19` | `authorized_by` | `tempest-oath` | — | s19 | canon | `[arden]` |
| `change-19` | `effect` | `eval-after` | `assert` | s19 | canon | all |
| `change-19` | `effect` | `arden-hearing-impaired` | `assert` | s19 | canon | all |
| `eval-after` | `evaluation.subject` | `arden` | — | s19 | canon | all |
| `eval-after` | `evaluation.criterion` | `guard-rank` | — | s19 | canon | all |
| `eval-after` | `evaluation.result` | `silver` | — | s19 | canon | all |
| `arden-fox-bond` | `permits` | `redirect-lightning` | `only_while_together` | s19 | canon | all |

**Prose legibility.** The pair redirects an attack neither could redirect alone; Arden later fails
to hear an approaching ally. A changed outfit is supporting evidence, not the semantic advancement.

**Anti-stasis.** The evaluation changes and a new joint action becomes reachable. The permanent
hearing loss alters later choices.

### 9.2 Non-combat: a cabinetmaker understands moving wood

| Subject | Predicate | Object | Value | Position | Authority | Visibility |
|---|---|---|---|---|---|---|
| `joinery-reach` | `type` | `criterion` | — | — | canon | all |
| `joinery-reach` | `comparator` | — | `strict_set_inclusion` | — | canon | all |
| `eval-before` | `evaluation.subject` | `elin` | — | s2 | canon | all |
| `eval-before` | `evaluation.criterion` | `joinery-reach` | — | s2 | canon | all |
| `eval-before` | `evaluation.result` | — | `[dry-stock-dovetail]` | s2 | canon | all |
| `hurdle-7` | `claim.content` | — | `three panel doors warped after wet weeks` | s7 | canon | all |
| `claim-11` | `claim.content` | — | `movement follows moisture gradient and grain orientation` | s11 | canon | all |
| `change-11` | `actor` | `elin` | — | s11 | canon | all |
| `change-11` | `precondition` | `hurdle-7` | — | s11 | canon | all |
| `change-11` | `caused_by` | `rebuild-and-season-test` | — | s11 | canon | all |
| `change-11` | `consumes` | `walnut-stock` | `three boards` | s11 | canon | all |
| `change-11` | `consumes` | `elin-time` | `forty hours` | s11 | canon | all |
| `change-11` | `effect` | `claim-11` | `understood_by=elin` | s11 | canon | all |
| `eval-after` | `evaluation.subject` | `elin` | — | s12 | canon | all |
| `eval-after` | `evaluation.criterion` | `joinery-reach` | — | s12 | canon | all |
| `eval-after` | `evaluation.result` | — | `[dry-stock-dovetail, humid-panel-door, predict-seasonal-gap]` | s12 | canon | all |
| `guild-eval` | `evaluation.subject` | `elin` | — | s16 | canon | all |
| `guild-eval` | `recognized_by` | `cabinetmakers-guild` | `journey-grade` | s16 | canon | all |

**Prose legibility.** A panel remains true after a wet week, and Elin predicts the required seasonal
gap before cutting. Competence changes before institutional recognition.

**Anti-stasis.** The new claim makes a correct prediction and makes a new humid-context action
reachable. “Elin understands wood more deeply” without those consequences would fail.

### 9.3 Collective, declining, and involuntary: a town archive steals craft memory

| Subject | Predicate | Object | Value | Position | Authority | Visibility |
|---|---|---|---|---|---|---|
| `archive-breadth` | `type` | `criterion` | — | — | canon | all |
| `archive-breadth` | `comparator` | — | `strict_set_inclusion` | — | canon | all |
| `rowan-retention` | `type` | `criterion` | — | — | canon | all |
| `rowan-retention` | `comparator` | — | `strict_set_inclusion` | — | canon | all |
| `archive-before` | `evaluation.result` | — | `12 craft domains` | s4 | canon | all |
| `rowan-before` | `evaluation.result` | — | `[glazing, firing, clay-selection]` | s4 | canon | all |
| `change-6` | `actor` | `north-archive` | — | s6 | canon | `[north-archive]` |
| `change-6` | `participant` | `rowan` | `donor` | s6 | canon | `[north-archive]` |
| `change-6` | `voluntary` | — | `false` | s6 | canon | `[north-archive]` |
| `transfer-leg-1` | `source` | `rowan` | — | s6 | canon | `[north-archive]` |
| `transfer-leg-1` | `target` | `north-archive` | — | s6 | canon | `[north-archive]` |
| `transfer-leg-1` | `content` | `glazing-knowledge` | — | s6 | canon | `[north-archive]` |
| `archive-after` | `evaluation.result` | — | `13 craft domains` | s6 | canon | `[north-archive]` |
| `rowan-after` | `evaluation.result` | — | `[firing, clay-selection]` | s6 | canon | all |
| `surface-claim` | `claim.content` | — | `Rowan blames exhaustion for the ruined glaze` | s7 | canon | all |
| `reveal-12` | `disclosed_to` | `reader` | `change-6` | s12 | canon | all |

**Prose legibility.** Rowan ruins a glaze that was previously habitual; the archive later answers a
question using Rowan's distinctive method.

**Anti-stasis.** The archive progresses under breadth while Rowan declines under retention and
autonomy. The transfer conserves knowledge instead of duplicating it. The truth predates the
reader's discovery.

---

## 10. Anti-stasis rules by geometry

| Geometry | Checkable movement condition |
|---|---|
| Ordinal or tier | Evaluation changes to a distinct ordered result and at least one affordance, constraint, recognition, or presentation consequence changes. |
| Breadth or set | The closure of reachable actions gains at least one non-entailed member. |
| Specialization or tree | The chosen branch changes reachability and either forecloses or increases the cost of an alternative. |
| Lateral reconfiguration | At least one context produces a different permitted action or outcome even if total value is equivalent. |
| Threshold or credential | Crossing changes authorization, recognition, or institutional treatment. Mere renewal is maintenance, not progress. |
| Depth or concept | The later claim is not entailed by earlier claims and supports a new prediction, explanation, distinction, or action. |
| Cycle or prestige | Local state returns to an equivalent class, but persistent meta-state changes reachability, efficiency, interpretation, or future options. |
| Decline or corruption | An affordance is lost, a constraint tightens, or a cost persists in later scenes. |
| Rating or estimate | The estimate changes beyond declared precision because evidence changed; the detector must not infer that latent capability moved. |
| Transfer or collective | Distribution or joint reachability changes without illicit duplication unless a replication rule permits it. |

For conceptual depth, let \(Cl(C_n)\) be the semantic closure of claims through rung \(n\). A
candidate rung must provide a claim \(c\) such that:

\[
c\notin Cl(C_n)
\]

and at least one new consequence is demonstrated. Exact entailment is not presently a safe
deterministic gate, so this check should initially annotate rather than block.

---

## 11. What progression does for a reader

The semantic mechanism and its presentation should remain separate.

| Reader function | Structural source |
|---|---|
| Anticipation | A visible criterion, incomplete collection, unresolved hurdle, or partially known transition graph. |
| Causal trust | Preconditions, attempts, costs, authorizers, and consequences explain why change occurred. |
| Vicarious mastery | The reader learns the task grammar and can anticipate later solutions. |
| Identity change | Beliefs, relationships, roles, and habitual choices change with capability. |
| Completion pressure | A finite set, threshold, vow sequence, or known endpoint remains incomplete. |
| Social comparison | Ratings, credentials, titles, and recognition place the subject relative to others. |
| Fragility and stakes | Revocation, decay, tradeoffs, and costs prevent capability from feeling unconditional. |
| Revelation | A gap between substrate, belief, interface, and disclosure lets earlier evidence be reread. |

Numbers, outfits, glowing auras, title cards, belts, uniforms, and status screens are legibility
channels. They are not progression primitives.

---

## 12. Failure-mode catalogue and detector signatures

| Failure | Checkable signature |
|---|---|
| Power creep | Success thresholds and antagonist baselines rise with the newest capability while older capabilities' causal use frequency falls toward zero. |
| Stat inflation | Evaluation values rise while reachable-action closure and outcome distribution remain unchanged. |
| System abandonment | A long narrative window contains no system constraint, change, evaluation, or causally necessary capability use. |
| Unearned advancement | A beneficial change has no prior hurdle, relevant attempt, credible cause, authorizer, or meaningful trade. |
| Ladder stasis | Repeated evaluation snapshots remain equivalent across promised milestone windows. |
| Pseudo-depth | A later concept claim is paraphrase or entailment of earlier claims and produces no new prediction or action. |
| False specialization | A branch is chosen, but no alternative is foreclosed and downstream outcomes converge. |
| Cost laundering | A cost is declared but never persists, changes a choice, removes reachability, consumes a conserved resource, or affects later prose. |
| Illegible rules | Near-equivalent contexts yield incompatible outcomes without a recorded modifier; explanations first appear after the outcome. |
| Interface drift | Displayed state changes without substrate change, reveal, correction, or declared remapping. |
| Double-counted transfer | A receiver gains an exclusive capability while the giver retains it and no copying rule exists. |
| Credential-capability conflation | Recognition changes without supporting performance evidence, or measured performance moves oppositely without the divergence being acknowledged. |
| Prestige treadmill | Reset occurs but persistent reachability, efficiency, options, and interpretation remain equivalent. |
| Collection bloat | Collection size increases while marginal items are never used, combined, exchanged, or made prerequisite. |
| Hidden-rule cheating | A rule first appears only after it resolves the problem it governs. |
| Rank reskinning | Outfit or title changes while affordances, treatment, risks, and constraints do not. |
| Agency aesthetic drift | Granted affordances cease to share any recorded motif, goal, method, or constraint with the granting agency without an explanatory change. |
| Collective free gain | A group evaluation rises although no member, asset, relation, coordination rule, or environment state changes. |
| Recognition monopoly | The narrative treats one institution's evaluation as substrate truth despite contradictory performance or rival recognition. |

Deterministic structural cases can eventually block: exact evaluation multiplicity, violation of a
declared maximum, illegal rank order, impossible conservation, and repeated identical state.
Semantic cases such as pseudo-depth, unearned advancement, and aesthetic drift should initially
produce evidence-bearing annotations.

---

## 13. Rejection list

The following should not become universal primitives or defaults:

- level;
- hit points, mana, currency, or experience points;
- a scalar overall power score;
- ladder, tier, or class;
- ability as an intrinsic property;
- cost as one numeric field;
- agency or grantor as a special entity type;
- carrier, collection, or bond as special entity types;
- individual-only progression;
- monotonicity;
- global functionality for `held_by`, `bonded_with`, or `holds_rank`;
- predicate arity without scope and grouping keys;
- Boolean visibility as a substitute for knowledge and disclosure;
- absence as false;
- a required diegetic System;
- a required personality or aesthetic;
- a printed stat line as the canonical extraction surface;
- a second mention alone as sufficient evidence that a newly invented concept is canon;
- arbitrary executable formulas embedded in `value`;
- an implicit rule that systems with similar labels share state or scale;
- an implicit rule that the stronger or older system wins conflicts.

---

## 14. Implementation handoff for LitHarness

### 14.1 Recommended sequence

1. **Replace global predicate arity with scoped cardinality.** Structural relation arity can remain
   fixed for evaluation, claim, transfer-leg, and constraint records.
2. **Add record patterns, not schema classes,** for `change`, `constraint`, `criterion`, and `view`.
3. **Build an active-state projection** that understands story-world supersession, validity, and
   contexts. Keep manuscript retraction separate.
4. **Separate causal and institutional roles:** `caused_by`, `performed_by`, `authorized_by`,
   `validated_by`, and `recognized_by` must not collapse into one edge.
5. **Reserve `StateAuthority` for workflow authority** and `pov_visibility` for operational packet
   access.
6. **Represent belief and disclosure as graph relations** to first-class claims.
7. **Implement a small comparator registry:** ordinal, numeric, threshold, equality, set inclusion,
   Pareto/vector, and replacement equivalence.
8. **Keep semantic depth advisory** until its false-positive rate is measured on published and
   generated prose.
9. **Permit proposed identifiers without laundering their claims.** Identity minting and factual
   promotion should be separate decisions. Repetition alone is weak evidence; later causal reuse is
   stronger.
10. **Keep the diegetic System optional.** The analytic regime bundle must not imply that the
    fictional world contains an agent or interface called a System.

### 14.2 Immediate correction to the existing design note

The current contradiction detector groups by `(subject, predicate, order_key)` and ignores
`object_ref`. The proposed repair should not be a frozen table such as:

```text
held_by -> functional
trait -> multivalued
```

Instead, the integrity layer should evaluate declared shapes such as:

```text
constraint: exclusive-carrier-holder
scope: subjects typed exclusive-carrier
predicate: possessed_by
group-key: [subject, story-context, overlapping-validity]
maximum: 1
```

Unknown predicates should remain untyped and non-blocking. A book-specific or regime-specific
shape may make them checkable later.

### 14.3 Extraction policy

The page should be able to establish:

- a state assertion;
- a relation;
- a change occurrence;
- a claim or belief;
- an evaluation;
- evidence for satisfying a constraint.

Extraction should return evidence spans and structured proposals. It should not require the visible
prose to print a stat block or ontology line. A rigid hidden extraction response format is useful;
a rigid in-story status line is not the general abstraction.

New subject handling should distinguish:

1. **identifier admission:** the text clearly denotes a new entity or claim;
2. **fact admission:** the proposed predicate and value are accepted as canon;
3. **rule admission:** the text supports a general rule rather than a one-off event.

This avoids making “the model named it once” equivalent to “the world has this rule.”

### 14.4 Existing infrastructure that can be reused

- `StateRecord.record_id` supplies identity for reified claims and relation occurrences.
- `object_ref` supplies graph edges.
- `record_json` carries shapes without new columns.
- state authority already separates proposals from accepted canon.
- evidence spans can make extracted state auditable.
- progression promises can link a hurdle to a later change payoff.
- manuscript retraction already establishes the principle that history is retained rather than
  destructively overwritten.

### 14.5 Suggested implementation phases

**Phase A: structural graph safety**

- scoped cardinality constraints;
- first-class evaluation and change records;
- active-state projection and story-world supersession;
- deterministic tests for exclusive possession and evaluation multiplicity.

**Phase B: capability and comparison**

- reachability or affordance records;
- ordinal, threshold, numeric, and set-inclusion comparators;
- transfer and cost-effect patterns;
- anti-stasis checks for tier, breadth, reset, and decline.

**Phase C: epistemic systems**

- first-class claims;
- knowledge, belief, and reader disclosure;
- view/substrate mappings;
- lie, reveal, and interface-drift checks.

**Phase D: semantic research**

- conceptual-depth candidate extraction;
- entailment and new-consequence probes;
- calibration against published prose;
- advisory findings only until error rates justify stronger policy.

---

## 15. Uncertainties and open questions

1. **Criterion as explicit primitive versus derived reachability.** Many access systems need no
   stored criterion; the strict-superset order is implicit. Explicit criteria are nevertheless
   useful when several values conflict or when social recognition differs from capability.
2. **Semantic depth is the weak point.** The structural representation is clear, but reliable
   automated non-entailment and genuine-understanding judgments are not established.
3. **Identity across time remains policy.** A bond, guild, ship, city, or lineage can change
   membership radically. The state store can record succession but cannot decide sameness.
4. **Open-world versus closed-world checks must be explicit.** Minimum cardinality and completeness
   are unsafe unless the relevant scope is declared closed.
5. **Causality in prose is often underdetermined.** A change record can cite narrated causes without
   claiming a complete causal model.
6. **Institutional recognition is plural.** “Official” rank or expertise may be contested. The
   model should not silently privilege one recognizer as truth.
7. **A comparator DSL should remain deliberately small.** Arbitrary executable rules would turn the
   state store into an unsafe and untestable simulation language.
8. **Absence must remain free.** No progression bundle, comparator, agency, or interface should be
   synthesized merely because a story contains ordinary learning or change.

---

## 16. Decision summary

Adopt:

- a qualified active-state graph;
- capability as contextual authorized reachability;
- change, constraint, criterion, and view as the four first-class progression patterns;
- partial rather than total comparison;
- scoped cardinality constraints;
- explicit causal, authorizing, validating, and recognizing roles;
- explicit truth, belief, disclosure, and interface layers;
- system interaction through independence, coupling, interference, exclusivity, conversion,
  dominance, composition, recognition, and view mappings.

Do not adopt:

- a universal character sheet;
- ladder or ability as the root abstraction;
- global predicate arity;
- monotone power as the definition of progression;
- a required diegetic System;
- cost, carrier, bond, agency, rank, or tier as irreducible ontology types.

The shortest final statement is:

> **Progression is a contextual change in reachable, authorized, recognized, or understood
> possibilities.**

---

## References

### Formal games and institutional systems

- Wizards of the Coast. “Creating a Character: Level Advancement,” *D&D Free Rules*.
- Evil Hat Productions. “Advancement & Change,” *Fate Core SRD*.
- Chaosium. *Basic Roleplaying: Universal Game Engine ORC Content Document*.
- Harper, John. “Advancement,” *Blades in the Dark*.
- LaTorra, Sage, and Adam Koebel. *Dungeon World SRD*.
- Free League Publishing. *Year Zero Engine Standard Reference Document*, version 1.0.
- Wube Software. “Technologies” and “Research,” *Official Factorio Wiki*.
- Nintendo. *Metroid Dread* product and gameplay documentation.
- Mega Crit. *Slay the Spire* press kit.
- Vaccarino, Donald X. *Dominion*, second-edition rules.
- Cephalofair Games. *Gloomhaven* rules and campaign documentation.
- Firaxis/2K. *Civilization VI* technology and civic shuffle documentation.
- FIDE. *FIDE Rapid and Blitz Rating Regulations*.
- UK Government. *Apprentice Guide to Assessment*.
- Quality Assurance Agency. *The Frameworks for Higher Education Qualifications of UK
  Degree-Awarding Bodies*.
- General Medical Council. “What is revalidation?”
- British Judo Association. Grading schemes and promotion syllabi.
- UK Ministry of Defence. Army officer promotion regulations.
- Suber, Peter. *Nomic: A Game of Self-Amendment*.

### Learning and knowledge representation

- Ericsson, K. Anders, Ralf T. Krampe, and Clemens Tesch-Römer. “The Role of Deliberate Practice
  in the Acquisition of Expert Performance.” *Psychological Review* 100, no. 3 (1993): 363–406.
- Chase, William G., and Herbert A. Simon. “Perception in Chess.” *Cognitive Psychology* 4, no. 1
  (1973): 55–81.
- Posner, George J., Kenneth A. Strike, Peter W. Hewson, and William A. Gertzog. “Accommodation of
  a Scientific Conception: Toward a Theory of Conceptual Change.” *Science Education* 66, no. 2
  (1982): 211–227.
- Meyer, Jan H. F., and Ray Land. “Threshold Concepts and Troublesome Knowledge: Linkages to Ways
  of Thinking and Practising.” 2003.
- Corbett, Albert T., and John R. Anderson. “Knowledge Tracing: Modeling the Acquisition of
  Procedural Knowledge.” *User Modeling and User-Adapted Interaction* 4 (1995): 253–278.
- Roediger, Henry L. III, and Jeffrey D. Karpicke. “Test-Enhanced Learning: Taking Memory Tests
  Improves Long-Term Retention.” *Psychological Science* 17, no. 3 (2006): 249–255.
- W3C. *Defining N-ary Relations on the Semantic Web*.
- W3C. *Shapes Constraint Language (SHACL)*.
- W3C. *OWL 2 Web Ontology Language Primer*.
- W3C. *PROV-O: The PROV Ontology*.
- W3C. *Time Ontology in OWL*.

### Prose stress tests

- Addison, Katherine. *The Goblin Emperor*.
- Clarke, Susanna. *Jonathan Strange & Mr Norrell*.
- Kurmaic, Domagoj. *Mother of Learning*.
- Le Guin, Ursula K. *A Wizard of Earthsea*.
- Sanderson, Brandon. *The Stormlight Archive*.
- Tevis, Walter. *The Queen's Gambit*.
- Tolkien, J. R. R. *The Lord of the Rings*.
- Wight, Will. *Cradle*.

[dnd]: https://www.dndbeyond.com/sources/dnd/br-2024/creating-a-character
[fate]: https://fate-srd.com/fate-core/advancement-change
[brp]: https://www.chaosium.com/content/orclicense/BasicRoleplaying-ORC-Content-Document.pdf
[blades]: https://bladesinthedark.com/advancement
[dungeon-world]: https://www.dungeonworldsrd.com/moves/
[yze]: https://freeleaguepublishing.com/wp-content/uploads/2023/11/YZE-Standard-Reference-Document.pdf
[factorio]: https://wiki.factorio.com/Technologies
[metroid]: https://www.nintendo.com/us/store/products/metroid-dread-switch/
[slay]: https://www.megacrit.com/press-kits/slay-the-spire/
[dominion]: https://www.riograndegames.com/wp-content/uploads/2016/09/Dominion2E.pdf
[gloomhaven]: https://cephalofair.com/pages/gloomhaven
[civ]: https://support.civilization.com/hc/en-us/articles/37661296703507-Patch-Notes-August-27-2020
[fide]: https://handbook.fide.com/chapter/B02RBRegulations2024
[apprentice]: https://www.gov.uk/guidance/apprentice-guide-to-assessment
[qaa]: https://www.qaa.ac.uk/docs/qaa/quality-code/the-frameworks-for-higher-education-qualifications-of-uk-degree-awarding-bodies-2024.pdf
[gmc]: https://www.gmc-uk.org/registration-and-licensing/managing-your-registration/revalidation/what-is-revalidation
[judo]: https://www.britishjudo.org.uk/get-started/grading/mon-grade-scheme/
[army]: https://assets.publishing.service.gov.uk/media/6645dab84f29e1d07fadc93a/FOI2023_06654.pdf
[ericsson]: https://doi.org/10.1037/0033-295X.100.3.363
[chase-simon]: https://doi.org/10.1016/0010-0285(73)90004-2
[posner]: https://doi.org/10.1002/sce.3730660207
[thresholds]: https://www.ee.ucl.ac.uk/mflanaga/thresholds.html
[bkt]: https://doi.org/10.1007/BF01099821
[retrieval]: https://doi.org/10.1111/j.1467-9280.2006.01693.x
[nary]: https://www.w3.org/TR/swbp-n-aryRelations/
[shacl]: https://www.w3.org/TR/shacl/
[owl]: https://www.w3.org/TR/owl-primer/
[nomic]: https://legacy.earlham.edu/~peters/writing/nomic.htm
