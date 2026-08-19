"""Panel v2, assembled: a deterministic gate, a frozen readout, and a verdict layer
that may not exist.

Stage-0 §89's Track A2'. The incumbent panel is out on three axioms (§86.6), and §87 explained why
in a way that changes the architecture rather than the tuning: **every instrument that answers a
slot fails and every instrument that measures without being asked succeeds.** So panel v2 is not a
better judge. It is a judge with two things bolted in front of it that are not judges at all.

    layer 1  counters   deterministic. Can VETO a comparison; can never pick a side.
    layer 2  readout    FROZEN_READOUT, BEHAVIOUR-class. Recorded; never decides a preference.
    layer 3  verdicts   the Track E survivor, if one survived. The only source of preference.

**Why layer 1 vetoes rather than votes, which is the whole design.** A counter measures that two
texts differ on a named axis. It does not measure which of them is better, and supplying that
valence would mean asserting craft doctrine — "told feeling is worse", "em dashes are a tell" —
which §87.1 and §87.3 record as *the hypothesis under test* rather than as a premise. §82 is
explicit: PREFERENCE is a human's blinded choice, and no machine measurement upgrades it. So a
counter here is licensed to say **"there is nothing here to prefer"** and nothing else. That is a
statement about the material, not about taste, and it is the one thing the incumbent panel could
not say: §83 and §85 both had to void arms where the panel answered the slot on near-twins, and
§78.1 measured a 96-100% preference produced by layout alone.

A veto-only layer 1 makes that failure structurally unavailable. The composite cannot express a
preference between a string and itself, or between two texts that differ only in whitespace,
because the gate returns `neither` before any judge is asked.

**Layer 3 may be empty and the composite still runs.** If no Track E protocol survives, this
object gates, ranks, and declines to prefer, and preference routes to the operator or to §80's
batch — §84 §6.4's floor, which was always the fallback and is not a failure state. A composite
with no layer 3 is a narrower machine than this project wanted and it is the one the measurements
support.

Nothing here moves a licence. Runs under `uv run python`; layer 3 spends whatever its protocol
spends and layers 1 and 2 are free.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from b6_benchmark import MEMBERS  # noqa: E402
from elicit import Comparison  # noqa: E402
from latent_fixtures import p0_features  # noqa: E402
from personas import PANEL, Persona  # noqa: E402

RESULTS = HERE / "results"

#: Collapses every run of whitespace. Two texts equal under this differ only in layout, which
#: §78.1 measured as capable of producing a 96-100% preference on its own and §87 registered as a
#: control whose recovery is VOID rather than weak.
_WHITESPACE = re.compile(r"\s+")


def _layout_only(left: str, right: str) -> bool:
    """Do these differ only in whitespace? The sham, detected rather than judged."""
    return _WHITESPACE.sub(" ", left).strip() == _WHITESPACE.sub(" ", right).strip()


def live_axes(left: str, right: str) -> dict[str, dict[str, Any]]:
    """Which admitted counters see a difference here, and how large. Signed left-to-right.

    Keyed by **axis** with the counter named in the value, rather than keyed by whichever of the
    two a caller happens to reach for. The first draft returned `{family: delta}` and the test
    written against it indexed by counter name — a lookup that raises loudly here and would have
    returned a plausible zero if the two namespaces had ever overlapped.

    Reported for every comparison whether or not the gate fires, because "the composite preferred
    B on a pair where every counter reads zero" and "…on a pair where the digit count moved by
    five" are different events and the aggregate must not merge them.
    """
    out: dict[str, dict[str, Any]] = {}
    for family, counter in MEMBERS.items():
        delta = (p0_features(right, steelman=True)[counter]
                 - p0_features(left, steelman=True)[counter])
        out[family] = {"counter": counter, "delta": round(delta, 6), "live": delta != 0}
    return out


AGGREGATION: dict[str, Any] = {
    "declared": "2026-08-19, before the composite was run through the axiom battery",
    "who_decides": (
        "Layer 3 alone decides a preference. Layer 1 decides only that there is no preference to "
        "be had. Layer 2 decides nothing and is recorded."
    ),
    "who_abstains": (
        "Layer 1 abstains on every pair that is not byte-identical and not layout-only — it has "
        "no valence for any axis and inventing one would assert craft doctrine as a premise "
        "(§87.1, §87.3). Layer 3 abstains by answering `neither`, which is preserved and never "
        "overwritten. Layer 2 abstains from preference by construction (§82, BEHAVIOUR at STORY "
        "grain)."
    ),
    "what_disagreement_produces": (
        "A recorded diagnostic and no change of verdict. Layer 2 ranking one way while layer 3 "
        "prefers the other is exactly §87's report deficit showing up inside one instrument, and "
        "it is the composite's most informative output — but resolving it in the readout's favour "
        "would let BEHAVIOUR-class evidence decide a preference, which §82 forbids, and resolving "
        "it in the verdict's favour would discard the only signal that the deficit is present."
    ),
    "veto_precedence": (
        "Layer 1 runs first and its veto is final. A vetoed comparison is `neither` with "
        "`reason_code='none'`, layer 3 is never called, and no money is spent on it."
    ),
    "what_it_cannot_do": (
        "Express a preference between a string and itself, or between two texts differing only in "
        "whitespace. Both were live failure modes of the incumbent (§83, §85, §78.1) and both are "
        "now unreachable rather than merely unlikely."
    ),
}

#: A layer-3 protocol: given (persona, left, right, orientation, sample) it returns a slot-frame
#: choice and a reason code, or `(None, None)` for a refusal. Deliberately the narrowest signature
#: that a Track E survivor can satisfy, so that swapping the protocol swaps one function.
Verdict = Callable[[Persona, str, str, int, int], tuple[str | None, str | None]]


class Composite:
    """The three layers, wired. An `Elicit` callable once bound to a pair.

    `verdict_layer` is `None` when no Track E protocol survived. The object is still usable and
    still passes through the axiom battery — it gates, records, and returns `neither` everywhere
    else — and `verdict_source` says so in the report rather than leaving a reader to infer it
    from a column of ties.
    """

    def __init__(
        self,
        verdict_layer: Verdict | None,
        *,
        personas: Sequence[Persona] = PANEL[:2],
        verdict_source: str = "none — no Track E protocol survived (§89)",
        readout: dict[str, Any] | None = None,
    ) -> None:
        self.verdict_layer = verdict_layer
        self.personas = tuple(personas)
        self.verdict_source = verdict_source
        self.readout = readout
        self.vetoed: list[dict[str, Any]] = []
        self.diagnostics: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ layer 1

    def gate(self, left: str, right: str) -> tuple[bool, str]:
        """Is there anything here to prefer? `(vetoed, why)`."""
        if left == right:
            return True, "byte-identical: there is no difference to prefer"
        if _layout_only(left, right):
            return True, "layout-only: §78.1 measured this producing 96-100% preference alone"
        return False, ""

    # ------------------------------------------------------------------ the callable

    def __call__(self, pair: Any) -> list[Comparison]:
        """One `axiom_battery.Pair` in, a list of `elicit.Comparison` out.

        `pair.left` is the original and `pair.right` the variant, and `Comparison.chose_variant`
        undoes the orientation swap — so this must answer in the **slot frame** (`"A"`/`"B"`),
        never in the left/right frame. That translation is the single likeliest place a composite
        gets it wrong, so it is done once, here, and nowhere else.
        """
        vetoed, why = self.gate(pair.left, pair.right)
        axes = live_axes(pair.left, pair.right)
        if vetoed:
            self.vetoed.append({"pair_id": pair.pair_id, "why": why, "live_axes": axes})
            return [
                Comparison(pair_id=pair.pair_id, persona_id=persona.persona_id, sample=sample,
                           model=f"composite/{self.verdict_source}", orientation=orientation,
                           choice="neither", reason_code="none", refused=False, usage={})
                for persona in self.personas
                for sample in range(getattr(pair, "samples", 1))
                for orientation in (0, 1)
            ]
        if self.verdict_layer is None:
            # No preference source. `neither` is the honest answer and it is a different event
            # from a veto, so it is not recorded in `vetoed`.
            return [
                Comparison(pair_id=pair.pair_id, persona_id=persona.persona_id, sample=sample,
                           model="composite/no-verdict-layer", orientation=orientation,
                           choice="neither", reason_code="none", refused=False, usage={})
                for persona in self.personas
                for sample in range(getattr(pair, "samples", 1))
                for orientation in (0, 1)
            ]
        out: list[Comparison] = []
        for persona in self.personas:
            for sample in range(getattr(pair, "samples", 1)):
                for orientation in (0, 1):
                    first, second = ((pair.left, pair.right) if orientation == 0
                                     else (pair.right, pair.left))
                    choice, reason = self.verdict_layer(
                        persona, first, second, orientation, sample
                    )
                    out.append(Comparison(
                        pair_id=pair.pair_id, persona_id=persona.persona_id, sample=sample,
                        model=f"composite/{self.verdict_source}", orientation=orientation,
                        choice=choice, reason_code=reason, refused=choice is None, usage={},
                    ))
        if self.readout is not None:
            self.diagnostics.append({
                "pair_id": pair.pair_id, "live_axes": axes,
                "note": "layer 2 recorded; it decides nothing (§82)",
            })
        return out

    def report(self) -> dict[str, Any]:
        """What the composite did, in the terms the aggregation was declared in."""
        return {
            "aggregation": AGGREGATION,
            "verdict_source": self.verdict_source,
            "layer_3_present": self.verdict_layer is not None,
            "vetoed": len(self.vetoed),
            "veto_detail": self.vetoed[:20],
            "readout": self.readout,
            "personas": [persona.persona_id for persona in self.personas],
        }


def selftest() -> int:
    """The gate and the frame, checked before the composite is pointed at the battery."""
    from dataclasses import dataclass

    @dataclass
    class _Pair:
        pair_id: str
        left: str
        right: str
        samples: int = 1
        question: str = "preference"

    failures: list[str] = []

    def check(claim: str, ok: bool) -> None:
        if not ok:
            failures.append(claim)

    composite = Composite(None)
    check("identical text is vetoed", composite.gate("a b c", "a b c")[0])
    check("whitespace-only differences are vetoed",
          composite.gate("a b\n\nc", "a  b\nc")[0])
    check("a real difference is not vetoed", not composite.gate("a b c", "a b d")[0])

    made = composite(_Pair("p1", "a b c", "a b c"))
    check("a veto answers every cell", len(made) == 2 * len(composite.personas))
    check("a veto answers `neither`", all(c.choice == "neither" for c in made))
    check("a veto is recorded", composite.vetoed and composite.vetoed[0]["pair_id"] == "p1")

    # The frame check: a layer 3 that always names the *variant* must come back as
    # `chose_variant` in both orientations, or the slot translation is inverted.
    def always_variant(_p: Persona, _a: str, _b: str, orientation: int, _s: int
                       ) -> tuple[str | None, str | None]:
        return ("B" if orientation == 0 else "A"), "curious"

    framed = Composite(always_variant, verdict_source="test")
    made = framed(_Pair("p2", "original", "variant"))
    check("the slot frame is not inverted", all(c.chose_variant for c in made))

    def always_original(_p: Persona, _a: str, _b: str, orientation: int, _s: int
                        ) -> tuple[str | None, str | None]:
        return ("A" if orientation == 0 else "B"), "curious"

    made = Composite(always_original, verdict_source="test")(_Pair("p3", "original", "variant"))
    check("preferring the original reads as not-variant", not any(c.chose_variant for c in made))

    empty = Composite(None)(_Pair("p4", "wholly different", "text entirely"))
    check("no layer 3 means `neither`, not a refusal",
          all(c.choice == "neither" and not c.refused for c in empty))

    for message in failures:
        print(f"  FAIL {message}", file=sys.stderr)
    print(f"composite selftest: {'PASS' if not failures else str(len(failures)) + ' FAILURES'}",
          file=sys.stderr)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--describe", action="store_true", help="print the declared aggregation")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.describe:
        print(json.dumps(AGGREGATION, indent=2))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
