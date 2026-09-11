"""Research mechanics: precommitted selection and controlled prompt differences."""

import importlib.util
import random
from pathlib import Path

import pytest

PATH = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/invention-contrast-20260911/run.py"
)
SPEC = importlib.util.spec_from_file_location("invention_contrast_experiment", PATH)
assert SPEC is not None and SPEC.loader is not None
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def test_contrast_selection_replays_without_changing_global_random_state():
    state = random.getstate()
    number = str((1 << 2047) + 713)
    selected = experiment.selected_index(number)
    assert selected == experiment.selected_index(number)
    assert 0 <= selected < 6
    assert random.getstate() == state


def test_contrast_manipulations_preserve_the_prefix_and_other_instructions():
    prefix = "OPAQUE_PREFIX"
    rendered = {a: experiment.system_text(prefix, a) for a in experiment.ARMS}
    assert all(t.startswith(prefix + "\n\n") for t in rendered.values())
    assert (
        rendered["single"].replace("exactly 1 premise.", "exactly 6 premises.")
        == rendered["batch"]
    )
    assert rendered["contrast"] == rendered["batch"] + "\n\n" + experiment.CONTRAST
    assert rendered["representative"] == rendered["contrast"] + "\n\n" + experiment.REPRESENTATIVE
    assert rendered["placebo"] == rendered["contrast"] + "\n\n" + experiment.PLACEBO
    assert len(experiment.REPRESENTATIVE) == len(experiment.PLACEBO)
    assert len(experiment.REPRESENTATIVE.split()) == len(experiment.PLACEBO.split()) == 4


@pytest.mark.parametrize("payload", [
    None, {"premises": ["one"]}, {"premises": ["one"] * 5 + [""]},
    {"premises": ["one"] * 5 + [42]}, {"premises": ["one"] * 6, "best": 3},
])
def test_malformed_batches_cannot_choose_a_replacement(payload):
    with pytest.raises(ValueError):
        experiment.parse_premises(payload, 6)


def test_selection_preserves_exact_text_and_list_order():
    premises = [f"  Candidate {i}.\n" for i in range(6)]
    parsed = experiment.parse_premises({"premises": premises}, 6)
    selected = experiment.selected_index("123456789")
    assert parsed[selected] == premises[selected]
    assert parsed == premises
