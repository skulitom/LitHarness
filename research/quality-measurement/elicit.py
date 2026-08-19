"""The elicitation front-end: ask a persona what reading a passage was like, and record it.

`personas.py` owns the readers and their prompts; this module owns the calls, the cache, and
the record. `plan/persona-reader-validity.md` is the protocol; `persona_battery.py` is the
driver that points this at `ablate.py`'s manufactured ground truth.

**Two stages, and only the second is calibrated.** Stage 1 is unprimed free text — "you've just
read this, what's going on for you?" — recorded as colour and never scored. Stage 2 is a forced
choice in the audit vocabulary plus at most one reason code, and it is a *second turn of the
same conversation*, so the persona is committing to a category after having already reacted
rather than reacting through the category. Stage 1 exists so the vocabulary is not planted in
the asking; that is the whole reason it costs a round trip.

**Stage 2 is a structured output, not a parsed one.** `output_config.format` with
`personas.STAGE2_SCHEMA` constrains the verdict to the three-way enum and the reason to the
closed code list at the API layer, so there is no regex, no retry-on-parse loop, and no path by
which a malformed answer becomes a plausible-looking datum. The schema is closed
(`additionalProperties: false`) and every field required, because §69 found the recognition
check bypassable by omission — an absent field defaulting to something benign is the shape of
defect this project has already been bitten by once.

**A refusal is recorded as a refusal.** Frontier models can decline a request outright
(`stop_reason == "refusal"`, HTTP 200, empty or partial content). The record carries
`refused: true` and no verdict, and `persona_battery.py` drops those samples from the rates
rather than reading them as `not-sure`. Silently coercing a refusal into the middle category
would put a safety classifier's behaviour into a reader-response distribution.

**One passage per conversation, which is narrower than "incremental reading" and deliberately so.**
Each cell is an independent two-turn conversation carrying one passage and no history. That is the
right frame for gate 1 — every manipulation in the protocol's §5 is a within-passage edit, so
reading cold is what isolates the edit from context effects — and it is what keeps a cell's `n`
samples independent, which gate 0's ICC assumes. The cost is that the panel cannot notice a promise
left unpaid across scenes, which is much of what the `stakes` and `grinder` personas are defined to
read *for*, and it is why gate 3's drop-point prediction cannot run through this module as written.
The protocol's §3 carries the per-gate reasoning; this note exists so the narrower claim is visible
where somebody would otherwise assume the broader one.

**`n` samples per persona per boundary means `n` byte-identical requests.** The datum is a
response distribution, so variation has to come from the model's own sampling — not from
perturbing the prompt, which would confound sample variance with prompt variance, and not from
`temperature`, which the current frontier models reject outright. Byte-identical prompts also
make the samples cacheable *in principle*; whether the cache engages is a property of the panel
model's minimum prefix length, and on the default it does not — see `_cell`.

**The cache is keyed by a digest of the exact request, not by `(passage, persona, sample)`.**
§56's lesson, applied one instrument over: a tuple key holds a claim the log cannot back — that
the prompt which produced a record is the prompt `personas.py` renders *today*. Edit a system
prompt and every record under a tuple key replays as if nothing changed, and the run completes
carrying measurements of a persona that no longer exists. Keyed by request digest, a persona
edit misses the cache for exactly its own records and hits it for everything else.

**Cost, and where the Batch API would go.** The panel runs on a cheap system-promptable model
with frontier spot checks on a fraction, per §70's cost note. The full gate-1 sweep is roughly 4
personas x 5 samples x ~25 variants x ~30 passages of two-call cells, which lands in the tens of
dollars on the default tier — small enough that the deciding factor is turnaround rather than
price, and the Batches API's asynchronous window is the wrong trade for an instrument still
being iterated on. Two stages would also make batching two dependent rounds rather than one.
Batching is the change to make for an unattended full sweep, and the record format does not move
when it happens.

**Spot checks compare two things at once, and the docstring says so rather than the summary.**
A frontier spot check differs from the panel model in tier *and* in deliberation depth (the
cheap model runs with no thinking; the frontier one runs adaptive at low effort, because
disabling thinking on that family has its own failure modes). A panel/spot disagreement
therefore cannot be attributed to tier alone. Deliberation depth is a declared parameter of the
instrument for exactly this reason — it is pre-registered in the summary, not chosen per run.

Needs the `persona` extra (`uv sync --extra persona`) and credentials the Anthropic SDK can
find. Never run from the production loop: this is research code that spends money.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from personas import (  # noqa: E402
    BY_ID,
    KEEP_CODES,
    PAIR_CHOICES,
    PAIR_SCHEMA,
    PANEL,
    REASON_CODES,
    STAGE2_SCHEMA,
    STOP_CODES,
    VERDICTS,
    Persona,
    anchor_agreement,
    fidelity_probe,
    pair_turn,
    stage1_turn,
    stage2_turn,
    system_prompt,
)

#: The panel model. Cheap and system-promptable, per §70's cost note — the panel is a
#: distribution of many samples, and the money belongs in the sample count rather than the tier.
PANEL_MODEL = "claude-haiku-4-5"
#: The spot-check model. Frontier, run on a fraction of the schedule to bound how much of the
#: result is an artifact of the cheap tier.
SPOT_MODEL = "claude-opus-5"
#: Fraction of (passage, persona) cells that also run on `SPOT_MODEL`. Chosen deterministically
#: from the request digest, so the spot subset is a function of the schedule and not of the run.
SPOT_FRACTION = 0.10

#: Deliberation depth, declared rather than chosen per run. `None` means no effort parameter is
#: sent, which is required on the Haiku family (it rejects `effort`) and means no thinking.
PANEL_EFFORT: str | None = None
SPOT_EFFORT: str | None = "low"

STAGE1_MAX_TOKENS = 350
STAGE2_MAX_TOKENS = 120
PROBE_MAX_TOKENS = 400
#: A pair answer is one JSON object; the passages are input, not output.
PAIR_MAX_TOKENS = 160

MAX_WORKERS = 8
MAX_RETRIES = 6

#: Fewer workers on the CLI transport: each call is a process, not a socket.
CLI_MAX_WORKERS = 4
CLI_TIMEOUT_SECONDS = 300.0
#: The hardening `providers/cli.py` earned, copied rather than imported — research code must not
#: depend on `src/`, and each flag there carries the reason it is not optional. Two differences,
#: both deliberate, both about the persona: this uses `--system-prompt` (which *replaces*) where
#: the production adapter uses `--append-system-prompt`, and it strips the dynamic sections. A
#: reader persona appended to "You are Claude Code, an interactive CLI tool" is not a reader — it
#: is an agent wearing a reader's answers, which is the caricature failure arriving through the
#: transport instead of through the prompt.
CLI_HARDENING = (
    "--exclude-dynamic-system-prompt-sections",
    "--allowed-tools", "",
    "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
    "--no-session-persistence",
    "--permission-mode", "manual",
)


#: The local transport. Ollama on the 4090 — see BRIEF.md §4 for what is in the cache.
OLLAMA_URL = "http://localhost:11434/api/chat"
#: One GPU serialises anyway, and concurrent requests only compete for the same VRAM.
OLLAMA_MAX_WORKERS = 1
OLLAMA_TIMEOUT_SECONDS = 300.0
#: Sleep this multiple of each call's duration after it, and hold while the card is hot.
#: `cdg_battery.py` earned these numbers the expensive way — a thermal shutdown killed a run at
#: call 431 — and its measured constants are 3.0 / 72 / 66 for a transformers workload that
#: saturates the card with back-to-back forward passes. Ollama at 4B is lighter per call, so the
#: duty cycle defaults lower and the **temperature governor is the actual protection**; the rest
#: ratio is only a coarse pre-emptive measure. Raise `--rest-ratio` if the card still climbs.
OLLAMA_REST_RATIO = 1.0
OLLAMA_PAUSE_ABOVE_C = 72
OLLAMA_RESUME_BELOW_C = 66
OLLAMA_POLL_SECONDS = 5.0


def gpu_temperature() -> int | None:
    """Current GPU core temperature, or None on a machine this cannot read."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return int(out.stdout.strip().splitlines()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def _supports_effort(model: str) -> bool:
    """Whether `output_config.effort` is accepted. The Haiku family errors on it."""
    return not model.startswith("claude-haiku")


def digest(payload: object) -> str:
    """Stable digest of a request payload. Sorted keys so dict order is never in the key."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def _block_text(content: Any) -> str:
    """Text out of a turn's content, which is either a string or a list of blocks."""
    if isinstance(content, str):
        return content
    return "\n".join(
        str(block.get("text", "")) for block in content if block.get("type") == "text"
    )


def _flatten_turns(turns: list[dict[str, Any]]) -> str:
    """SDK turns rendered as one prompt, for a transport that has no multi-turn form.

    **This is the one place the two transports are not the same measurement, and it is worth
    being exact about.** On the SDK, stage 2 is a genuine third turn: the persona's stage-1 answer
    is an `assistant` message and the model is continuing its own conversation. `claude -p` is
    single-shot, so the same conditioning is reconstructed as a transcript inside one user turn —
    the passage, the question it was asked, the answer it gave, then the stage-2 question.

    The property the protocol actually needs survives: stage 2 is answered *after* a stage-1
    answer exists and in its presence, so the categories are still not planted in the asking. What
    does not survive is the assistant-turn framing, and a model can treat quoted-back text as
    someone else's words. Read a CLI-transport stage 2 as "given this reaction, which category"
    rather than as "you said this, now commit to it"; if the two transports disagree on the same
    passages, this is the first place to look.
    """
    if len(turns) == 1:
        return _block_text(turns[0]["content"])
    parts: list[str] = []
    for turn in turns:
        text = _block_text(turn["content"])
        if turn["role"] == "user":
            parts.append(text)
        else:
            parts.append(f"Your answer was:\n\n{text}")
    return "\n\n---\n\n".join(parts)


def _strip_fence(text: str) -> str:
    """Recover the JSON object from a transport with no structured-output guarantee.

    **This replaced a stricter version that discarded 72% of a metered run.** The first
    implementation only unwrapped text that *began* with a fence. `claude -p` answers the pair
    question with the object first and then keeps talking:

        {"choice": "A", "reason_code": "stakes-real"} ``` Passage A is a complete scene that
        lands on stakes I can feel...

    That is a well-formed answer with a suffix, and `json.loads` over the whole string fails on
    it. 370 of 512 pair records were being dropped as unparseable — not refused, not malformed,
    just followed by commentary. Scanning for the first balanced object recovers all of them, and
    because the raw text is cached, re-running re-parses the existing log without a single new
    call.

    **This loosens the parser, never the schema.** The caller still checks the decoded value
    against the closed choice and reason-code enums, so a recovered object that says something
    outside them is still discarded. What is given up is the "no regex, no salvage" property the
    SDK transport has by construction — and that property was never true here, which `_call_cli`
    already records: on this transport the schema is an instruction rather than a guarantee.
    Silently binning three-quarters of the evidence is the worse failure, and a *selective* one,
    since a model that adds commentary is plausibly a model that was less decisive.
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


#: Stand-in answers for the verbalize protocol, spanning the axes its matchers look for and some
#: they do not. Kept beside `_synthetic_text` rather than in `elicitation_study` so that every
#: dry-run answer in this project is written in one place, under the same no-signal rule.
_DRY_DIFFERENCES: tuple[str, ...] = (
    "(dry run) One has numbers in the status block and the other does not.",
    "(dry run) One gives access to the character's thoughts and the other stays outside.",
    "(dry run) One uses em dashes where the other uses full stops.",
    "(dry run) One is longer.",
    "(dry run) The paragraphs are broken up differently.",
    "(dry run) They read the same to me.",
)


#: Stop reasons that mean **no judgment was ever obtained** — the process died, timed out, or the
#: CLI returned an error envelope. They are not cached, and the distinction is §87.3's:
#: `gpt-oss:20b` returned 32 of 32 transport errors there and folding those into "ineligible"
#: would have reported a model as answering a slot it never answered, letting a broken install
#: masquerade as evidence about judges. `NOT_SCREENABLE` is its own state.
#:
#: **The cache is where that distinction has teeth.** A refusal is a measurement and belongs in
#: the replay cache; a transport failure is the absence of one, and caching it bakes a network
#: hiccup into every future run of the same schedule — a thousand-call sweep would carry its own
#: flakiness forward permanently and no resume could ever repair it. So these records are
#: returned to the caller, which marks the cell unscored for *this* run, and are not persisted:
#: a resume re-issues exactly them and nothing else.
_TRANSPORT_FAILURES = ("transport_error", "cli_error", "cli_is_error")


def _is_transport_failure(stop_reason: str) -> bool:
    """Did this call fail to obtain an answer at all, as opposed to obtaining a refusal?"""
    return stop_reason.startswith(_TRANSPORT_FAILURES)


def _synthetic_text(key: str, tag: dict[str, Any]) -> str:
    """A dry run's stand-in answer: deterministic, and deliberately carrying **no signal**.

    Dry-run mode exists to exercise the arithmetic downstream of these calls — ICC, the variance
    decomposition, the collapse correlation, the de-stake comparison — none of which had ever run
    on anything but empty data, because the first version of this branch returned an empty string
    and every sample came back `refused`. A pipeline whose statistics have never executed is a
    pipeline whose first real run is also its first integration test.

    **The verdict is drawn from a hash of the request key and ignores the ablation entirely**, so
    a dry run is a draw from the null: ICC should land near zero, `detect_auc` near 0.5, and the
    verdict should read DEAD. That is a property worth asserting rather than a limitation — see
    `persona_battery.selftest`. Synthesising a *plausible* signal here would be worse than
    useless: a fabricated `detect_auc` of 0.7 sitting in a summary file is exactly the number
    somebody quotes six months later.
    """
    marker = int(key.split(":")[0][:8], 16)
    if tag.get("stage") == "pair":
        # Orientation is in the key, so the two orientations of a pair draw independently —
        # which is what lets a dry run exercise `positional_bias` rather than only the win rate.
        choice = PAIR_CHOICES[marker % len(PAIR_CHOICES)]
        codes = STOP_CODES if choice == "neither" else KEEP_CODES
        return json.dumps({
            "choice": choice,
            "reason_code": codes[(marker // 3) % len(codes)],
        })
    if tag.get("stage") == 2:
        verdict = VERDICTS[marker % len(VERDICTS)]
        codes = STOP_CODES if verdict == "would-stop" else KEEP_CODES
        return json.dumps({
            "verdict": verdict,
            "reason_code": codes[(marker // 3) % len(codes)],
        })
    # `elicitation_study.py`'s protocols, on the same terms as everything above: the answer is a
    # function of the request key and never of which side or which family is being asked about,
    # so a dry run is a draw from the null and every protocol should read FAILS on it. Without
    # these the study's scorers parse nothing, every response counts as refused, and the dry run
    # exercises exactly the code path a real run never takes.
    if tag.get("stage") == "scalar":
        return json.dumps({"rating": marker % 101})
    if tag.get("stage") == "describe":
        return "(dry run) The first passage read one way and the second read another."
    if tag.get("stage") == "judge":
        choice = PAIR_CHOICES[marker % len(PAIR_CHOICES)]
        codes = STOP_CODES if choice == "neither" else KEEP_CODES
        return json.dumps({"choice": choice, "reason_code": codes[(marker // 3) % len(codes)]})
    if tag.get("stage") == "verbalize":
        # Phrases rather than one string, because E6 is scored by regex matchers and a fixed
        # answer would make every matcher fire always or never. Some of these hit an axis and
        # some do not; which one a call draws is the hash's business, so the *rate* at which any
        # matcher fires is the same on every family, which is the null E6's Fisher test needs.
        return json.dumps({"difference": _DRY_DIFFERENCES[marker % len(_DRY_DIFFERENCES)]})
    if tag.get("stage") == 0:
        persona = BY_ID.get(str(tag.get("persona", "")))
        anchors = persona.held_out_anchors if persona else ()
        return json.dumps({
            "verdicts": [
                {
                    "work": anchor.work,
                    "verdict": VERDICTS[(marker + index) % len(VERDICTS)],
                    "reason_code": REASON_CODES[(marker + index) % len(REASON_CODES)],
                }
                for index, anchor in enumerate(anchors)
            ]
        })
    return "(dry run: no model was called)"


@dataclass(frozen=True, slots=True)
class Sample:
    """One persona's two-stage response to one passage, at one sample index.

    `stage1` is colour. `verdict` and `reason_code` are the calibrated datum, and both are None
    on a refusal — the field that says a safety classifier answered instead of a reader.
    """

    passage_id: str
    persona_id: str
    sample: int
    model: str
    stage1: str
    verdict: str | None
    reason_code: str | None
    refused: bool
    request_digest: str
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def would_stop(self) -> bool:
        return self.verdict == "would-stop"


@dataclass(frozen=True, slots=True)
class Comparison:
    """One persona's blinded choice between a passage and its manipulated copy.

    `orientation` records which side the original was shown on, so positional bias is
    recoverable from the log rather than only from the aggregate: a persona answering the same
    *position* across both orientations has reported on layout, not on prose.
    """

    pair_id: str
    persona_id: str
    sample: int
    model: str
    orientation: int
    choice: str | None
    reason_code: str | None
    refused: bool
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def chose_variant(self) -> bool:
        """Whether the choice landed on the manipulated text, undoing the orientation swap."""
        if self.choice not in ("A", "B"):
            return False
        variant_side = "B" if self.orientation == 0 else "A"
        return self.choice == variant_side


def positional_bias(comparisons: list[Comparison]) -> dict[str, object]:
    """How often the panel picked a *side* rather than a text. §69's check, ported.

    RevisionBench measured 43-65% positional artifacts in model judges, which is the measurement
    that made position-swapping non-optional for the human channel; a persona panel gets checked
    on the same terms rather than trusted. A rate far from 0.5 means the instrument is reading
    layout, and every preference it reports is suspect regardless of how cleanly it separates.
    """
    decided = [c for c in comparisons if c.choice in ("A", "B")]
    if not decided:
        return {"decided": 0, "chose_A_rate": float("nan"), "note": "no decided comparisons"}
    chose_a = sum(1 for c in decided if c.choice == "A")
    per_persona: dict[str, float] = {}
    for persona in sorted({c.persona_id for c in decided}):
        mine = [c for c in decided if c.persona_id == persona]
        per_persona[persona] = round(sum(1 for c in mine if c.choice == "A") / len(mine), 4)
    return {
        "decided": len(decided),
        "chose_A_rate": round(chose_a / len(decided), 4),
        "per_persona_chose_A": per_persona,
        "note": "0.5 is unbiased; distance from it is the share of the answer that is layout",
    }


class Elicitor:
    """Calls, cached and concurrent, with the record as the primary artifact.

    The cache file is append-only JSONL and is both the output and the resume point. A run
    interrupted anywhere replays every record whose request digest still matches and re-issues
    only the rest — the same discipline `cdg_battery.py` earned when a thermal shutdown killed
    a run at call 431, arriving here because an interrupted API sweep has the same shape and a
    per-call cost.
    """

    def __init__(
        self,
        cache_path: Path,
        *,
        model: str = PANEL_MODEL,
        spot_model: str | None = SPOT_MODEL,
        spot_fraction: float = SPOT_FRACTION,
        effort: str | None = PANEL_EFFORT,
        spot_effort: str | None = SPOT_EFFORT,
        max_workers: int | None = None,
        transport: str = "cli",
        pair_question: str = "preference",
        temperature: float = 0.8,
        no_think: bool = True,
        rest_ratio: float = OLLAMA_REST_RATIO,
        dry_run: bool = False,
    ) -> None:
        self.cache_path = cache_path
        self.model = model
        self.spot_model = spot_model
        self.spot_fraction = spot_fraction
        self.effort = effort
        self.spot_effort = spot_effort
        self.transport = transport
        self.pair_question = pair_question
        self.temperature = temperature
        self.no_think = no_think
        self.rest_ratio = rest_ratio
        self.max_workers = max_workers if max_workers is not None else {
            "cli": CLI_MAX_WORKERS, "ollama": OLLAMA_MAX_WORKERS,
        }.get(transport, MAX_WORKERS)
        self.dry_run = dry_run
        self._client: Any | None = None
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, Any]] = {}
        self._handle: Any = None
        self.api_calls = 0
        self.replayed = 0
        #: Calls that obtained no answer at all. Counted, never cached — see
        #: :func:`_is_transport_failure`. A run that reports a verdict beside a
        #: non-zero count here is reporting on the cells that answered.
        self.transport_failures = 0
        self._load_cache()

    # ------------------------------------------------------------------ cache plumbing

    def _load_cache(self) -> None:
        """Replay a prior run's records. Tolerates exactly one truncated final line."""
        if not self.cache_path.is_file():
            return
        kept = 0
        for line in self.cache_path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # the shape an interrupted write leaves; redoing is cheap
            key = record.get("key")
            if isinstance(key, str):
                self._cache[key] = record
                kept += 1
        if kept:
            print(f"replaying {kept} cached call(s) from {self.cache_path.name}",
                  file=sys.stderr, flush=True)

    def _open(self) -> Any:
        if self._handle is None:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self.cache_path.open("a", encoding="utf-8")
        return self._handle

    def _persist(self, record: dict[str, Any]) -> None:
        handle = self._open()
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> Elicitor:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -------------------------------------------------------------------- the API layer

    def _sdk(self) -> Any:
        """Lazy client. Imported here so `personas.py` and the schedule stay import-free."""
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - environment, not logic
                raise SystemExit(
                    "elicit.py needs the anthropic SDK: uv sync --extra persona"
                ) from exc
            if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
                # Not fatal: `ant auth login` stores a profile the SDK reads with no env var.
                print("no ANTHROPIC_API_KEY set; relying on an `ant auth login` profile",
                      file=sys.stderr, flush=True)
            self._client = anthropic.Anthropic(max_retries=MAX_RETRIES)
        return self._client

    def _params(
        self,
        persona: Persona,
        turns: list[dict[str, Any]],
        *,
        model: str,
        effort: str | None,
        max_tokens: int,
        schema: dict[str, object] | None,
    ) -> dict[str, Any]:
        """Build one request. The caller places the cache breakpoint; see `_cell`.

        The breakpoint is deliberately *not* on the system block. A breakpoint marks a prefix,
        and the prefix has to clear the model's minimum cacheable length or it silently does
        nothing — no error, just `cache_creation_input_tokens: 0`. A persona system prompt is
        about 300 tokens, under every current model's floor, so a system-only breakpoint would
        look like caching and never cache. `_cell` puts it after the passage instead, which is
        the longest prefix shared by both stages and all `n` samples.
        """
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt(persona),
            "messages": turns,
        }
        output_config: dict[str, Any] = {}
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        if effort is not None and _supports_effort(model):
            output_config["effort"] = effort
        if output_config:
            params["output_config"] = output_config
        return params

    def _call(self, params: dict[str, Any], *, sample: int, tag: dict[str, Any]) -> dict[str, Any]:
        """One cached call. The key is the request digest plus the sample index.

        The sample index is in the key rather than the payload: `n` samples of one cell are `n`
        byte-identical requests, so without it they would collide into a single cache entry and
        the "distribution" would be one draw repeated.
        """
        # Transport is inside the key, not beside it: a CLI answer and an SDK answer to the same
        # prompt are two different measurements (different system-prompt handling, different
        # multi-turn form — see `_flatten_turns`), and serving one from a cache the other filled
        # would pool them into a single distribution that describes neither.
        key = f"{digest({'params': params, 'transport': self.transport})}:{sample}"
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self.replayed += 1
                return cached
        if self.dry_run:
            return {
                **tag,
                "key": key,
                "model": params["model"],
                "text": _synthetic_text(key, tag),
                "refused": False,
                "usage": {},
                "dry_run": True,
            }
        if self.transport == "ollama":
            return self._call_ollama(params, sample=sample, key=key, tag=tag)
        if self.transport == "cli":
            return self._call_cli(params, key=key, tag=tag)

        response = self._sdk().messages.create(**params)
        refused = response.stop_reason == "refusal"
        text = ""
        if not refused:
            text = "".join(
                block.text for block in response.content if getattr(block, "type", "") == "text"
            )
        usage = {
            "input": getattr(response.usage, "input_tokens", 0),
            "output": getattr(response.usage, "output_tokens", 0),
            "cache_read": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            "cache_write": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
        }
        record = {
            "key": key,
            "model": params["model"],
            "text": text,
            "refused": refused,
            "stop_reason": response.stop_reason,
            "usage": usage,
            **tag,
        }
        with self._lock:
            self._cache[key] = record
            self.api_calls += 1
            self._persist(record)
        return record

    def _throttle(self, elapsed: float) -> None:
        """Duty-cycle, then hold while the card is hot. See the constants above.

        Three consecutive unreadable temperatures end a hold rather than one: `cdg_battery`
        measured a single transient `nvidia-smi` hiccup cancelling a cooldown at 69C that should
        have run to 66, and un-governed beats hanging on a dead sensor.
        """
        time.sleep(self.rest_ratio * elapsed)
        temperature = gpu_temperature()
        if temperature is None or temperature < OLLAMA_PAUSE_ABOVE_C:
            return
        print(f"      gpu at {temperature}C; holding until below {OLLAMA_RESUME_BELOW_C}C",
              file=sys.stderr, flush=True)
        failures = 0
        while True:
            time.sleep(OLLAMA_POLL_SECONDS)
            temperature = gpu_temperature()
            if temperature is None:
                failures += 1
                if failures >= 3:
                    return
                continue
            failures = 0
            if temperature < OLLAMA_RESUME_BELOW_C:
                return

    def _call_ollama(
        self, params: dict[str, Any], *, sample: int, key: str, tag: dict[str, Any]
    ) -> dict[str, Any]:
        """One call to a local model. Free, offline, and better instrumented than either API path.

        **The reason to prefer this is not only cost.** On three of the protocol's requirements
        the local transport is the *strictest* of the three available, not a cheap substitute:

        - **The schema is enforced, not requested.** Ollama's `format` takes the JSON schema
          directly, so a malformed verdict is impossible — the property the SDK transport has and
          the `claude -p` transport cannot have, since it has no structured-output mode and falls
          back to instruction-plus-fence-stripping.
        - **The output cap is real.** `options.num_predict` is honoured. `claude -p` has no
          max-tokens flag at all, which is why that transport's mean output ran to 1,049 tokens
          against a stage-1 cap of 350 — the cap was built and silently dropped.
        - **The response distribution is reproducible.** `options.seed` is set to the sample
          index, so the `n` draws of a cell are distinct *and* a re-run reproduces them exactly.
          No API path offers this: there, `n` byte-identical requests draw from an unseeded
          sampler and the distribution can never be reproduced, only re-drawn.

        Stage 2 is also a genuine assistant turn here rather than the transcript reconstruction
        `_flatten_turns` performs for `claude -p`, so the two-stage conditioning matches the SDK
        path exactly.

        What is given up is capability, and that is the whole question gates 0 and 1 exist to
        answer: a local panel that passes them is a validated instrument with no quota cost, and
        one that fails has priced the capability floor cheaply.
        """
        messages = [{"role": "system", "content": params["system"]}]
        for turn in params["messages"]:
            messages.append({"role": turn["role"], "content": _block_text(turn["content"])})
        schema = (
            params.get("output_config", {}).get("format", {}).get("schema")
            if isinstance(params.get("output_config"), dict) else None
        )
        payload: dict[str, Any] = {
            "model": params["model"],
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": params["max_tokens"],
                "temperature": self.temperature,
                # The sample index *is* the seed, which is what makes the distribution
                # reproducible. A fixed seed would collapse all n draws onto one answer.
                "seed": sample,
            },
        }
        if schema is not None:
            payload["format"] = schema
        if self.no_think:
            # Reasoning models spend the whole `num_predict` budget on hidden thinking and
            # return empty content with `done_reason: length`. Measured on qwen3:4b before this
            # flag existed. Top-level, not an option — inside `options` it is silently ignored.
            payload["think"] = False

        begun = time.time()
        try:
            request = urllib.request.Request(
                OLLAMA_URL, data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
                envelope = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            record = {**tag, "key": key, "model": params["model"], "text": "", "refused": True,
                      "stop_reason": f"transport_error:{type(error).__name__}", "usage": {}}
            with self._lock:
                self._cache[key] = record
                self.api_calls += 1
                self._persist(record)
            return record
        elapsed = time.time() - begun

        text = _strip_fence(str(envelope.get("message", {}).get("content", "")))
        record = {
            **tag,
            "key": key,
            "model": params["model"],
            "text": text,
            "refused": not text,
            "stop_reason": str(envelope.get("done_reason") or "stop"),
            "usage": {
                "input": int(envelope.get("prompt_eval_count", 0) or 0),
                "output": int(envelope.get("eval_count", 0) or 0),
                "cache_read": 0,
                "cache_write": 0,
                "seconds": round(elapsed, 2),
            },
        }
        with self._lock:
            self._cache[key] = record
            self.api_calls += 1
            self._persist(record)
        self._throttle(elapsed)
        return record

    def _call_cli(self, params: dict[str, Any], *, key: str, tag: dict[str, Any]) -> dict[str, Any]:
        """One call through `claude -p`, which runs on the local install's own authentication.

        On a Claude subscription this consumes that subscription and no API key is involved, so
        the envelope's `total_cost_usd` is an *equivalent* API price for quota already paid for
        rather than money being charged — `providers/cli.py` argues that position at length and
        this records the field for the same reason: a subscription is still a bounded resource
        and the equivalent price is the best available proxy for how fast it is going.

        **Structured output is an instruction here, not a guarantee.** The SDK transport
        constrains stage 2 with `output_config.format`, so a malformed verdict is impossible;
        `claude -p` has no such mode, so the schema is appended to the system prompt and the
        answer is fence-stripped and parsed. That is strictly weaker, and the failure is handled
        the same way a refusal is — `_cell` finds no valid verdict and marks the sample unscored
        rather than guessing. The count of those lands in `refused_samples`, which is where a
        transport that cannot hold its format would show up.
        """
        system = params["system"]
        schema = (
            params.get("output_config", {}).get("format", {}).get("schema")
            if isinstance(params.get("output_config"), dict) else None
        )
        if schema is not None:
            system += (
                "\n\nReply with a single JSON object conforming to this schema and nothing "
                "else — no prose, no code fence:\n" + json.dumps(schema, sort_keys=True)
            )
        argv = [
            "claude", "-p", _flatten_turns(params["messages"]),
            "--output-format", "json",
            "--model", params["model"],
            "--system-prompt", system,
            *CLI_HARDENING,
        ]
        try:
            completed = subprocess.run(
                argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=CLI_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL, check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as error:
            record = {**tag, "key": key, "model": params["model"], "text": "", "refused": True,
                      "stop_reason": f"transport_error:{type(error).__name__}", "usage": {}}
            with self._lock:
                self.api_calls += 1
                self.transport_failures += 1
            return record

        text, stop_reason, usage = "", "cli_error", {}
        if completed.returncode == 0:
            try:
                envelope = json.loads(completed.stdout)
            except json.JSONDecodeError:
                envelope = {}
            text = _strip_fence(str(envelope.get("result", "")))
            stop_reason = str(envelope.get("stop_reason") or "end_turn")
            if envelope.get("is_error"):
                stop_reason, text = "cli_is_error", ""
            tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
            for entry in (envelope.get("modelUsage") or {}).values():
                tokens["input"] += int(entry.get("inputTokens", 0) or 0)
                tokens["output"] += int(entry.get("outputTokens", 0) or 0)
                tokens["cache_read"] += int(entry.get("cacheReadInputTokens", 0) or 0)
                tokens["cache_write"] += int(entry.get("cacheCreationInputTokens", 0) or 0)
            usage = {**tokens, "equivalent_usd": float(envelope.get("total_cost_usd") or 0.0)}
        record = {
            **tag,
            "key": key,
            "model": params["model"],
            "text": text,
            "refused": not text,
            "stop_reason": stop_reason,
            "usage": usage,
        }
        with self._lock:
            self.api_calls += 1
            if _is_transport_failure(stop_reason):
                self.transport_failures += 1
            else:
                self._cache[key] = record
                self._persist(record)
        return record

    # ------------------------------------------------------------------- the two stages

    def _cell(self, persona: Persona, passage_id: str, passage: str, sample: int,
              model: str, effort: str | None) -> Sample:
        """One (passage, persona, sample) cell: stage 1, then stage 2 on its answer.

        The cache breakpoint goes on the passage turn — the last block shared by stage 1, stage
        2, and every sample of this cell. Whether it engages depends on the panel model: the
        rendered prefix here is roughly 300 tokens of system plus the passage, so it clears the
        512-token floor of the Opus 5 family and the 1024 of the Sonnet 5 family on a
        normal-length scene, and does **not** clear Haiku 4.5's 4096. On the default panel model
        the marker is therefore inert and the schedule pays full input price for every sample.
        That is the accepted trade for the cheapest tier, and it is written down here so a later
        reader does not mistake the marker for a saving that was measured.
        """
        first = [{
            "role": "user",
            "content": [{
                "type": "text",
                "text": stage1_turn(passage),
                "cache_control": {"type": "ephemeral"},
            }],
        }]
        stage1 = self._call(
            self._params(persona, first, model=model, effort=effort,
                         max_tokens=STAGE1_MAX_TOKENS, schema=None),
            sample=sample,
            tag={"passage": passage_id, "persona": persona.persona_id, "stage": 1,
                 "sample": sample},
        )
        if stage1["refused"]:
            return Sample(passage_id, persona.persona_id, sample, model, "", None, None,
                          True, stage1["key"], stage1["usage"])

        second = [
            *first,
            {"role": "assistant", "content": stage1["text"] or "(no answer)"},
            {"role": "user", "content": stage2_turn()},
        ]
        stage2 = self._call(
            self._params(persona, second, model=model, effort=effort,
                         max_tokens=STAGE2_MAX_TOKENS, schema=STAGE2_SCHEMA),
            sample=sample,
            tag={"passage": passage_id, "persona": persona.persona_id, "stage": 2,
                 "sample": sample},
        )
        verdict = reason = None
        if not stage2["refused"] and stage2["text"]:
            try:
                parsed = json.loads(_strip_fence(stage2["text"]))
                verdict = parsed.get("verdict")
                reason = parsed.get("reason_code")
            except (json.JSONDecodeError, AttributeError):
                verdict = reason = None
        if verdict not in VERDICTS:
            # The schema makes this near-impossible; treating it as a refusal rather than as a
            # missing value keeps un-scored cells out of the rates instead of into the middle.
            verdict = reason = None
        usage = {k: stage1["usage"].get(k, 0) + stage2["usage"].get(k, 0)
                 for k in ("input", "output", "cache_read", "cache_write")}
        return Sample(passage_id, persona.persona_id, sample, model, stage1["text"],
                      verdict, reason, verdict is None, stage2["key"], usage)

    # ------------------------------------------------------------------------- pairwise

    def _compare(
        self, persona: Persona, pair_id: str, original: str, variant: str,
        *, orientation: int, sample: int, model: str, effort: str | None,
    ) -> Comparison:
        """One blinded comparison. `orientation` 0 puts the original in A, 1 puts it in B.

        Both orientations are run for every pair, which is what makes positional bias
        *measurable* rather than assumed away — §69's discipline, whose docstring notes that
        RevisionBench measured 43-65% positional artifacts in model judges and that humans get
        checked rather than trusted. A persona that answers "A" in both orientations has told us
        about position, not about the passages, and `Comparison.chose_variant` is what the caller
        aggregates precisely so that case cannot be mistaken for a preference.
        """
        first, second = (original, variant) if orientation == 0 else (variant, original)
        turns = [{"role": "user",
                  "content": pair_turn(first, second, question=self.pair_question)}]
        record = self._call(
            self._params(persona, turns, model=model, effort=effort,
                         max_tokens=PAIR_MAX_TOKENS, schema=PAIR_SCHEMA),
            sample=sample,
            tag={"passage": pair_id, "persona": persona.persona_id, "stage": "pair",
                 "question": self.pair_question,
                 "orientation": orientation, "sample": sample},
        )
        choice = reason = None
        if not record["refused"] and record["text"]:
            try:
                parsed = json.loads(_strip_fence(record["text"]))
                choice, reason = parsed.get("choice"), parsed.get("reason_code")
            except (json.JSONDecodeError, AttributeError):
                choice = reason = None
        if choice not in PAIR_CHOICES:
            choice = reason = None
        return Comparison(
            pair_id=pair_id, persona_id=persona.persona_id, sample=sample, model=model,
            orientation=orientation, choice=choice, reason_code=reason,
            refused=choice is None, usage=record.get("usage", {}),
        )

    def ask(
        self, persona: Persona, turns: list[dict[str, Any]], *, schema: dict[str, object] | None,
        max_tokens: int, tag: dict[str, Any], sample: int = 0,
    ) -> dict[str, Any]:
        """One cached call whose turns and schema the caller chose. The generic seam.

        Every other public method here fixes a protocol: `panel` asks two stages about one
        passage, `compare_pair` asks one blinded choice between two. A study *of* protocols has
        to vary exactly that — the turns and the answer's shape — while holding the persona, the
        transport, the digest keying and the replay cache identical underneath, so that what
        differs between two arms is the asking and nothing below it.

        Deliberately thin, and it returns the raw cache record rather than a typed result: what
        counts as an answer is the calling protocol's definition, and a shared parser here would
        quietly impose one protocol's shape on the rest. `model` and `effort` are not parameters
        because a protocol comparison that varied the tier between arms would not be one.
        """
        return self._call(
            self._params(persona, turns, model=self.model, effort=self.effort,
                         max_tokens=max_tokens, schema=schema),
            sample=sample, tag=tag,
        )

    def compare_pair(
        self, pair_id: str, original: str, variant: str, *, n: int = 1,
        personas: tuple[Persona, ...] = PANEL,
    ) -> list[Comparison]:
        """Every persona x sample x **both orientations** for one pair.

        `n` defaults to 1 because the two orientations already give each persona two independent
        draws on the same pair; `n` multiplies that rather than replacing it.
        """
        jobs: list[Callable[[], Comparison]] = []
        for persona in personas:
            for sample in range(n):
                for orientation in (0, 1):
                    jobs.append(
                        lambda p=persona, s=sample, o=orientation: self._compare(
                            p, pair_id, original, variant, orientation=o, sample=s,
                            model=self.model, effort=self.effort,
                        )
                    )
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            return list(pool.map(lambda job: job(), jobs))

    def variant_win_rate(
        self, pair_id: str, original: str, variant: str, *, n: int = 1,
        tie_policy: str = "half_win",
    ) -> float:
        """P(the panel prefers the variant over its own original). The gate-1 scalar.

        0.5 is indifference, so **damage is declared to lower it** and `persona_battery` passes
        `direction=-1`. The original compared against itself is 0.5 by construction and never
        elicited, which is why `evaluate`'s per-chapter baseline costs nothing here.

        `tie_policy` is declared, not discovered: `half_win` scores `neither` as half a win —
        §69's option of the same name — and `drop` removes it from the denominator. Refused or
        unparseable comparisons are always dropped and counted separately; they are a transport
        failure, not a reader's indifference, and conflating the two would put format errors into
        a preference distribution.
        """
        comparisons = [
            c for c in self.compare_pair(pair_id, original, variant, n=n)
            if c.model == self.model and not c.refused
        ]
        scores = []
        for comparison in comparisons:
            if comparison.choice == "neither":
                if tie_policy == "drop":
                    continue
                scores.append(0.5)
            else:
                scores.append(1.0 if comparison.chose_variant else 0.0)
        if not scores:
            return 0.5
        return sum(scores) / len(scores)

    def _is_spot(self, passage_id: str, persona_id: str) -> bool:
        """Deterministic spot-check membership, so the subset is a function of the schedule.

        Picked by hashing rather than sampling: a random 10% redraws every run, which means the
        spot evidence for a given cell exists in one run and not the next and cannot be
        accumulated across them.
        """
        if not self.spot_model or self.spot_fraction <= 0:
            return False
        marker = int(digest([passage_id, persona_id])[:8], 16) / 0xFFFFFFFF
        return marker < self.spot_fraction

    def panel(self, passage_id: str, passage: str, *, n: int = 5,
              personas: tuple[Persona, ...] = PANEL) -> list[Sample]:
        """Every persona x sample for one passage, concurrently. The unit of the datum."""
        jobs: list[Callable[[], Sample]] = []
        for persona in personas:
            for sample in range(n):
                jobs.append(
                    lambda p=persona, s=sample: self._cell(
                        p, passage_id, passage, s, self.model, self.effort
                    )
                )
            if self._is_spot(passage_id, persona.persona_id) and self.spot_model:
                jobs.append(
                    lambda p=persona: self._cell(
                        p, passage_id, passage, 0, self.spot_model, self.spot_effort
                    )
                )
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            return list(pool.map(lambda job: job(), jobs))

    def stop_rate(self, passage_id: str, passage: str, *, n: int = 5) -> float:
        """`evaluate.py`-shaped scalar: the panel's would-stop rate on this passage.

        This is the reduction from a distribution to the one number the ablation harness can
        score, and it is a lossy one by design — the distribution is what the record keeps and
        what gate 0 and the variance decomposition read. Damage is declared to *raise* it, which
        is why `persona_battery` passes `direction=+1`.

        Refused samples are excluded from the denominator rather than counted as not-stopping.
        A passage whose every sample refused has no rate; 0.5 is returned and the battery's
        refusal count is what makes that visible.
        """
        samples = [s for s in self.panel(passage_id, passage, n=n)
                   if s.model == self.model and not s.refused]
        if not samples:
            return 0.5
        return sum(1 for s in samples if s.would_stop) / len(samples)

    # ------------------------------------------------------------------ persona fidelity

    def fidelity(self, persona: Persona) -> dict[str, object]:
        """Ask a persona for its held-out anchors and score the answer.

        Run before any passage. A persona that cannot reproduce its own held-out verdicts is
        refit or dropped — fidelity is validated before the persona validates anything.
        """
        probe = fidelity_probe(persona)
        if probe is None:
            return {"persona": persona.persona_id, "held_out": 0, "matched": 0,
                    "verdict_agreement": 0.0, "reason_agreement": 0.0, "detail": []}
        turn, schema = probe
        record = self._call(
            self._params(persona, [{"role": "user", "content": turn}], model=self.model,
                         effort=self.effort, max_tokens=PROBE_MAX_TOKENS, schema=schema),
            sample=0,
            tag={"passage": "__anchors__", "persona": persona.persona_id, "stage": 0,
                 "sample": 0},
        )
        if record["refused"] or not record["text"]:
            return {"persona": persona.persona_id, "held_out": len(persona.held_out_anchors),
                    "matched": 0, "verdict_agreement": 0.0, "reason_agreement": 0.0,
                    "refused": True, "detail": []}
        try:
            answers = json.loads(_strip_fence(record["text"])).get("verdicts", [])
        except (json.JSONDecodeError, AttributeError):
            answers = []
        return anchor_agreement(persona, answers)

    def spend(self) -> dict[str, int]:
        """Token totals over every record in the cache, replayed and fresh alike."""
        totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
                  "equivalent_usd": 0.0}
        for record in self._cache.values():
            usage = record.get("usage", {})
            for key in totals:
                value = usage.get(key, 0) or 0
                totals[key] = totals[key] + (
                    float(value) if key == "equivalent_usd" else int(value)
                )
        totals["equivalent_usd"] = round(totals["equivalent_usd"], 4)
        return totals


def samples_to_rows(samples: list[Sample]) -> list[dict[str, Any]]:
    """Flatten for the raw log. `asdict` on a slots dataclass, plus the derived flag."""
    return [{**asdict(sample), "would_stop": sample.would_stop} for sample in samples]


#: Openings that say the model is narrating its task instead of reading. Measured on qwen3:4b,
#: whose first 350 tokens were "Hmm, the user wants me to act as a reader who's experienced..."
_NARRATION_MARKERS = (
    "the user wants", "the user is asking", "i need to respond", "i should respond",
    "as a reader, i should", "my task", "the system prompt", "the instruction",
    "okay, ", "hmm, ", "first, i need", "let me ",
)
#: Openings that say the model is reviewing rather than reading. Measured on phi4, which is
#: larger than both 4B models and further from the register this instrument needs.
_CRITIC_MARKERS = (
    "this passage", "this scene", "this chapter", "this excerpt", "the passage",
    "the author", "the writer", "the prose ", "the narrative", "the text ",
    "conveys", "the reader is", "readers will", "it is clear that",
)


def adherence_flags(text: str) -> list[str]:
    """Register problems visible in an opening. **A screen, not a classifier.**

    A lexical detector for register is exactly the shape of thing this directory keeps killing —
    `tricolon_rate` detected the year, and the stake lexicon's first draft selected discourse
    adverbs. So this does not decide anything: it flags a candidate and the caller prints the
    actual text, because the only reliable check is reading what the model wrote. It exists to
    make a cheap failure cheap to *find*, not to automate the judgement.

    Two failure registers, both measured rather than imagined. **Task-narration** is the model
    describing the instruction it was given instead of following it. **Critic register** is the
    expert frame the entire program exists to avoid — a model writing "this passage conveys" has
    answered §1a.2's refuted question, not the reader question.
    """
    opening = " ".join(text.strip().split())[:400].lower()
    flags = []
    if any(marker in opening for marker in _NARRATION_MARKERS):
        flags.append("task-narration")
    if any(marker in opening for marker in _CRITIC_MARKERS):
        flags.append("critic-register")
    if not opening:
        flags.append("empty")
    return flags


def probe_discrimination(
    original: str, variant: str, *, transport: str, model: str,
    personas: tuple[Persona, ...] = PANEL, cache: Path | None = None,
) -> dict[str, Any]:
    """Can this model *decide* between two texts at all? The precondition `probe_adherence` misses.

    **Register and discrimination are different capabilities, and checking only the first cost a
    105-minute run.** `gemma3:4b` passes the adherence probe beautifully — it answers in
    first-person reader register, four personas visibly differentiating. Put the same model behind
    a closed-enum schema and it collapses: 97.7% `neither` across 904 comparisons, uniform over all
    four personas (1.3%-3.5% decided), with one reason code taking 78% of the answers. A near
    constant, which is the same failure the absolute verdict died of, at a different constant.

    So this probes the other half: hand the panel the **strongest** manipulation available and
    check it decides. `transplant` at full dose grafts a length-matched run from another story —
    if a reader cannot separate a scene from a foreign graft, it will not separate a de-stake, and
    every subtler arm in the schedule is below its resolution. That makes the strongest arm a
    resolution *floor* rather than another measurement, and eight calls establish it.

    Returns the decided rate and the choice distribution. There is no threshold here: a floor is
    read, not passed, and what counts as usable depends on how much of the schedule sits below it.
    """
    rows: list[dict[str, Any]] = []
    with Elicitor(
        cache or (HERE / "results" / "persona-discrimination.jsonl"),
        transport=transport, model=model, spot_model=None,
    ) as elicitor:
        for persona in personas:
            for orientation in (0, 1):
                comparison = elicitor._compare(
                    persona, "__discrimination__", original, variant,
                    orientation=orientation, sample=0, model=model, effort=None,
                )
                rows.append({
                    "persona": persona.persona_id,
                    "orientation": orientation,
                    "choice": comparison.choice,
                    "reason_code": comparison.reason_code,
                })
    decided = [r for r in rows if r["choice"] in ("A", "B")]
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row["choice"])
        counts[key] = counts.get(key, 0) + 1
    return {
        "model": model,
        "comparisons": len(rows),
        "decided": len(decided),
        "decided_rate": round(len(decided) / len(rows), 4) if rows else 0.0,
        "choices": counts,
        "rows": rows,
        "reading": (
            "the strongest manipulation is a resolution floor: a panel that ties on a foreign "
            "graft cannot separate anything subtler, and every arm below it is unmeasurable"
        ),
    }


def probe_adherence(
    passage: str, *, transport: str, model: str, personas: tuple[Persona, ...] = PANEL,
    cache: Path | None = None,
) -> list[dict[str, Any]]:
    """Can this model hold a reader persona at all? The cheapest precondition there is.

    **Run this before spending a panel budget on any model.** Persona adherence turned out not
    to track model size: on one generated scene, `gemma3:4b` (3.3GB) answered in first-person
    reader register — "The numbers are a weight... the 3,999 is wrong, in a way that makes my
    breath catch" — while `qwen3:4b` spent its whole budget narrating the task and `phi4`, larger
    than both, returned "This passage conveys a gritty, almost oppressive atmosphere", which is
    the critic frame §1a.2 already refuted. Parameters do not predict it; whether the model can
    inhabit a voice rather than analyse one does.

    That makes this a *precondition* rather than a gate: a model failing here would corrupt the
    two-stage design silently, because stage 1 would be task-narration and stage 2 would be a
    category committed on the back of it. Four calls answer it; gate 0 costs hundreds.
    """
    rows: list[dict[str, Any]] = []
    with Elicitor(
        cache or (HERE / "results" / "persona-adherence.jsonl"),
        transport=transport, model=model, spot_model=None,
    ) as elicitor:
        for persona in personas:
            turn = [{"role": "user", "content": stage1_turn(passage)}]
            record = elicitor._call(
                elicitor._params(persona, turn, model=model, effort=None,
                                 max_tokens=STAGE1_MAX_TOKENS, schema=None),
                sample=0,
                tag={"passage": "__adherence__", "persona": persona.persona_id,
                     "stage": 1, "sample": 0},
            )
            text = str(record.get("text", ""))
            rows.append({
                "persona": persona.persona_id,
                "model": model,
                "flags": adherence_flags(text),
                "opening": " ".join(text.strip().split())[:200],
            })
    return rows


if __name__ == "__main__":
    # Persona-adherence probe: the precondition check `probe_adherence` documents. Four calls
    # against one real passage, printing what each persona actually wrote — the flags are a
    # screen and the text is the evidence.
    #
    #   python elicit.py ollama gemma3:4b
    #   python elicit.py cli claude-haiku-4-5
    import argparse

    parser = argparse.ArgumentParser(description="probe whether a model can hold a reader persona")
    parser.add_argument("transport", choices=("cli", "sdk", "ollama"))
    parser.add_argument("model")
    parser.add_argument("--book-db", help="a book database; defaults to the golden fixtures")
    options = parser.parse_args()

    if options.book_db:
        from corpus_io import generated_scenes

        passage = generated_scenes(options.book_db, min_words=500)[0].text
    else:
        from corpus_io import fixture_scenes

        passage = fixture_scenes()[2].text

    words = len(passage.split())
    print(f"probing {options.model} via {options.transport} on a {words}-word passage\n")
    failures = 0
    for row in probe_adherence(passage, transport=options.transport, model=options.model):
        mark = "FLAG" if row["flags"] else "ok  "
        failures += bool(row["flags"])
        print(f"{mark} {row['persona']:<10} {','.join(row['flags']) or 'reader register'}")
        print(f"     {row['opening'][:150]}")
    print(f"\n{failures}/{len(PANEL)} persona(s) flagged. Read the openings — the flags are "
          "a screen, not a verdict.")
