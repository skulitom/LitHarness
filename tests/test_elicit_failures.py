"""A failed `claude -p` call says why, and the saying does not disturb anything cached.

What this file pins: a non-zero exit carries its code and a bounded first line of stderr into
the reason a run reports; the reason still starts with `cli_error`, so the transport-failure
predicate that decides what is counted, left uncached and re-issued by a resume is unchanged;
stdout is the fallback when stderr is silent; and the snippet is bounded so the reasons table
stays a table rather than growing one key per call.

**Why it exists.** The cost-that-bites arm was voided by 60 contiguous `cli_error`s and nothing
on disk could say whether they were a usage limit or a crashed binary — two families that argue
in opposite directions about how many workers an arm may use (stage-0 §222, §224). The reason
was that the transport discarded stdout and stderr at the moment it failed.
"""

from __future__ import annotations

import subprocess

import pytest

elicit = pytest.importorskip(
    "elicit",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


def _completed(returncode: int, stderr: str = "", stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["claude", "-p"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_a_usage_limit_and_a_crash_are_different_reasons() -> None:
    limit = elicit._cli_failure_reason(
        _completed(1, stderr="Claude AI usage limit reached|1757030400")
    )
    crash = elicit._cli_failure_reason(_completed(134, stderr="Aborted (core dumped)"))
    assert limit != crash
    assert "usage limit reached" in limit
    assert "rc=1" in limit and "rc=134" in crash


def test_every_reason_is_still_a_transport_failure() -> None:
    """The prefix is load-bearing: it decides what is counted, uncached and re-issued."""
    for completed in (
        _completed(1, stderr="Claude AI usage limit reached"),
        _completed(134, stderr="Aborted"),
        _completed(2),
        _completed(0),
    ):
        assert elicit._is_transport_failure(elicit._cli_failure_reason(completed))


def test_stdout_is_the_fallback_when_stderr_says_nothing() -> None:
    reason = elicit._cli_failure_reason(
        _completed(1, stderr="   \n\n", stdout='{"is_error":true,"result":"overloaded"}')
    )
    assert "overloaded" in reason


def test_a_failure_that_says_nothing_at_all_still_carries_its_exit_code() -> None:
    assert elicit._cli_failure_reason(_completed(9)) == "cli_error:rc=9"


def test_the_first_non_empty_line_is_taken_and_whitespace_is_collapsed() -> None:
    reason = elicit._cli_failure_reason(
        _completed(1, stderr="\n\n  rate   limited\n a second line that is not taken\n")
    )
    assert reason == "cli_error:rc=1:rate limited"


def test_the_snippet_is_bounded_so_the_reasons_table_stays_a_table() -> None:
    reason = elicit._cli_failure_reason(_completed(1, stderr="x" * 500))
    assert len(reason) <= len("cli_error:rc=1:") + elicit._CLI_STDERR_CHARS


def test_a_zero_exit_keeps_the_plain_bucket_it_never_reports() -> None:
    """Return code zero takes the parsing branch, so this value is only ever discarded."""
    assert elicit._cli_failure_reason(_completed(0, stderr="ignored")) == "cli_error"


# ----------------------------------------------------- the answer survives the fence-stripper

ARRAY = (
    '[\n  {"outcome": "first", "stance": "hope"},\n'
    '  {"outcome": "second", "stance": "dread"},\n'
    '  {"outcome": "third", "stance": "neither"}\n]'
)
OBJECT = '{"choice": "A", "reason_code": "stakes-real"}'


def test_an_array_answer_survives_whole() -> None:
    """It did not until 2026-09-04: every array was truncated to its first element and cached
    that way, which cost the anticipation probe's entire paid run (stage-0 §226)."""
    import json

    recovered = elicit._strip_fence(ARRAY)
    assert json.loads(recovered) == [
        {"outcome": "first", "stance": "hope"},
        {"outcome": "second", "stance": "dread"},
        {"outcome": "third", "stance": "neither"},
    ]


@pytest.mark.parametrize("wrapper", ["```json\n{body}\n```", "```\n{body}\n```", "{body}"])
def test_an_array_survives_fenced_and_bare(wrapper: str) -> None:
    import json

    assert len(json.loads(elicit._strip_fence(wrapper.format(body=ARRAY)))) == 3


def test_an_array_survives_commentary_after_it() -> None:
    import json

    trailing = ARRAY + "\n\nThose are the three I would expect, given the toll plot."
    assert len(json.loads(elicit._strip_fence(trailing))) == 3


def test_the_object_path_is_unchanged() -> None:
    """The shape the stripper was written for, including an object followed by prose —
    the case that made it scan for a balanced value in the first place."""
    import json

    assert json.loads(elicit._strip_fence(OBJECT)) == {
        "choice": "A",
        "reason_code": "stakes-real",
    }
    trailing = OBJECT + " ``` Passage A is a complete scene that lands on stakes I can feel..."
    assert json.loads(elicit._strip_fence(trailing))["choice"] == "A"
    assert json.loads(elicit._strip_fence("```json\n" + OBJECT + "\n```"))["choice"] == "A"


def test_an_object_wins_when_it_comes_first_and_an_array_when_it_does() -> None:
    """The opening bracket is whichever appears first, and only its own kind is matched."""
    import json

    assert isinstance(json.loads(elicit._strip_fence('{"a": [1, 2]}')), dict)
    assert isinstance(json.loads(elicit._strip_fence('[{"a": 1}, {"a": 2}]')), list)


def test_text_with_no_json_at_all_comes_back_stripped() -> None:
    assert elicit._strip_fence("  I would rather not answer that.  ") == (
        "I would rather not answer that."
    )
