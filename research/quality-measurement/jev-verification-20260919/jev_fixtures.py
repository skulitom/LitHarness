"""Authored synthetic logic fixtures; no book, corpus or production inputs."""

from __future__ import annotations

import hashlib
import json

LABELS = ("contradiction", "entailment", "neutral")
VARIANTS = ("base", "rename", "reflow", "distractor", "remove_evidence")

# Each row is (family, background, hypothesis, true assertion, false assertion).
# Removing the assertion leaves the hypothesis undecided, never false by absence.
SCENARIOS = (
    (
        "negation",
        "Mira stood beside the gate.",
        "The gate is open.",
        "The gate is open.",
        "The gate is not open.",
    ),
    (
        "wrong_actor",
        "Mira and Oren were beside the bell.",
        "Mira rang the bell.",
        "Mira rang the bell; Oren did not ring it.",
        "Oren rang the bell; Mira did not ring it.",
    ),
    (
        "possession_transfer",
        "Mira held the key at dawn. It is now noon.",
        "Mira holds the key now.",
        "Mira kept the key and still holds it now.",
        "Mira handed the key to Oren and no longer holds it now.",
    ),
    (
        "location_change",
        "Mira was in the tower at dawn. It is now noon.",
        "Mira is in the tower now.",
        "Mira stayed in the tower and is still there now.",
        "Mira left the tower and is now outside it in the garden.",
    ),
    (
        "reported_speech",
        'Oren said, "The bridge collapsed." Oren sometimes lies.',
        "The bridge collapsed.",
        "The narrator confirms that the bridge did collapse.",
        "The narrator confirms that the bridge did not collapse.",
    ),
    (
        "belief_vs_fact",
        "Mira believes the chest is empty. Her beliefs are sometimes mistaken.",
        "The chest is empty.",
        "In fact, the chest is empty.",
        "In fact, the chest contains a stone and is not empty.",
    ),
    (
        "conditional",
        "If Mira pulls the lever, the alarm will sound.",
        "Mira pulled the lever.",
        "Mira pulled the lever.",
        "Mira did not pull the lever.",
    ),
    (
        "intention",
        "Mira planned to burn the letter before noon. It is now noon.",
        "Mira burned the letter before noon.",
        "Mira carried out the plan and burned the letter before noon.",
        "Mira abandoned the plan and did not burn the letter before noon.",
    ),
    (
        "partial_obligation",
        "Mira owed Oren ten coins, due today. It is now the end of today.",
        "Mira repaid all ten coins today.",
        "Mira repaid all ten coins today, leaving nothing owed.",
        "Mira repaid only three coins today and still owes seven.",
    ),
    (
        "temporal_scope",
        "Mira's lamp was lit yesterday. It is now noon today.",
        "Mira's lamp is lit now.",
        "Mira's lamp is lit at noon today.",
        "Mira's lamp is unlit at noon today.",
    ),
    (
        "speaker_attribution",
        "Mira and Oren each spoke once during the meeting.",
        'Mira said "I will return" during the meeting.',
        'Mira said "I will return", while Oren said "Goodbye".',
        'Mira said only "Goodbye", while Oren said "I will return".',
    ),
    (
        "counterfactual",
        "Mira imagined a world where Oren won the race.",
        "Oren won the actual race.",
        "In the actual world, Oren won the race.",
        "In the actual world, Oren lost the race and was not a winner.",
    ),
)

RENAMES = {"Mira": "Tessa", "Oren": "Bram"}
DISTRACTORS = [
    f"In archive room {i}, a clerk sorted blue folders and recorded the shelf numbers."
    for i in range(1, 49)
]


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def renamed(text: str) -> str:
    for old, new in RENAMES.items():
        text = text.replace(old, new)
    return text


def build_cases() -> list[dict]:
    cases = []
    for index, (family, background, hypothesis, positive, negative) in enumerate(SCENARIOS):
        for surface in range(2):
            # Surface 1 moves the decisive assertion ahead of the background and renames
            # both characters. These are dependent variants, not independent examples.
            bg, hyp, pos, neg = background, hypothesis, positive, negative
            if surface:
                bg, hyp, pos, neg = map(renamed, (bg, hyp, pos, neg))
            for original in LABELS:
                assertion = {"entailment": pos, "contradiction": neg, "neutral": ""}[original]
                parts = [bg, assertion] if not surface else [assertion, bg]
                premise = " ".join(part for part in parts if part)
                for variant in VARIANTS:
                    p, h, expected = premise, hyp, original
                    if variant == "rename":
                        # Disjoint names for each surface prevent a no-op rename control.
                        mapping = RENAMES if not surface else {"Tessa": "Lina", "Bram": "Soren"}
                        for old, new in mapping.items():
                            p, h = p.replace(old, new), h.replace(old, new)
                    elif variant == "reflow":
                        p, h = "\n  ".join(p.split()), "\n  ".join(h.split())
                    elif variant == "distractor":
                        split = (index % 3) * 24
                        p = " ".join([*DISTRACTORS[:split], p, *DISTRACTORS[split:]])
                    elif variant == "remove_evidence":
                        p, expected = bg, "neutral"
                    cases.append({
                        "id": f"{family}.{surface}.{original}.{variant}",
                        "family": family, "surface": surface, "variant": variant,
                        "original_label": original, "expected": expected,
                        "premise": p, "hypothesis": h,
                        "input_sha256": digest([p, h]),
                    })
    return cases


def manifest() -> dict:
    cases = build_cases()
    return {
        "dataset_sha256": digest(cases),
        "n_pairs": len(cases),
        "n_families": len(SCENARIOS),
        "unique_inputs": len({row["input_sha256"] for row in cases}),
        "cases": [
            {key: value for key, value in row.items() if key not in {"premise", "hypothesis"}}
            for row in cases
        ],
    }
