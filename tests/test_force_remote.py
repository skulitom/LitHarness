"""The rails under §95.10's remote transport, checked rather than asserted.

`force_remote` is the only place in the force programme that spends money and the only place a
control is *weakened* rather than enforced, so both properties want a test that fails loudly:

1. **The spend ceiling is a stop, not a note.** It must raise on the charge that crosses it and
   refuse the next call before it is made. A ceiling discovered after the fact is an overrun.
2. **The per-pair seed cap is symmetric.** §95.4's confound — 23 of 281 pairs differ by more than
   0.04 in |log10 word ratio|, one by 2.85x — is closed by both sides entering at the same
   length. On this transport there is no tokenizer, so the cap is in words, and the substitution
   is only safe while it stays symmetric.
3. **Continuations are length-normalised.** F1's statistic is a *window index*, so a side whose
   continuations run longer has more windows to cross in. Locally `max_new_tokens` makes every
   trajectory the same length; here the model stops when it stops, and the fix is a fixed word
   cut with a short-drop floor.
4. **The weakening is visible.** `UNPINNED` and the determinism downgrade must appear in the
   provenance block, because a result file that does not say it was produced without a pinned
   revision or an exact placebo reads exactly like one that was.

Hermetic: no subprocess, no network, no calls. Everything here is arithmetic and string handling.
"""

from __future__ import annotations

import pytest

force_remote = pytest.importorskip(
    "force_remote",
    reason="research module; needs the quality-measurement directory on the path",
)


def test_the_ceiling_raises_on_the_charge_that_crosses_it():
    ledger = force_remote.Ledger(ceiling_usd=0.05)
    ledger.charge({"total_cost_usd": 0.02, "usage": {"output_tokens": 10}})
    assert ledger.calls == 1
    with pytest.raises(force_remote.CeilingReached):
        ledger.charge({"total_cost_usd": 0.04, "usage": {}})


def test_a_closed_ceiling_refuses_the_next_call_before_it_is_made():
    ledger = force_remote.Ledger(ceiling_usd=0.01)
    with pytest.raises(force_remote.CeilingReached):
        ledger.charge({"total_cost_usd": 0.02, "usage": {}})
    with pytest.raises(force_remote.CeilingReached):
        ledger.check()


def test_the_ledger_reports_what_a_result_file_needs_to_trace_a_spend():
    ledger = force_remote.Ledger(ceiling_usd=10.0)
    ledger.charge({
        "total_cost_usd": 0.021,
        "usage": {
            "cache_read_input_tokens": 20807,
            "cache_creation_input_tokens": 5677,
            "output_tokens": 643,
            "output_tokens_details": {"thinking_tokens": 300},
        },
    })
    report = ledger.report()
    assert report["calls"] == 1
    assert report["cache_read_tokens"] == 20807
    assert report["cache_write_tokens"] == 5677
    assert report["thinking_tokens"] == 300
    assert report["usd_per_call"] == pytest.approx(0.021, abs=1e-4)
    # The figures are subscription quota, not billed dollars, and the file has to say so.
    assert "equivalent quota" in report["note"]


def test_the_word_cap_is_symmetric_and_records_what_it_cut():
    high, low, record = force_remote.symmetric_seeds_by_words("a b c d e f", "g h i", cap=900)
    assert len(high.split()) == len(low.split()) == 3
    assert record["truncated"] is True
    assert record["log10_word_ratio"] > 0


def test_the_word_cap_binds_when_both_sides_are_long():
    high, low, _ = force_remote.symmetric_seeds_by_words("x " * 2000, "y " * 2000, cap=900)
    assert len(high.split()) == len(low.split()) == 900


def test_the_word_cap_never_pads_the_shorter_side():
    high, low, record = force_remote.symmetric_seeds_by_words("a " * 50, "b " * 5, cap=900)
    assert len(high.split()) == len(low.split()) == 5
    assert record["seed_words_used"] == 5


def test_length_normalisation_constants_are_ordered_sanely():
    assert force_remote.MIN_CONTINUATION_WORDS < force_remote.CONTINUATION_WORDS
    assert force_remote.MIN_CONTINUATION_WORDS > 0


def test_the_provenance_block_admits_every_weakening():
    provenance = force_remote.provenance()
    assert "UNPINNED" in provenance["revision"]
    assert "NONE" in provenance["determinism"]
    assert "instruct" in provenance["base_or_instruct"]
    # The instruction is frozen and its digest travels, so a later run cannot quietly reword it.
    assert provenance["system_prompt_digest"]
    assert provenance["instruction"] == force_remote.CONTINUATION_SYSTEM


def test_the_instruction_asks_for_no_judgment():
    """The axiom is about not asking which passage is better. This must not drift into that."""
    instruction = force_remote.CONTINUATION_SYSTEM.lower()
    for forbidden in ("better", "prefer", "which", "rate", "score", "quality", "judge", "choose"):
        assert forbidden not in instruction


def test_the_module_selftest_passes():
    assert force_remote.selftest() == 0
