"""Frozen scene-request comparisons using one subscription CLI invocation per slot.

Configure FrozenSceneExperiment with a fixed order, a pure request composer, a pure
transformation receipt and the experiment's code/tests/registration files. The composer
returns condition names mapped to {system, prompt, timeout}. Source JSON must also retain
control, original_request_path and original_request_sha256. There is no model selection,
retry, repair, scoring or production-state access in this helper.
"""

from __future__ import annotations

import hashlib
import re
import runpy
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PRIOR = runpy.run_path(str(HERE / "prose_production_obligations.py"))
CODEX = PRIOR["CODEX"]
read, write_new, sha = (CODEX[key] for key in ("read", "write_new", "sha"))
test_guard, transport_files, usage_tokens = (
    PRIOR[key] for key in ("_test_guard", "_transport_files", "_usage_tokens")
)
EFFORT = "high"
TRANSPORT_TIMEOUT = 900
RETRY_PATTERN = re.compile(r"retrying\s+sampling\s+request", re.IGNORECASE)


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def audit(folder: Path) -> dict[str, Any]:
    stderr = read(folder / "full-1.raw.json").get("stderr")
    if not isinstance(stderr, str):
        raise ValueError("missing raw stderr")
    return {
        "schema": "litharness.prose-transport-audit.v1",
        **{
            f"{name}_sha256": sha(folder / filename)
            for name, filename in (
                ("request", "full-1.request.json"),
                ("raw", "full-1.raw.json"),
                ("result", "full-1.result.json"),
                ("text", "full-1.txt"),
            )
        },
        "internal_sampling_retry_reported": bool(RETRY_PATTERN.search(stderr)),
    }


class FrozenSceneExperiment:
    """Explicit configuration around the shared frozen dispatch and stop protocol."""

    def __init__(
        self,
        *,
        root: Path,
        order: tuple[str, ...],
        registered_files: tuple[Path, ...],
        compose: Callable[[Any], dict[str, dict[str, Any]]],
        receipt: Callable[[Any], dict[str, Any]],
        token_stop: int,
    ) -> None:
        if (
            len(order) != 4
            or len(set(order)) != 4
            or any(re.fullmatch(r"[a-z][a-z0-9_]*-[12]", name) is None for name in order)
        ):
            raise ValueError("exactly four distinct safe invocation slots required")
        if type(token_stop) is not int or token_stop <= 0:
            raise ValueError("positive reported token stop required")
        self.root, self.order = root.resolve(), order
        self.compose, self.receipt, self.token_stop = compose, receipt, token_stop
        self.registered_files = (
            Path(__file__).resolve(),
            HERE / "prose_production_obligations.py",
            HERE / "prose_codex.py",
            *registered_files,
        )

    def _out(self, out: Path) -> Path:
        out = out.resolve()
        if not out.is_relative_to(self.root / "runs") or out == self.root / "runs":
            raise ValueError("output must be beneath ignored runs")
        return out

    def _original(self, source: Any) -> Path:
        path = Path(source["original_request_path"])
        path = (path if path.is_absolute() else self.root / path).resolve()
        if sha(path) != source["original_request_sha256"] or read(path) != source["control"]:
            raise ValueError("original request identity changed")
        return path

    def _registration_commit(self) -> str:
        paths = [str(path.relative_to(self.root)) for path in self.registered_files]
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", *paths],
            cwd=self.root,
            capture_output=True,
            check=False,
        )
        clean = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", *paths],
            cwd=self.root,
            check=False,
        )
        if tracked.returncode or clean.returncode:
            raise RuntimeError(
                "runner, helpers, tests and registration must be committed and clean"
            )
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.root, text=True
        ).strip()

    def _files(self, out: Path, source_path: Path, source: Any, prefix: list[str]) -> list[Path]:
        return [
            *self.registered_files,
            source_path,
            source_path.with_name("prepare_source.py"),
            source_path.with_name("input-audit.md"),
            self._original(source),
            *transport_files(prefix),
            *(out / name / "system.txt" for name in self.order),
        ]

    def _record(self, out: Path, name: str, request: Any, prefix: list[str]) -> dict[str, Any]:
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

    def _settings(self, source: Any) -> dict[str, Any]:
        return {
            "order": list(self.order),
            "token_stop": self.token_stop,
            "token_counter": "input_tokens + output_tokens",
            "authentication": "chatgpt",
            "reasoning_effort": EFFORT,
            "transport_slot_per_logical_call": "full-1",
            "transport_timeout_seconds": TRANSPORT_TIMEOUT,
            "source_timeout": source["control"]["timeout"],
        }

    def prepare(self, out: Path, source_path: Path) -> None:
        test_guard()
        out, source_path = self._out(out), source_path.resolve()
        if out.exists():
            raise FileExistsError("output directory must be new")
        source = read(source_path)
        requests = self.compose(source)
        if set(requests) != {name.rsplit("-", 1)[0] for name in self.order}:
            raise ValueError("request conditions differ from registered slots")
        self._original(source)
        commit = self._registration_commit()
        prefix = CODEX["command_prefix"]()
        paths = self._files(out, source_path, source, prefix)
        systems = {out / name / "system.txt" for name in self.order}
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
        for name in self.order:
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
                **self._settings(source),
                "source": source,
                "source_path": str(source_path),
                "requests": requests,
                "transformation": self.receipt(source),
                "prefix": prefix,
                "slot_requests": {
                    name: self._record(out, name, requests[name.rsplit("-", 1)[0]], prefix)
                    for name in self.order
                },
                "files": {str(path): sha(path) for path in paths},
                "code_commit": commit,
                "cli_version": version,
            },
        )

    def validate(self, out: Path) -> dict[str, Any]:
        out = self._out(out)
        manifest = CODEX["validate"](out)
        source, prefix = manifest["source"], manifest["prefix"]
        source_path = Path(manifest["source_path"])
        requests = self.compose(source)
        self._original(source)
        if set(requests) != {name.rsplit("-", 1)[0] for name in self.order}:
            raise ValueError("request conditions differ from registered slots")
        if set(manifest["files"]) != {
            str(path) for path in self._files(out, source_path, source, prefix)
        }:
            raise ValueError("frozen file inventory changed")
        if any(manifest.get(key) != value for key, value in self._settings(source).items()):
            raise ValueError("registered dispatch settings changed")
        if manifest.get("transformation") != self.receipt(source):
            raise ValueError("frozen transformation receipt changed")
        if source != read(source_path) or manifest["requests"] != requests:
            raise ValueError("frozen source or request identity changed")
        expected = {
            name: self._record(out, name, requests[name.rsplit("-", 1)[0]], prefix)
            for name in self.order
        }
        if manifest["slot_requests"] != expected:
            raise ValueError("frozen slot request identity changed")
        for name in self.order:
            if (out / name / "system.txt").read_bytes().decode("utf-8") != requests[
                name.rsplit("-", 1)[0]
            ]["system"]:
                raise ValueError("system file differs from frozen request")
            path = out / name / "full-1.request.json"
            if path.exists() and read(path) != expected[name]:
                raise ValueError("recorded request identity changed")
        return manifest

    def quota(self, out: Path) -> int:
        requests, results = list(out.glob("*/*.request.json")), list(out.glob("*/*.result.json"))
        for paths, filename in ((requests, "full-1.request.json"), (results, "full-1.result.json")):
            if any(path.parent.name not in self.order or path.name != filename for path in paths):
                raise ValueError("unregistered invocation or result")
        names, completed = (
            {path.parent.name for path in requests},
            {path.parent.name for path in results},
        )
        if names != set(self.order[: len(names)]):
            raise ValueError("invocation slot order changed")
        if completed - names:
            raise ValueError("result has no recorded request")
        for pattern, filename in (
            ("*/*.raw.json", "full-1.raw.json"),
            ("*/transport-audit.json", "transport-audit.json"),
            ("*/full-1.txt", "full-1.txt"),
        ):
            if any(
                path.parent.name not in names or path.name != filename for path in out.glob(pattern)
            ):
                raise ValueError("orphan or unregistered transport artifact")
        if names - completed:
            raise RuntimeError("request has no result; no retry")
        total = 0
        for path in results:
            result = read(path)
            if result.get("status") != "completed":
                raise RuntimeError("previous failure; no retry")
            total += usage_tokens(result.get("usage"))
            audit_path = path.parent / "transport-audit.json"
            if not audit_path.is_file():
                raise RuntimeError("completed call has no transport audit; no retry")
            checked = audit(path.parent)
            if read(audit_path) != checked:
                raise ValueError("recorded transport artifacts changed")
            if checked["internal_sampling_retry_reported"]:
                raise RuntimeError("internal sampling retry retained; stop without redraw")
        if total >= self.token_stop:
            raise RuntimeError("reported token stop reached")
        return total

    def call(self, out: Path, name: str) -> dict[str, Any]:
        test_guard()
        out = self._out(out)
        if name not in self.order:
            raise ValueError("unregistered invocation")
        frozen = self.validate(out)
        self.quota(out)
        if any(
            not (out / prior / "full-1.result.json").is_file()
            for prior in self.order[: self.order.index(name)]
        ):
            raise ValueError("prior invocation missing")
        folder = out / name
        if (folder / "full-1.result.json").is_file():
            return read(folder / "full-1.result.json")
        if any((folder / "work").iterdir()):
            raise ValueError("isolated work directory is not empty")
        print(f"LOGICAL CALL {name}", flush=True)
        result = CODEX["complete_once"](
            folder,
            "full-1",
            {
                "prefix": frozen["prefix"],
                "requests": {"full": frozen["requests"][name.rsplit("-", 1)[0]]},
            },
            effort=EFFORT,
        )
        checked = audit(folder)
        write_new(folder / "transport-audit.json", checked)
        usage_tokens(result.get("usage"))
        if checked["internal_sampling_retry_reported"]:
            raise RuntimeError("internal sampling retry retained; stop without redraw")
        return result

    def draft(self, out: Path, slot: str | None = None) -> None:
        test_guard()
        if slot is not None and slot not in self.order:
            raise ValueError("unregistered invocation")
        for name in self.order if slot is None else (slot,):
            self.call(out, name)
