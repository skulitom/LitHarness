"""The cross-family reader seam: one `--reader` selection, both shipped instruments.

`plan/reader-architecture-program.md`, cross-family row: a claude-written listing read by a
model with no stake in claude's habits attacks self-familiarity directly. Both
`blurb_shelf.py` and `blurb_rewrite.py` currently reach exactly one model family, through
`build_default_registry()`. This module is the execution-side parameter that widens that to
`ollama:<model>` without moving anything registered: the ask, the schema, K, the legs and the
kills are properties of the instruments and are untouched.

**The seam.** `completer(reader_spec, build_request=...)` returns one callable with the call
surface both instruments already use — prompt, system, schema and max tokens in; a parsed
answer (or plain text when no schema was asked) plus a failure signal out:

    answer, failure = complete(prompt, system, schema, max_tokens, sample=draw)

`failure is None` on success. A failure comes back as `(None, reason)` — the same None signal
both instruments already exclude and count (`record["refusal"]` / `failed_draws`), never as an
exception and never scored.

- **`registry`** wraps today's path exactly: the instrument's own `build_request` builds the
  request, the adapter passes it to `registry.complete` untouched and returns `result.parsed`
  (or `result.text` when no schema). Byte-identity is structural, not coincidental — there is
  one request constructor per instrument and the adapter does not rebuild it.
- **`ollama:<model>`** follows `elicit.py`'s ollama request shape: `POST /api/chat`,
  `stream: false`, system as the first message, the schema passed natively in `format` so a
  malformed verdict is impossible at the API layer, `options.num_predict` honouring the cap,
  and `think: false` because reasoning models spend the whole budget on hidden thinking.
  Elicit's `_call_ollama` is a closure over panel state, not an importable function, and
  `elicit.py` must not be edited — so the shape repeats minimally here rather than importing
  half a persona battery to get it. Schema conformance is additionally checked by
  parse-and-retry at most twice after the fact; a transport error returns immediately without
  retries and is not cached.

**The replay cache is keyed on the text digest of system+prompt+model**, elicit's pattern:
a tuple key would claim the prompt which produced a record is the prompt rendered *today*.
The draw index rides beside the digest (elicit puts it in the key for the same reason) — K
byte-identical requests per shelf or sentence are K draws of a distribution, and collapsing
them into one cache entry would manufacture perfect cross-draw agreement out of replay.
Records persist as JSONL beside the results file, so a re-run replays identical requests for
free and the cache file doubles as the run's progress bar.

**Cross-family numbers are labelled, never pooled.** Nothing here combines rows from two
readers into one statistic, and nothing downstream can do it by accident either: every run
writes one file, the file carries a single `reader` block at the top, and a non-default
reader suffixes the default `--out` filename (`out_with_reader`) so a cross-family run cannot
overwrite a registry run. Whether the cross-family leg separates §141's gradient is the
instrument's own business; this module only makes sure its numbers arrive wearing their
reader's name.
"""

from __future__ import annotations

import json
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

#: The local transport, `elicit.py`'s endpoint. Local models only by construction: there is
#: no paid key anywhere on this path, which is what makes it admissible as an experiment side
#: arm rather than a spend decision.
OLLAMA_URL = "http://localhost:11434/api/chat"
#: Seconds on one HTTP attempt. Generous because local models queue behind each other.
OLLAMA_TIMEOUT_SECONDS = 600.0

#: Parse-and-retry at most twice: the first reply plus two more attempts before the answer is
#: refused. Ollama enforces `format` at the API layer, so reaching the retry loop at all means
#: the model answered around the schema — worth two more asks, not a silent salvage.
PARSE_RETRIES = 2

#: A completed reader call: `(parsed-or-text, failure)`; `(None, reason)` on failure.
ReaderAnswer = tuple[Any, str | None]
#: The seam callable both instruments hold: positional prompt/system/schema/max-tokens, the
#: draw index keyword-only (it separates cache entries for byte-identical draws).
Completer = Callable[..., ReaderAnswer]


@dataclass(frozen=True)
class ReaderSpec:
    """One reader selection: `registry` (the default family) or `ollama:<model>`."""

    transport: str
    #: The ollama model tag, e.g. `qwen3:14b`; always `None` for the registry transport.
    model: str | None = None


def parse_reader_spec(spec: str) -> ReaderSpec:
    """Parse a `--reader` value; refuse everything else loudly.

    `registry` is the default and names today's behaviour exactly. `ollama:<model>` selects a
    cross-family reader. Anything else — empty, a bare scheme, an unknown scheme — is a typo
    waiting to be silently read as something else, so it raises instead of guessing.
    """
    text = spec.strip()
    if text == "registry":
        return ReaderSpec(transport="registry", model=None)
    if text.startswith("ollama:"):
        model = text[len("ollama:") :].strip()
        if not model:
            raise ValueError("--reader ollama: needs a model tag, e.g. ollama:qwen3:14b")
        return ReaderSpec(transport="ollama", model=model)
    raise ValueError(f"unknown --reader {spec!r}: use 'registry' (default) or 'ollama:<model>'")


def describe(spec: ReaderSpec) -> str:
    """The spec back as the operator typed it, for stdout."""
    return spec.transport if spec.model is None else f"{spec.transport}:{spec.model}"


def reader_block(spec: ReaderSpec) -> dict[str, Any]:
    """The labelling block written once at the top of every results file.

    This block is why pooling cannot happen by accident: a result file states which reader
    produced every number under it, and a run writes exactly one file.
    """
    return {"transport": spec.transport, "model": spec.model}


def model_slug(model: str) -> str:
    """A filename-safe slug for a model tag: `qwen3:14b` -> `qwen3-14b`."""
    return re.sub(r"[^A-Za-z0-9]+", "-", model).strip("-").lower()


def out_with_reader(out: Path, spec: ReaderSpec) -> Path:
    """Suffix the default output filename with the model slug for non-default readers.

    The default reader leaves the filename untouched — today's runs land where they always
    did. A cross-family run gains `-<slug>`, so it can never overwrite a registry run's file:
    the two readers' numbers live in two files because they are two measurements.
    """
    if spec.transport == "registry":
        return out
    return out.with_name(f"{out.stem}-{model_slug(str(spec.model))}{out.suffix}")


def cache_key(system: str, prompt: str, model: str, sample: int = 0) -> str:
    """The replay-cache key: text digest of system+prompt+model, then the draw index.

    Keyed on the exact bytes asked, never on `(passage, shelf, draw)` — edit a frozen byte
    string and exactly those records miss the cache while everything else replays. The sample
    index sits *beside* the digest rather than inside it: K byte-identical requests are K
    draws of one distribution and must not collapse onto one cached answer.
    """
    material = f"{system}\n\x1f{prompt}\n\x1f{model}"
    return f"{sha256(material.encode('utf-8')).hexdigest()}:{sample}"


# --------------------------------------------------------------------------- schema checks


_SCHEMA_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _schema_problem(value: dict[str, Any], schema: dict[str, Any]) -> str | None:
    """Why `value` does not satisfy the closed schema, or None if it does.

    Deliberately shallow-but-real: required fields present, declared types holding (an
    integer is not a bool), numeric bounds honoured. The API layer enforces the schema on
    ollama; this is the belt to that braces — enough that a malformed answer can never wear a
    plausible-looking datum's clothes.
    """
    for name in schema.get("required") or []:
        if name not in value:
            return f"missing:{name}"
    properties = schema.get("properties") or {}
    for name, bound in value.items():
        property_schema = properties.get(name)
        if property_schema is None:
            if schema.get("additionalProperties") is False:
                return f"unexpected:{name}"
            continue
        expected = property_schema.get("type")
        python_type = _SCHEMA_TYPES.get(expected)
        if python_type is None:
            continue
        actual = bound
        if expected in ("integer", "number") and isinstance(actual, bool):
            return f"type:{name}"
        if not isinstance(actual, python_type):
            return f"type:{name}"
        if isinstance(actual, (int, float)) and not isinstance(actual, bool):
            minimum = property_schema.get("minimum")
            maximum = property_schema.get("maximum")
            if minimum is not None and actual < minimum:
                return f"minimum:{name}"
            if maximum is not None and actual > maximum:
                return f"maximum:{name}"
    return None


def _strip_fence(text: str) -> str:
    """Recover a JSON object from prose, elicit.py's `_strip_fence` shape.

    A fenced reply, or an object followed by commentary, is a well-formed answer the naive
    parse would drop. Scanning for the first balanced object recovers it; the caller still
    checks the decoded value against the schema, so recovery loosens the parser and never the
    schema.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            body = lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]
            stripped = "\n".join(body).strip()
    start = stripped.find("{")
    if start < 0:
        return stripped
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(stripped)):
        character = stripped[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : index + 1]
    return stripped


def _decode(text: str, schema: dict[str, Any] | None) -> ReaderAnswer:
    """Reply text to (answer, failure): parsed against the schema, or bare text."""
    if schema is None:
        return _strip_fence(text).strip(), None
    try:
        parsed = json.loads(_strip_fence(text))
    except json.JSONDecodeError:
        return None, "unparseable_json"
    if not isinstance(parsed, dict):
        return None, "not_an_object"
    problem = _schema_problem(parsed, schema)
    if problem is not None:
        return None, problem
    return parsed, None


# ------------------------------------------------------------------------ the replay cache


class ReplayCache:
    """Digest-keyed JSONL replay cache, elicit.py's pattern in miniature.

    Loaded whole from disk at construction; every new record appends one line. Point
    `cache_path` at a prior run's file and identical requests replay for free.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._records: dict[str, dict[str, Any]] = {}
        self.replayed = 0
        self.persisted = 0
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue  # a torn final line from a killed run; the next write heals it
                if isinstance(record, dict) and isinstance(record.get("key"), str):
                    self._records[record["key"]] = record

    def get(self, key: str) -> dict[str, Any] | None:
        record = self._records.get(key)
        if record is not None:
            self.replayed += 1
        return record

    def put(self, record: dict[str, Any]) -> None:
        self._records[str(record["key"])] = record
        self.persisted += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def _http_post(url: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """The real transport: one POST, elicit.py's request shape, the envelope back."""

    def post(payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            envelope = json.loads(response.read())
        return envelope if isinstance(envelope, dict) else {}

    return post


# ------------------------------------------------------------------------------- the seam


def completer(
    reader_spec: str | ReaderSpec,
    *,
    build_request: Callable[[str], Any] | None = None,
    registry: Any = None,
    cache_path: Path | None = None,
    url: str = OLLAMA_URL,
    post: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Completer:
    """Build the one seam an instrument swaps: a `--reader` selection in, a completer out.

    `build_request` is the instrument's own request constructor (its registered request
    shape); the registry path calls it per prompt and hands the result to `registry.complete`
    untouched. The ollama path ignores it and asks the local model through elicit's request
    shape instead. `post` replaces the HTTP call wholesale — that is the test seam, and the
    only way this module is exercised without a GPU.
    """
    spec = reader_spec if isinstance(reader_spec, ReaderSpec) else parse_reader_spec(reader_spec)
    if spec.transport == "registry":
        if build_request is None or registry is None:
            raise ValueError("the registry reader needs both build_request and a registry")
        return _registry_completer(build_request, registry)

    if spec.model is None:  # unreachable via parse_reader_spec; kept for direct construction
        raise ValueError("an ollama reader needs a model tag")
    sender = post if post is not None else _http_post(url)
    cache = ReplayCache(cache_path) if cache_path is not None else None
    return _ollama_completer(spec.model, sender, cache)


def _registry_completer(build_request: Callable[[str], Any], registry: Any) -> Completer:
    """Today's path, wrapped. The instrument's request bytes go through unrebuilt."""

    def complete(
        prompt: str,
        system: str,
        schema: dict[str, Any] | None,
        max_tokens: int,
        *,
        sample: int = 0,
    ) -> ReaderAnswer:
        del system, max_tokens, sample  # already inside the instrument's own constructor
        request = build_request(prompt)
        try:
            result, _resolution = registry.complete(request)
        except Exception as error:  # an outage is a fact about the day, not about the text
            return None, str(error)[:160]
        if schema is not None:
            parsed = result.parsed if isinstance(result.parsed, dict) else None
            return parsed, None
        return result.text, None

    return complete


def _ollama_completer(
    model: str,
    sender: Callable[[dict[str, Any]], dict[str, Any]],
    cache: ReplayCache | None,
) -> Completer:
    """One local-model call, elicit.py's `_call_ollama` shape, cached and retried."""

    def complete(
        prompt: str,
        system: str,
        schema: dict[str, Any] | None,
        max_tokens: int,
        *,
        sample: int = 0,
    ) -> ReaderAnswer:
        key = cache_key(system, prompt, model, sample)
        cached = cache.get(key) if cache is not None else None
        if cached is not None:
            return _decode(str(cached.get("text") or ""), schema)

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                # Greedy: conformance is the point of these calls, and elicit's sampler note
                # applies — a seed selects nothing at temperature 0 anyway.
                "temperature": 0.0,
            },
            # Reasoning models spend the whole num_predict budget on hidden thinking and
            # return empty content; elicit measured this on qwen3 before the flag existed.
            "think": False,
        }
        if schema is not None:
            payload["format"] = schema

        failure = "unanswered"
        for _attempt in range(PARSE_RETRIES + 1):
            try:
                envelope = sender(payload)
                text = str((envelope or {}).get("message", {}).get("content", "") or "")
            except Exception as error:
                # Not cached: an outage is about the day, and tomorrow the same request
                # should be free to succeed rather than replay yesterday's refusal.
                return None, f"transport_error:{type(error).__name__}:{str(error)[:120]}"
            answer, problem = _decode(text, schema)
            if problem is None:
                if cache is not None:
                    cache.put({"key": key, "model": model, "text": text, "refused": False})
                return answer, None
            failure = problem
        if cache is not None:
            # Cached as refused, like elicit caches refusals: a re-run must not respend on a
            # request this model has already shown it cannot answer within the schema.
            cache.put({"key": key, "model": model, "text": "", "refused": True})
        return None, failure

    return complete
