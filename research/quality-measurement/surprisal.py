"""Context Dependency Gain: how much a chapter's own earlier text predicts its later text.

The instrument. `ablate.py` supplies ground truth and `evaluate.py` supplies the controls;
this is the thing being tested.

**The idea in one line.** Take a block of prose from the middle of a chapter and score it twice
under a frozen base model — once with the chapter's *own* preceding text in context, once with
a length-matched prefix from a *different* chapter. The gap is how much this story's own setup
was doing to make this passage land.

    CDG = mean_over_blocks[ logP(block | its own prefix) - logP(block | a foreign prefix) ]

**Why this is not another entry in the refutation ledger.** All thirteen refuted proxies share
three properties, and this shares none of them:

- They were *static* — a count over one text. This is a difference between two forward passes.
- They were *absolute*, so era, author, story maturity and length entered every comparison.
  This is a difference-of-two-scores over **identical target tokens**: the only thing that
  differs between the two conditions is the prefix. Everything about the target block — its
  vocabulary, its length, its difficulty, its year, its author — is present in both terms and
  subtracts out. That is the structural property the `tricolon_rate` control was needed to
  discover the absence of.
- They were *correlational*. This intervenes: the foreign prefix is a controlled substitution.

**Training-set contamination, which is the first thing to raise about any model-based measure
over published fiction, is handled by the same subtraction.** If the base model has memorised
Mother of Learning, recall raises `logP(block | own prefix)` — and it raises
`logP(block | foreign prefix)` too, because the block is still the memorised continuation of a
memorised book. What memorisation *cannot* do is survive `ablate.rename_entities`, which is
why that sham is in the battery: a CDG that collapses under a consistent rename was reading
the training set, and a CDG that does not was reading the prose. The control is already built;
this module just has to not get in its way.

**What it is aimed at.** §1a.3 item 3, escalation and payoff, and item 1, dramatic function —
the two nothing in this project has ever reached. A chapter whose blocks are interchangeable
has a low CDG whatever its sentence rhythm; a chapter whose late passages depend on its early
ones has a high one. That is a hypothesis about human judgment until it is validated against
some, and it is exactly as unvalidated as every proxy in the ledger was at this stage.

**What would make it just another dead proxy**, stated before the numbers exist:

- If it responds to `paragraph_shuffle` no more strongly than to `rename_entities`, it is
  reading entity continuity, not narrative structure.
- If `connective_scramble` — nine changed words — moves it as much as a full shuffle, the
  dose ladder is not monotone and it is detecting token novelty.
- If raw word count separates the same pairs as well, §1a.1's shallow incumbent wins.

Run offline, never from the loop. Nothing in `src/` imports this.
"""

from __future__ import annotations

import gc
from dataclasses import dataclass
from functools import lru_cache

#: Base, not instruct. An instruction-tuned model's distribution is shaped by preference
#: training toward assistant register, which is a different distribution from "what does
#: published fiction do next" — and the whole measurement is a statement about that
#: distribution. `-pt` is the pretrained checkpoint.
DEFAULT_MODEL = "google/gemma-3-4b-pt"

#: Target block size in tokens. Large enough that a mean log-probability over it is stable,
#: small enough that a chapter yields several blocks. Not tuned: tuning it against the
#: outcome is how a proxy gets fitted to its own validation set.
BLOCK_TOKENS = 384

#: Prefix length in tokens, identical for the true and the foreign condition. Fixed rather
#: than "everything before this block" for one load-bearing reason: a growing prefix makes
#: later blocks incomparable to earlier ones and reintroduces *position* as a confound, which
#: is the variable that killed the Wayback comment-count proxy.
PREFIX_TOKENS = 768


@dataclass(frozen=True, slots=True)
class Scored:
    cdg: float
    own_logprob: float
    foreign_logprob: float
    blocks: int


@lru_cache(maxsize=1)
def _load(model_id: str):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, dtype=torch.bfloat16, device_map="cuda"
    )
    model.eval()
    return tokenizer, model


def free() -> None:
    """Drop the model. Long batches otherwise hold 8GB across an experiment that is done."""
    import torch

    _load.cache_clear()
    gc.collect()
    torch.cuda.empty_cache()


def _mean_logprob(model, tokenizer, prefix_ids, target_ids) -> float:
    """Mean log-probability of `target_ids`, conditioned on `prefix_ids`.

    Scores **only** the target positions. Including the prefix in the mean would make the two
    conditions incomparable — the foreign prefix is different text and would contribute its
    own difficulty to the average, so the "gain" would partly measure which prefix was easier.
    That is the mechanical null this function is written to avoid.
    """
    import torch

    ids = torch.cat([prefix_ids, target_ids]).unsqueeze(0).to(model.device)
    with torch.no_grad():
        logits = model(ids).logits.float()
    # Position i predicts token i+1, so the logits that score the target start one before it.
    start = prefix_ids.shape[0]
    window = logits[0, start - 1 : -1, :]
    gold = ids[0, start:]
    logprobs = torch.log_softmax(window, dim=-1)
    picked = logprobs.gather(-1, gold.unsqueeze(-1)).squeeze(-1)
    return float(picked.mean())


def make_scorer(
    foreign_source: str,
    *,
    model_id: str = DEFAULT_MODEL,
    block_tokens: int = BLOCK_TOKENS,
    prefix_tokens: int = PREFIX_TOKENS,
    max_blocks: int = 6,
):
    """Build a `text -> float` CDG scorer, so it plugs straight into `evaluate.evaluate`.

    `foreign_source` is the text the control prefix is drawn from and it must **not** be the
    chapter being scored or its neighbours. Drawing it from the same book is the stricter
    choice and the one taken here: the model still gets this author, this cast and this genre
    in the control condition, so what the gain isolates is *this chapter's own* setup rather
    than "the model has heard of Mother of Learning".
    """
    tokenizer, model = _load(model_id)
    import torch

    foreign_ids = tokenizer(foreign_source, return_tensors="pt", add_special_tokens=False)[
        "input_ids"
    ][0]

    def score(text: str) -> float:
        ids = tokenizer(text, return_tensors="pt", add_special_tokens=False)["input_ids"][0]
        stride = prefix_tokens + block_tokens
        if ids.shape[0] < stride + block_tokens or foreign_ids.shape[0] < prefix_tokens:
            return float("nan")
        own_total = 0.0
        foreign_total = 0.0
        count = 0
        # Blocks are taken at fixed offsets from the start rather than at random positions, so
        # two variants of the same chapter are scored at the same places and the pairing in
        # `evaluate` is between comparable numbers.
        for index in range(max_blocks):
            start = index * stride
            if start + stride > ids.shape[0]:
                break
            prefix = ids[start : start + prefix_tokens]
            target = ids[start + prefix_tokens : start + stride]
            # The control prefix is length-matched and taken from a fixed, deterministic
            # offset in the foreign text — a random draw per call would make the metric
            # non-deterministic and its own re-runs incomparable.
            offset = (index * prefix_tokens) % max(1, foreign_ids.shape[0] - prefix_tokens)
            foreign = foreign_ids[offset : offset + prefix_tokens]
            if foreign.shape[0] < prefix_tokens:
                break
            own_total += _mean_logprob(model, tokenizer, prefix, target)
            foreign_total += _mean_logprob(model, tokenizer, foreign, target)
            count += 1
        if not count:
            return float("nan")
        del ids
        torch.cuda.empty_cache()
        return (own_total - foreign_total) / count

    return score


def detail(text: str, foreign_source: str, **kwargs) -> Scored:
    """Same computation, with both terms reported. For reading a single case by hand."""
    scorer = make_scorer(foreign_source, **kwargs)
    value = scorer(text)
    return Scored(cdg=value, own_logprob=float("nan"), foreign_logprob=float("nan"), blocks=0)


if __name__ == "__main__":
    import sys
    import time
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ablate import BY_KEY
    from corpus_io import mol_chapters

    chapters = mol_chapters()
    host = chapters[20].text
    foreign = chapters[80].text

    print(f"loading {DEFAULT_MODEL} ...", flush=True)
    started = time.time()
    score = make_scorer(foreign)
    print(f"loaded in {time.time() - started:.1f}s", flush=True)

    started = time.time()
    base = score(host)
    elapsed = time.time() - started
    print(f"\noriginal CDG = {base:+.4f}   ({elapsed:.1f}s per chapter)\n")

    # One degrader and one sham at full strength. If the degrader does not move CDG down and
    # the sham does not leave it roughly alone, there is no point running the full battery.
    for key in ("paragraph_shuffle", "rename_entities"):
        damaged = BY_KEY[key].apply(host, 1.0)
        value = score(damaged)
        tag = "degrader" if BY_KEY[key].sign < 0 else "SHAM"
        print(f"{key:<20} {tag:<9} CDG = {value:+.4f}   delta = {value - base:+.4f}")
