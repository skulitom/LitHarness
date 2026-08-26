"""The cross-family reader seam, checked without any transport.

What this file pins: the reader-spec parser (`registry` default, `ollama:<model>`, everything
else refused), the out-filename suffix rule (default untouched, a cross-family run suffixed so
it can never overwrite a registry run), the digest-keyed replay-cache key stability, the
retry-then-None failure shape against a stubbed transport, and — the point of the seam — that
`--reader registry` leaves each instrument's built request identical to today's.
What this file does not establish: anything about any reader, cross-family or otherwise. No
network, no ollama, no registry construction and no model call happens here; the HTTP
boundary is a stub, which is the only way the retry arithmetic can be observed at all.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

reader_transport = pytest.importorskip(
    "reader_transport",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
blurb_shelf = pytest.importorskip(
    "blurb_shelf",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
blurb_rewrite = pytest.importorskip(
    "blurb_rewrite",
    reason="research module; imported by path, skipped where research/ is unavailable",
)

SCHEMA = blurb_shelf.ANSWER_SCHEMA


# ------------------------------------------------------------------------------- fakes


class _StubPost:
    """The fake HTTP boundary: scripted replies, counted calls."""

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.calls = 0

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        reply = self.replies[min(self.calls - 1, len(self.replies) - 1)]
        if isinstance(reply, Exception):
            raise reply
        return {"message": {"content": reply}}


class _FakeResult:
    def __init__(self, text: str = "A sentence.", parsed: dict[str, Any] | None = None) -> None:
        self.text = text
        self.parsed = parsed


class _CapturingRegistry:
    """Records every request it is handed; returns one canned result."""

    def __init__(self, result: _FakeResult | None = None) -> None:
        self.result = result or _FakeResult()
        self.requests: list[Any] = []

    def complete(self, request: Any) -> tuple[Any, object]:
        self.requests.append(request)
        return self.result, object()


def _ollama_reader(tmp_path: Path, post: _StubPost) -> Any:
    return reader_transport.completer(
        "ollama:qwen3:14b", cache_path=tmp_path / "cache.raw.jsonl", post=post
    )


# ------------------------------------------------------------------------- the spec parser


def test_registry_parses_to_the_default_spec_with_no_model() -> None:
    spec = reader_transport.parse_reader_spec("registry")
    assert spec.transport == "registry"
    assert spec.model is None


def test_an_ollama_spec_carries_its_model_tag_whole() -> None:
    spec = reader_transport.parse_reader_spec("ollama:qwen3:14b")
    assert spec.transport == "ollama"
    assert spec.model == "qwen3:14b"  # colons inside the tag survive


@pytest.mark.parametrize(
    ("bad",),
    [("", ), ("   ", ), ("ollama", ), ("ollama:", ), ("ollama:  ", ),
     ("claude:opus-5", ), ("registry:x", ), ("local", )],
)
def test_malformed_reader_specs_are_refused_not_guessed(bad: str) -> None:
    with pytest.raises(ValueError):
        reader_transport.parse_reader_spec(bad)


def test_the_instruments_refuse_a_malformed_reader_at_the_cli() -> None:
    with pytest.raises(SystemExit):  # argparse usage error, before anything loads
        blurb_rewrite.main(["--dry-run", "--reader", "claude:opus-5"])
    with pytest.raises(SystemExit):
        blurb_shelf.main(
            ["--dry-run", "--texts", "unused.txt", "--reader", "ollama:"]
        )


# --------------------------------------------------------------------- the filename suffix


def test_the_default_reader_leaves_the_out_filename_untouched() -> None:
    out = Path("results/blurb-shelf.json")
    spec = reader_transport.parse_reader_spec("registry")
    assert reader_transport.out_with_reader(out, spec) == out


def test_a_cross_family_reader_suffixes_the_out_filename_with_its_slug() -> None:
    out = Path("results/blurb-shelf.json")
    spec = reader_transport.parse_reader_spec("ollama:qwen3:14b")
    got = reader_transport.out_with_reader(out, spec)
    assert got == Path("results/blurb-shelf-qwen3-14b.json"), (
        "a cross-family run must never overwrite a registry run's file"
    )


# ------------------------------------------------------------------------ the cache key


def test_the_cache_key_is_stable_for_identical_inputs() -> None:
    first = reader_transport.cache_key("system", "prompt", "qwen3:14b")
    second = reader_transport.cache_key("system", "prompt", "qwen3:14b")
    assert first == second
    assert len(first) >= 64  # a full text digest, not a truncated tuple key


def test_the_cache_key_moves_with_model_system_prompt_and_draw() -> None:
    base = reader_transport.cache_key("system", "prompt", "qwen3:14b")
    assert reader_transport.cache_key("system", "prompt", "gemma3:4b") != base, (
        "a different model is a different measurement"
    )
    assert reader_transport.cache_key("other system", "prompt", "qwen3:14b") != base
    assert reader_transport.cache_key("system", "other prompt", "qwen3:14b") != base
    assert reader_transport.cache_key("system", "prompt", "qwen3:14b", sample=2) != base, (
        "K byte-identical draws are K draws of a distribution, never one cached answer"
    )


# ------------------------------------------------------------------ the ollama call shape


def test_a_conforming_reply_parses_and_an_identical_call_replays_from_cache(
    tmp_path: Path,
) -> None:
    post = _StubPost('```json\n{"off_shelf": 3, "phrase": "patch"}\n```')
    cache_path = tmp_path / "cache.raw.jsonl"
    complete = reader_transport.completer("ollama:qwen3:14b", cache_path=cache_path, post=post)
    answer, failure = complete("p", "s", SCHEMA, 64)
    assert (answer, failure) == ({"off_shelf": 3, "phrase": "patch"}, None)
    replayed, replay_failure = complete("p", "s", SCHEMA, 64)
    assert (replayed, replay_failure) == ({"off_shelf": 3, "phrase": "patch"}, None)
    assert post.calls == 1, "the identical request must replay, not re-ask"
    lines = cache_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["refused"] is False and record["model"] == "qwen3:14b"


def test_unparseable_replies_retry_at_most_twice_then_return_none(tmp_path: Path) -> None:
    post = _StubPost("not json at all")
    answer, failure = _ollama_reader(tmp_path, post)("p", "s", SCHEMA, 64)
    assert answer is None
    assert isinstance(failure, str) and failure
    assert post.calls == 3, "the initial ask plus at most two parse retries"


def test_an_out_of_schema_answer_is_refused_not_salvaged(tmp_path: Path) -> None:
    post = _StubPost('{"off_shelf": 9, "phrase": ""}')  # above the schema's maximum of 6
    answer, failure = _ollama_reader(tmp_path, post)("p", "s", SCHEMA, 64)
    assert answer is None
    assert failure == "maximum:off_shelf"
    assert post.calls == 3


def test_a_transport_error_returns_the_failure_signal_without_retry_or_cache(
    tmp_path: Path,
) -> None:
    post = _StubPost(OSError("server down"))
    cache_path = tmp_path / "cache.raw.jsonl"
    complete = reader_transport.completer("ollama:qwen3:14b", cache_path=cache_path, post=post)
    answer, failure = complete("p", "s", SCHEMA, 64)
    assert answer is None
    assert failure is not None and failure.startswith("transport_error")
    assert post.calls == 1, "an outage is not a schema problem; it does not burn retries"
    assert not cache_path.exists(), "an outage must not poison tomorrow's replay"


def test_free_text_calls_skip_schema_parsing_entirely(tmp_path: Path) -> None:
    post = _StubPost("A rewritten sentence, spoken plainly.")
    answer, failure = _ollama_reader(tmp_path, post)("p", "s", None, 64)
    assert (answer, failure) == ("A rewritten sentence, spoken plainly.", None)


def test_every_result_file_carries_exactly_one_reader_block() -> None:
    registry_block = reader_transport.reader_block(reader_transport.parse_reader_spec("registry"))
    cross_block = reader_transport.reader_block(
        reader_transport.parse_reader_spec("ollama:qwen3:14b")
    )
    assert registry_block == {"transport": "registry", "model": None}
    assert cross_block == {"transport": "ollama", "model": "qwen3:14b"}


# ------------------------------------------------------- the seam: registry bytes unchanged


def test_shelf_registry_requests_are_byte_identical_to_today() -> None:
    rows = [
        {"title": f"Title {i}", "listing": f"Listing number {i} holds.", "source": f"s{i}"}
        for i in range(6)
    ]
    prompt = blurb_shelf.render_shelf(rows)
    capturing = _CapturingRegistry(_FakeResult(parsed={"off_shelf": 0, "phrase": ""}))
    complete = reader_transport.completer(
        "registry", build_request=blurb_shelf.build_request, registry=capturing
    )
    answer, failure = complete(
        prompt, blurb_shelf.SYSTEM, blurb_shelf.ANSWER_SCHEMA, blurb_shelf.MAX_OUTPUT_TOKENS
    )

    assert failure is None
    assert answer == {"off_shelf": 0, "phrase": ""}
    request = capturing.requests[0]
    # Identical to today's construction, field by field: the frozen system, the closed schema,
    # the registered profile and cap. The frozen dataclass equality IS the byte comparison.
    assert request == blurb_shelf.build_request(prompt)
    assert request.system == "You have read serial fiction on this market for years."
    assert request.schema == blurb_shelf.ANSWER_SCHEMA
    assert request.max_output_tokens == blurb_shelf.MAX_OUTPUT_TOKENS == 400
    assert request.profile == "reader.shelf.v0"
    assert request.call_class == "generation"
    assert request.timeout_seconds == 300.0


def test_rewrite_registry_requests_are_byte_identical_to_today() -> None:
    prompt = blurb_rewrite.render_ask("A Title", "One line. Two line.", 2, "Two line.")
    capturing = _CapturingRegistry(_FakeResult(text="Two lines, written plainly."))
    complete = reader_transport.completer(
        "registry", build_request=blurb_rewrite.build_request, registry=capturing
    )
    answer, failure = complete(
        prompt, blurb_rewrite.SYSTEM, None, blurb_rewrite.MAX_OUTPUT_TOKENS
    )

    assert failure is None
    assert answer == "Two lines, written plainly."
    request = capturing.requests[0]
    assert request == blurb_rewrite.build_request(prompt)
    assert request.system == blurb_rewrite.SYSTEM
    assert request.schema is None
    assert request.max_output_tokens == blurb_rewrite.MAX_OUTPUT_TOKENS == 256
    assert request.profile == "reader.rewrite.v0"
    assert request.call_class == "generation"


def test_a_registry_outage_comes_back_as_the_same_none_signal() -> None:
    class _Exploding:
        def complete(self, request: Any) -> tuple[Any, object]:
            raise RuntimeError("provider down")

    complete = reader_transport.completer(
        "registry", build_request=blurb_rewrite.build_request, registry=_Exploding()
    )
    answer, failure = complete("p", blurb_rewrite.SYSTEM, None, 256)
    assert answer is None
    assert failure == "provider down"


def test_the_registry_seam_refuses_to_be_built_half_wired() -> None:
    with pytest.raises(ValueError):
        reader_transport.completer("registry")
