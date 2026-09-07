"""Move one reviewed hidden-claim bullet into current-scene reveal permission."""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = runpy.run_path(str(HERE / "prose_production_obligations.py"))
CODEX = PRIOR["CODEX"]
_test_guard, _transport_files, _usage_tokens = (
    PRIOR[key] for key in ("_test_guard", "_transport_files", "_usage_tokens")
)
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REG = HERE / "prose-disclosure-permission"
ORDER = ("control-1", "permission-1", "permission-2", "control-2")
PERMISSION_HEADING = "May be revealed in this scene; not established as prior reader knowledge:\n"
TOKEN_STOP = 100_000
EFFORT = "high"
TRANSPORT_TIMEOUT = 900
RETRY_PATTERN = re.compile(r"retrying\s+sampling\s+request", re.IGNORECASE)


def _span(source: dict[str, Any], name: str) -> tuple[int, int, str]:
    span, prompt = source[name], source["control"]["prompt"]
    if not isinstance(span, dict) or set(span) != {"start", "end", "text"}:
        raise ValueError(f"invalid {name} shape")
    start, end, text = (span[key] for key in ("start", "end", "text"))
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(prompt):
        raise ValueError(f"invalid {name} offsets")
    if not isinstance(text, str) or not text or prompt[start:end] != text:
        raise ValueError(f"{name} does not match its exact prompt span")
    if start and prompt[start - 1] != "\n":
        raise ValueError(f"{name} must start at a line boundary")
    return start, end, text


def compose(source: Any) -> dict[str, dict[str, Any]]:
    """Relocate exactly one bullet; this does not establish actual reader disclosure."""
    if not isinstance(source, dict) or set(source) != {
        "control",
        "hidden_block",
        "release",
        "original_request_path",
        "original_request_sha256",
    }:
        raise ValueError("invalid source schema")
    control = source["control"]
    if not isinstance(control, dict) or set(control) != {"system", "prompt", "timeout"}:
        raise ValueError("invalid original request shape")
    if any(
        not isinstance(control[key], str) or not control[key].strip()
        for key in ("system", "prompt")
    ):
        raise ValueError("nonempty system and prompt required")
    timeout = control["timeout"]
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("invalid original timeout")
    if not isinstance(source["original_request_path"], str) or not source["original_request_path"]:
        raise ValueError("original request path required")
    digest = source["original_request_sha256"]
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("invalid original request hash")
    start, end, hidden = _span(source, "hidden_block")
    release_start, release_end, release = _span(source, "release")
    if not start < release_start < release_end < end:
        raise ValueError("release must be strictly inside the hidden block")
    if (
        not release.startswith("- ")
        or not release.endswith("\n")
        or len(release.splitlines(keepends=True)) != 1
        or "\r" in release
        or not release[2:-1].strip()
    ):
        raise ValueError("release must be exactly one nonblank LF-terminated bullet")
    prompt = control["prompt"]
    witness = release[2:].rstrip("\n")
    outside = prompt[:start] + prompt[end:]
    if prompt.count(witness) != 2 or hidden.count(witness) != 1 or outside.count(witness) != 1:
        raise ValueError("claim must occur twice, once inside and once outside the hidden block")
    remaining = hidden[: release_start - start] + hidden[release_end - start :]
    if not remaining.strip():
        raise ValueError("remaining hidden block must be nonempty")
    permission = PERMISSION_HEADING + release + "\n"
    treatment = prompt[:start] + permission + remaining + prompt[end:]
    if treatment.count(witness) != 2:
        raise ValueError("claim copies must be preserved in the treatment")
    return {"control": dict(control), "permission": {**control, "prompt": treatment}}


def _text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def transformation_receipt(source: Any) -> dict[str, Any]:
    """Character spans and hashes permit an exact inverse without a semantic matcher."""
    requests = compose(source)
    hidden, release = source["hidden_block"], source["release"]
    start, end = hidden["start"], hidden["end"]
    permission_length = len(PERMISSION_HEADING) + len(release["text"]) + 1
    remaining_start = start + permission_length
    remaining_end = remaining_start + len(hidden["text"]) - len(release["text"])
    control, treatment = requests["control"]["prompt"], requests["permission"]["prompt"]
    return {
        "schema": "litharness.prose-disclosure-permission-transform.v1",
        "offset_unit": "unicode_code_points_half_open",
        "control_prompt_sha256": _text_sha(control),
        "permission_prompt_sha256": _text_sha(treatment),
        "control_prompt_characters": len(control),
        "permission_prompt_characters": len(treatment),
        "hidden_before": {"start": start, "end": end},
        "release_before": {"start": release["start"], "end": release["end"]},
        "permission_after": {"start": start, "end": remaining_start},
        "hidden_after": {"start": remaining_start, "end": remaining_end},
        "release_insert_offset_in_remaining_hidden": release["start"] - start,
        "prefix_sha256": _text_sha(control[:start]),
        "suffix_sha256": _text_sha(control[end:]),
        "remaining_hidden_sha256": _text_sha(treatment[remaining_start:remaining_end]),
        "claim_witness_occurrences": {"control": 2, "permission": 2},
    }


def _original(source: dict[str, Any]) -> Path:
    path = Path(source["original_request_path"])
    return (path if path.is_absolute() else ROOT / path).resolve()


def _verify_original(source: dict[str, Any]) -> Path:
    path = _original(source)
    if sha(path) != source["original_request_sha256"] or read(path) != source["control"]:
        raise ValueError("original request identity changed")
    return path


def _registered_files() -> list[Path]:
    return [
        Path(__file__).resolve(),
        HERE / "prose_codex.py",
        HERE / "prose_production_obligations.py",
        ROOT / "tests/test_prose_disclosure_permission.py",
        REG / "PREREG.md",
        REG / "RUNBOOK.md",
    ]


def _registration_commit() -> str:
    paths = [str(path.relative_to(ROOT)) for path in _registered_files()]
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", *paths],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    clean = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *paths],
        cwd=ROOT,
        check=False,
    )
    if tracked.returncode or clean.returncode:
        raise RuntimeError("runner, helper, tests and registration must be committed and clean")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _files(out: Path, source_path: Path, source: Any, prefix: list[str]) -> list[Path]:
    return [
        *_registered_files(),
        source_path,
        source_path.with_name("prepare_source.py"),
        source_path.with_name("input-audit.md"),
        _original(source),
        *_transport_files(prefix),
        *(out / name / "system.txt" for name in ORDER),
    ]


def _record(out: Path, name: str, request: Any, prefix: list[str]) -> dict[str, Any]:
    folder = out / name
    return {
        "system": request["system"],
        "prompt": request["prompt"],
        "argv": CODEX["argv"](prefix, folder / "system.txt", folder / "work", effort=EFFORT),
        "requested_model": CODEX["MODEL"],
        "reasoning_effort": EFFORT,
        "authentication": "chatgpt",
        "removed_environment_keys": list(CODEX["REMOVED_ENV"]),
    }


def prepare(out: Path, source_path: Path) -> None:
    _test_guard()
    out, source_path = out.resolve(), source_path.resolve()
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath ignored runs")
    if out.exists():
        raise FileExistsError("output directory must be new")
    source = read(source_path)
    requests = compose(source)
    _verify_original(source)
    commit = _registration_commit()
    prefix = CODEX["command_prefix"]()
    paths = _files(out, source_path, source, prefix)
    systems = {out / name / "system.txt" for name in ORDER}
    if any(not path.is_file() for path in paths if path not in systems):
        raise ValueError("missing frozen source, review, code or registration")
    auth = subprocess.run(
        [*prefix, "login", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=CODEX["subscription_env"](),
        check=False,
    )
    if auth.returncode or (auth.stdout + auth.stderr).strip() != "Logged in using ChatGPT":
        raise RuntimeError("ChatGPT subscription required; no API or login fallback")
    version = subprocess.check_output(
        [*prefix, "--version"],
        text=True,
        env=CODEX["subscription_env"](),
    ).strip()
    out.mkdir(parents=True, exist_ok=False)
    for name in ORDER:
        folder = out / name
        (folder / "work").mkdir(parents=True)
        (folder / "system.txt").write_text(
            requests[name.rsplit("-", 1)[0]]["system"],
            encoding="utf-8",
            newline="\n",
        )
    write_new(
        out / "manifest.json",
        {
            "source": source,
            "source_path": str(source_path),
            "requests": requests,
            "transformation": transformation_receipt(source),
            "slot_requests": {
                name: _record(out, name, requests[name.rsplit("-", 1)[0]], prefix) for name in ORDER
            },
            "prefix": prefix,
            "order": list(ORDER),
            "token_stop": TOKEN_STOP,
            "token_counter": "input_tokens + output_tokens",
            "transport_timeout_seconds": TRANSPORT_TIMEOUT,
            "source_timeout": source["control"]["timeout"],
            "files": {str(path): sha(path) for path in paths},
            "authentication": "chatgpt",
            "reasoning_effort": EFFORT,
            "transport_slot_per_logical_call": "full-1",
            "code_commit": commit,
            "cli_version": version,
        },
    )


def validate(out: Path) -> dict[str, Any]:
    manifest = CODEX["validate"](out)
    source_path = Path(manifest["source_path"])
    if not out.resolve().is_relative_to(ROOT / "runs") or out.resolve() == ROOT / "runs":
        raise ValueError("output must be beneath ignored runs")
    source, prefix = manifest["source"], manifest["prefix"]
    requests = compose(source)
    _verify_original(source)
    if set(manifest["files"]) != {str(path) for path in _files(out, source_path, source, prefix)}:
        raise ValueError("frozen file inventory changed")
    settings = {
        "order": list(ORDER),
        "token_stop": TOKEN_STOP,
        "token_counter": "input_tokens + output_tokens",
        "authentication": "chatgpt",
        "reasoning_effort": EFFORT,
        "transport_slot_per_logical_call": "full-1",
        "transport_timeout_seconds": TRANSPORT_TIMEOUT,
        "source_timeout": source["control"]["timeout"],
    }
    if any(manifest.get(key) != value for key, value in settings.items()):
        raise ValueError("registered dispatch settings changed")
    if manifest.get("transformation") != transformation_receipt(source):
        raise ValueError("frozen transformation receipt changed")
    if source != read(source_path) or manifest["requests"] != requests:
        raise ValueError("frozen source or request identity changed")
    expected = {
        name: _record(out, name, requests[name.rsplit("-", 1)[0]], prefix) for name in ORDER
    }
    if manifest["slot_requests"] != expected:
        raise ValueError("frozen slot request identity changed")
    for name in ORDER:
        system = (out / name / "system.txt").read_bytes().decode("utf-8")
        if system != requests[name.rsplit("-", 1)[0]]["system"]:
            raise ValueError("system file differs from frozen request")
        path = out / name / "full-1.request.json"
        if path.exists() and read(path) != expected[name]:
            raise ValueError("recorded request identity changed")
    return manifest


def _audit(folder: Path) -> dict[str, Any]:
    raw = read(folder / "full-1.raw.json")
    stderr = raw.get("stderr")
    if not isinstance(stderr, str):
        raise ValueError("missing raw stderr")
    return {
        "schema": "litharness.prose-transport-audit.v1",
        "request_sha256": sha(folder / "full-1.request.json"),
        "raw_sha256": sha(folder / "full-1.raw.json"),
        "result_sha256": sha(folder / "full-1.result.json"),
        "text_sha256": sha(folder / "full-1.txt"),
        "internal_sampling_retry_reported": bool(RETRY_PATTERN.search(stderr)),
    }


def quota(out: Path) -> int:
    requests, results = list(out.glob("*/*.request.json")), list(out.glob("*/*.result.json"))
    if any(
        path.parent.name not in ORDER or path.name != "full-1.request.json" for path in requests
    ):
        raise ValueError("unregistered invocation")
    if any(path.parent.name not in ORDER or path.name != "full-1.result.json" for path in results):
        raise ValueError("unregistered result")
    names, completed = (
        {path.parent.name for path in requests},
        {path.parent.name for path in results},
    )
    if names != set(ORDER[: len(names)]):
        raise ValueError("invocation slot order changed")
    if completed - names:
        raise ValueError("result has no recorded request")
    for pattern, filename in (
        ("*/*.raw.json", "full-1.raw.json"),
        ("*/transport-audit.json", "transport-audit.json"),
        ("*/full-1.txt", "full-1.txt"),
    ):
        for path in out.glob(pattern):
            if path.parent.name not in names or path.name != filename:
                raise ValueError("orphan or unregistered transport artifact")
    if names - completed:
        raise RuntimeError("request has no result; no retry")
    total = 0
    for path in results:
        result = read(path)
        if result.get("status") != "completed":
            raise RuntimeError("previous failure; no retry")
        total += _usage_tokens(result.get("usage"))
        audit_path = path.parent / "transport-audit.json"
        if not audit_path.is_file():
            raise RuntimeError("completed call has no transport audit; no retry")
        audit = _audit(path.parent)
        if read(audit_path) != audit:
            raise ValueError("recorded transport artifacts changed")
        if audit["internal_sampling_retry_reported"]:
            raise RuntimeError("internal sampling retry retained; stop without redraw")
    if total >= TOKEN_STOP:
        raise RuntimeError("reported token stop reached")
    return total


def call(out: Path, name: str, request: Any, manifest: Any) -> dict[str, Any]:
    _test_guard()
    if name not in ORDER:
        raise ValueError("unregistered invocation")
    frozen = validate(out)
    if manifest != frozen or request != frozen["requests"][name.rsplit("-", 1)[0]]:
        raise ValueError("dispatch request identity changed")
    quota(out)
    if any(
        not (out / prior / "full-1.result.json").is_file() for prior in ORDER[: ORDER.index(name)]
    ):
        raise ValueError("prior invocation missing")
    folder = out / name
    result_path = folder / "full-1.result.json"
    if result_path.is_file():
        return read(result_path)
    if any((folder / "work").iterdir()):
        raise ValueError("isolated work directory is not empty")
    print(f"LOGICAL CALL {name}", flush=True)
    result = CODEX["complete_once"](
        folder,
        "full-1",
        {"prefix": frozen["prefix"], "requests": {"full": request}},
        effort=EFFORT,
    )
    audit = _audit(folder)
    write_new(folder / "transport-audit.json", audit)
    _usage_tokens(result.get("usage"))
    if audit["internal_sampling_retry_reported"]:
        raise RuntimeError("internal sampling retry retained; stop without redraw")
    return result


def draft(out: Path, slot: str | None = None) -> None:
    _test_guard()
    out = out.resolve()
    if slot is not None and slot not in ORDER:
        raise ValueError("unregistered invocation")
    for name in ORDER if slot is None else (slot,):
        manifest = read(out / "manifest.json")
        call(out, name, manifest["requests"][name.rsplit("-", 1)[0]], manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "draft"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--slot", choices=ORDER)
    args = parser.parse_args()
    if args.phase == "prepare":
        if args.source is None or args.slot is not None:
            parser.error("prepare requires --source and takes no --slot")
        prepare(args.out, args.source)
    else:
        if args.source is not None:
            parser.error("draft uses the frozen source; --source is not accepted")
        draft(args.out, args.slot)


if __name__ == "__main__":
    main()
