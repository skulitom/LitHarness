# Follower signal: the operator's library-following idea, mapped to the rails before anything is built

**Status: direction note, 2026-08-28. No arm, no registration, no claim.** The operator, verbatim,
recorded because it names the product signal §126 already defined and adds two design intuitions:

> *"I'm thinking of having the LLM Readers should have oportunity to follow books in our
> book-library, and we can keep statistics of followers in the root of book-library. I feel like
> this might be useful. Obviously there needs to be some sort of cost or compromise to the agents
> for following, otherwise we can just follow no matter what. Maybe followers can only be other
> writers, so when a book is liked by a more diverse writer set it might have more quality.
> Anyways just throwing ideas out here"*

## What this is, said plainly

§126's product objective is *fiction a defined simulated audience continues and recommends*.
A persistent follow, accumulated per book in the library, is that objective made into a running
statistic instead of a per-arm measurement. The idea is aligned with the registered goal, not a
new goal.

## The three pieces, each against the record

**1. "There needs to be some sort of cost… otherwise we can just follow no matter what" — the
operator has independently named §134.** Uncosted opt-in signals saturate: continuation returned
13/16, 15/16, 15/16, 16/16, 16/16 across the recorded rounds, and every 4/4 since is reported
with that ceiling written across it. The record also already holds the validated mechanism for
following-at-a-price: `fcr.v0` (§122) — the costed feed with skim and voluntary abandonment,
where the informative act is *stopping*, and `bcr.v0`'s budgeted continuation. A follow should be
what the code computes from that behaviour (a reader who keeps paying attention out of a bounded
budget with rival feeds available), never a free button and never a stated preference — the
verdict channel stays shut (§89, §97.4).

**2. "Followers can only be other writers" — this half collides with a recorded rail.** R3, in
`domain/writers.py`'s own docstring: *a writer never judges; a writer that did would be a judge
in a hat.* And §137: no key exists that licenses comparing writers, so writer-sourced preference
would be doubly unreadable. The intuition *inside* the idea survives in an admissible form:

**3. "Liked by a more diverse set = more quality" — breadth-weighting, and it is the novel
piece.** Count-of-followers is the popularity confound this project already measured
(reader preference ≠ popularity). Breadth — a book followed across *appetites* rather than
within one niche — is a different statistic, and a dossier-diverse simulated READER pool is the
admissible carrier (the new roster/recruiter machinery can mint reader personas with varied
appetites exactly as it mints writers; §83/§89.1's decorative-persona prior applies and must be
checked, not assumed). Diversity weighting of a behavioural signal has no recorded refutation.

## The gates any version must pass, in order

1. **§141 first.** Whatever the follower statistic is, it validates blind on the registered
   market follower gradient (the one thing this readership has proven it can read) before its
   number on our shelf is believed. The symmetry is the point: simulated followers of ours
   against real followers of the market's.
2. **Distributions before bars** (§61), and the §134 ceiling check: a design whose statistic can
   saturate has to show a non-saturating distribution at the real n before any reading.
3. **No selection without containment** (§61(5), §105.1): the moment follower counts pick which
   book continues, gets chapters, or gets shown, a model is selecting among candidates — that
   needs the containment log, not just the instrument.
4. **Register before any paid call**; kills and readings fixed; alpha divided if N reader
   personas each get a vote-like behaviour.

## Where the statistics would live

`book-library/` is generated, gitignored state — a `followers.json` at its root is plumbing and
fine. The number in it is not evidence until the gates above are passed; nothing restates it
elsewhere (counts are pointed to, never copied).

## Anti-scope

Nothing here is scheduled. The current pipeline (pilot 12's review package, the recruiter's
twelve, the registered brief/dossier arm) is the priority, and this note exists so that when
following is built, it is built from `fcr.v0`'s costed-behaviour machinery under the gates above
— not as a free follow bit that dies on §134, and not with writers in the jury box against R3.
