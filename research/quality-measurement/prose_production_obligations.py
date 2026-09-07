"""Delete reviewed duplicate prompt spans in four isolated subscription scene calls."""

from __future__ import annotations

import argparse
import math
import os
import platform
import re
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CODEX = runpy.run_path(str(HERE / "prose_codex.py"))
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REG = HERE / "prose-production-obligations"
ORDER = ("control-1", "single-1", "single-2", "control-2")
TOKEN_STOP = 100_000
EFFORT = "high"
TRANSPORT_TIMEOUT = 900
RETRY_PATTERN = re.compile(r"retrying\s+sampling\s+request", re.IGNORECASE)


def compose(source: Any) -> dict[str, dict[str, Any]]:
    """Only exact reviewed prompt deletions; surviving witnesses are not semantic proof."""
    if not isinstance(source, dict) or set(source) != {
        "control",
        "cuts",
        "original_request_path",
        "original_request_sha256",
    }:
        raise ValueError("invalid source schema")
    control = source["control"]
    if not isinstance(control, dict) or set(control) != {"system", "prompt", "timeout"}:
        raise ValueError("invalid original request shape")
    if any(not isinstance(control[k], str) or not control[k].strip() for k in ("system", "prompt")):
        raise ValueError("nonempty system and prompt required")
    timeout = control["timeout"]
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("invalid original timeout")
    if not isinstance(source["original_request_path"], str) or not source["original_request_path"]:
        raise ValueError("original request path required")
    digest = source["original_request_sha256"]
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("invalid original request hash")
    cuts, prompt = source["cuts"], control["prompt"]
    if not isinstance(cuts, list) or not cuts:
        raise ValueError("nonempty reviewed cuts required")
    for cut in cuts:
        if not isinstance(cut, dict) or set(cut) != {"start", "end", "text", "witness"}:
            raise ValueError("invalid cut shape")
        start, end, text, witness = (cut[k] for k in ("start", "end", "text", "witness"))
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(prompt):
            raise ValueError("invalid cut offsets")
        if not isinstance(text, str) or not text or prompt[start:end] != text:
            raise ValueError("cut does not match its exact prompt span")
        if not isinstance(witness, str) or not witness.strip() or witness not in text:
            raise ValueError("nonempty witness must occur inside its cut")
        if prompt.count(witness) < 2:
            raise ValueError("witness is not duplicated in the control prompt")
    ordered = sorted(cuts, key=lambda cut: cut["start"])
    previous, pieces = 0, []
    for cut in ordered:
        if cut["start"] < previous:
            raise ValueError("cuts overlap")
        pieces.append(prompt[previous : cut["start"]])
        previous = cut["end"]
    pieces.append(prompt[previous:])
    single = "".join(pieces)
    if not single.strip() or single == prompt:
        raise ValueError("cuts must leave a nonempty changed prompt")
    if any(cut["witness"] not in single for cut in cuts):
        raise ValueError("cut witness does not survive in the treatment")
    return {"control": dict(control), "single": {**control, "prompt": single}}


def _test_guard() -> None:
    if os.environ.get("LITHARNESS_ENV", "").strip().lower() == "test":
        raise RuntimeError("live trial is disabled in tests")


def _original(source: dict[str, Any]) -> Path:
    path = Path(source["original_request_path"])
    return (path if path.is_absolute() else ROOT / path).resolve()


def _verify_original(source: dict[str, Any]) -> Path:
    path = _original(source)
    if sha(path) != source["original_request_sha256"] or read(path) != source["control"]:
        raise ValueError("original request identity changed")
    return path


def _transport_files(prefix: list[str]) -> list[Path]:
    """The npm launcher delegates to a native executable; freeze both, plus Node."""
    entry = Path(prefix[1]).resolve()
    machine = platform.machine().lower()
    architecture = "arm64" if machine in {"arm64", "aarch64"} else "x64"
    targets = {
        ("win32", "x64"): "x86_64-pc-windows-msvc",
        ("win32", "arm64"): "aarch64-pc-windows-msvc",
        ("linux", "x64"): "x86_64-unknown-linux-musl",
        ("linux", "arm64"): "aarch64-unknown-linux-musl",
        ("darwin", "x64"): "x86_64-apple-darwin",
        ("darwin", "arm64"): "aarch64-apple-darwin",
    }
    target = targets.get((sys.platform, architecture))
    if target is None:
        raise RuntimeError("unsupported native CLI platform")
    package = f"codex-{sys.platform}-{architecture}"
    package_roots = (
        entry.parents[1] / "node_modules" / "@openai" / package,
        entry.parents[2] / package,
    )
    executable = "codex.exe" if sys.platform == "win32" else "codex"
    common = [Path(prefix[0]).resolve(), entry, entry.parents[1] / "package.json"]
    for package_root in package_roots:
        metadata = package_root / "package.json"
        if metadata.is_file():
            native = package_root / "vendor" / target / "bin" / executable
            if not native.is_file():
                raise RuntimeError("resolved native CLI executable missing")
            return [*common, metadata.resolve(), native.resolve()]
    native = entry.parents[1] / "vendor" / target / "bin" / executable
    if not native.is_file():
        raise RuntimeError("native CLI executable unavailable; no transport fallback")
    return [*common, native.resolve()]


def _registered_files() -> list[Path]:
    return [
        Path(__file__).resolve(),
        HERE / "prose_codex.py",
        ROOT / "tests/test_prose_production_obligations.py",
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
        "internal_sampling_retry_reported": bool(RETRY_PATTERN.search(stderr)),
    }


def _usage_tokens(usage: Any) -> int:
    if not isinstance(usage, dict):
        raise ValueError("invalid reported usage")
    for key in ("input_tokens", "output_tokens"):
        if type(usage.get(key)) is not int or usage[key] < 0:
            raise ValueError("invalid reported usage")
    for key, maximum in (
        ("cached_input_tokens", usage["input_tokens"]),
        ("reasoning_output_tokens", usage["output_tokens"]),
    ):
        value = usage.get(key)
        if value is not None and (type(value) is not int or not 0 <= value <= maximum):
            raise ValueError("invalid reported usage component")
    return usage["input_tokens"] + usage["output_tokens"]


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
