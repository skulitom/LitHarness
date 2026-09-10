"""Read, compare and search recorded generation calls without opening a store or provider.

Application traces, completion receipts and native Codex traces remain separate evidence
layers. Missing transport data never becomes an assertion that no extra context was sent.
Default reports contain hashes and locations; excerpts require an explicit request.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def encoded(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def native_records(source: dict[str, Any], gaps: list[str]) -> list[dict[str, Any]]:
    """Retain valid events when failed native stdout also contains warnings or truncation."""
    events = source.get("events")
    if isinstance(events, list):
        return [e for e in events if isinstance(e, dict)]
    stdout = source.get("stdout")
    if not isinstance(stdout, str) or not stdout.strip():
        return []
    try:
        value = json.loads(stdout)
        if isinstance(value, dict):
            return [value]
        return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []
    except ValueError:
        records, skipped = [], 0
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if isinstance(event, dict):
                    records.append(event)
            except ValueError:
                skipped += 1
        if skipped:
            gaps.append(f"Native stdout has {skipped} non-JSON or truncated lines; retained file.")
        return records


def option(argv: list[Any] | None, flag: str) -> Any:
    if argv is not None and flag in argv and argv.index(flag) + 1 < len(argv):
        return argv[argv.index(flag) + 1]
    return None


@dataclass
class Trace:
    path: Path
    file_sha256: str
    profile: str | None
    model: str | None
    fields: dict[str, str]
    sessions: list[str]
    configuration: dict[str, Any] | None
    gaps: list[str]
    status: str | None

    def summary(self) -> dict[str, Any]:
        fingerprints = {key: digest(value) for key, value in self.fields.items()}
        return {
            "path": str(self.path),
            "file_sha256": self.file_sha256,
            "profile": self.profile,
            "recorded_model": self.model,
            "status": self.status,
            "sessions": self.sessions,
            "field_sha256": fingerprints,
            "field_characters": {key: len(value) for key, value in self.fields.items()},
            "application_input_sha256": self.input_digest("application"),
            "transport_input_sha256": self.input_digest("transport"),
            "configuration": self.configuration,
            "gaps": self.gaps,
        }

    def input_digest(self, layer: str) -> str | None:
        values = {k: v for k, v in self.fields.items() if k.startswith(layer + ".")}
        if not {layer + ".system", layer + ".prompt"} <= values.keys():
            return None
        return digest(encoded(values))


def load_trace(path: Path) -> Trace:
    data = path.read_bytes()
    record = json.loads(data.decode("utf-8-sig"))
    if not isinstance(record, dict):
        raise ValueError("trace root is not an object")
    request = record.get("request")
    result = record.get("result")
    if request is None and {"system", "prompt"} <= record.keys() and "argv" not in record:
        request = record
    if isinstance(request, dict):
        raw = result.get("raw") if isinstance(result, dict) else record.get("raw")
        raw = raw if isinstance(raw, dict) else None
        response = result.get("text") if isinstance(result, dict) else record.get("response")
        profile = request.get("profile", record.get("profile"))
        model = result.get("model") if isinstance(result, dict) else record.get("model")
        model = model or request.get("model")
    elif {"provider", "prompt", "system", "argv"} <= record.keys():
        request, raw = None, record
        response, profile, model = raw.get("final_text"), None, raw.get("requested_model")
    else:
        raise ValueError("unsupported trace envelope")

    # An instrumented launch is separate from the provider's returned envelope. Legacy
    # Claude envelopes report sessions/model usage but do not capture submitted inputs.
    launch = record.get("transport")
    native = launch if isinstance(launch, dict) else raw
    fields: dict[str, str] = {}
    gaps = []
    if record.get("contains_exemplar_material"):
        gaps.append("Application input withheld: trace marks exemplar material.")
        request = None
    for layer, source in (("application", request), ("transport", native)):
        if record.get("contains_exemplar_material") and source is not None:
            gaps.append(f"{layer} input withheld: trace marks exemplar material.")
            continue
        if source is None:
            gaps.append(f"{layer} input not captured.")
            continue
        for name in ("system", "prompt"):
            value = source.get(name)
            if isinstance(value, str):
                fields[f"{layer}.{name}"] = value
            else:
                gaps.append(f"{layer}.{name} not captured.")
        schema_name = "native_schema" if layer == "transport" else "schema"
        if schema_name in source:
            fields[f"{layer}.schema"] = encoded(source[schema_name])
        if layer == "application":
            fields["application.parameters"] = encoded(
                {k: v for k, v in source.items() if k not in {"system", "prompt", "schema"}}
            )
    if isinstance(response, str):
        fields["output.text"] = response
    else:
        gaps.append("Final output text not captured.")
    configuration = None
    sessions: list[str] = []
    if native is not None:
        events = native_records(native, gaps)
        if raw is not None:
            events.append(raw)
        sessions = sorted(
            {
                e["thread_id"]
                for e in events
                if e.get("type") == "thread.started" and isinstance(e.get("thread_id"), str)
            }
            | {e["session_id"] for e in events if isinstance(e.get("session_id"), str)}
        )
        argv = native.get("argv")
        argv = argv if isinstance(argv, list) else None
        settings = native.get("settings")
        if settings is None and isinstance(value := option(argv, "--settings"), str):
            settings = json.loads(value)
        # The file's captured contents above matter; its temporary filename is incidental.
        settings = (
            {k: v for k, v in settings.items() if k != "model_instructions_file"}
            if isinstance(settings, dict)
            else None
        )
        if argv is not None or settings is not None:
            configuration = {
                "provider": native.get("provider"),
                "requested_model": native.get("requested_model") or option(argv, "--model"),
                "cli_version": native.get("cli_version"),
                "mode": native.get("mode"),
                "settings": settings,
                "sampler_requested": request.get("sampler") if request else None,
            }
            for flag in (
                "output-schema",
                "json",
                "ephemeral",
                "ignore-user-config",
                "ignore-rules",
                "safe-mode",
                "no-session-persistence",
                "strict-mcp-config",
            ):
                configuration[flag.replace("-", "_")] = (
                    "--" + flag in argv if argv is not None else None
                )
            for flag in ("tools", "allowed-tools", "setting-sources", "permission-mode"):
                configuration[flag.replace("-", "_")] = option(argv, "--" + flag)
        else:
            gaps.append("Native launch configuration not captured.")
        if not sessions:
            gaps.append("Native session identity not captured.")
        if not (raw and isinstance(raw.get("modelUsage"), dict) and raw["modelUsage"]):
            gaps.append("Backend-resolved model not reported.")
        gaps.append("Resolved sampling distribution is not reported.")
    return Trace(
        path.resolve(),
        hashlib.sha256(data).hexdigest(),
        profile,
        model,
        fields,
        sessions,
        configuration,
        gaps,
        record.get("status"),
    )


def compare(left: Trace, right: Trace, *, show_text: bool = False) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in sorted(left.fields.keys() | right.fields.keys()):
        before, after = left.fields.get(key), right.fields.get(key)
        item: dict[str, Any] = {
            "equal": before == after if before is not None and after is not None else None,
            "left_sha256": digest(before) if before is not None else None,
            "right_sha256": digest(after) if after is not None else None,
        }
        if show_text and before is not None and after is not None and before != after:
            item["diff"] = list(
                difflib.unified_diff(
                    before.splitlines(),
                    after.splitlines(),
                    fromfile="left",
                    tofile="right",
                    lineterm="",
                )
            )
        fields[key] = item
    return {
        "left": left.summary(),
        "right": right.summary(),
        "fields": fields,
        "configuration_equal": (
            left.configuration == right.configuration
            if left.configuration is not None and right.configuration is not None
            else None
        ),
        "same_native_session": (
            bool(set(left.sessions) & set(right.sessions))
            if left.sessions and right.sessions
            else None
        ),
        "limitation": "Equal inputs or separate sessions do not explain the model's choice.",
    }


def search(trace: Trace, pattern: re.Pattern[str], *, context: int = 0) -> list[dict[str, Any]]:
    hits = []
    for field, value in trace.fields.items():
        for match in pattern.finditer(value):
            hit: dict[str, Any] = {
                "path": str(trace.path),
                "file_sha256": trace.file_sha256,
                "profile": trace.profile,
                "field": field,
                "field_sha256": digest(value),
                "start": match.start(),
                "end": match.end(),
                "line": value.count("\n", 0, match.start()) + 1,
            }
            if context:
                hit["excerpt"] = value[max(0, match.start() - context) : match.end() + context]
            hits.append(hit)
    return hits


def paths(roots: list[Path], pattern: str) -> list[Path]:
    result: set[Path] = set()
    for root in roots:
        if not root.exists():
            raise ValueError(f"Missing path: {root}")
        result.update(root.rglob(pattern) if root.is_dir() else [root])
    return sorted(p.resolve() for p in result if p.is_file())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inventory", "search"):
        command = sub.add_parser(name)
        command.add_argument("paths", nargs="+", type=Path)
        command.add_argument("--glob", default="discovery-trace.json")
        command.add_argument("--profile")
        if name == "search":
            command.add_argument("--query", required=True)
            command.add_argument("--regex", action="store_true")
            command.add_argument("--context", type=int, choices=range(201), default=0)
    command = sub.add_parser("compare")
    command.add_argument("left", type=Path)
    command.add_argument("right", type=Path)
    command.add_argument("--text-diff", action="store_true")
    command = sub.add_parser("show", help="Explicitly display a complete captured field")
    command.add_argument("path", type=Path)
    command.add_argument(
        "--field",
        default="output.text",
        choices=(
            "application.system",
            "application.prompt",
            "application.schema",
            "application.parameters",
            "transport.system",
            "transport.prompt",
            "transport.schema",
            "output.text",
        ),
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "show":
            trace = load_trace(args.path)
            if args.field not in trace.fields:
                raise ValueError(f"{args.field} unavailable: {' '.join(trace.gaps)}")
            report = {
                "trace": trace.summary(),
                "field": args.field,
                "text": trace.fields[args.field],
            }
        elif args.command == "compare":
            report = compare(
                load_trace(args.left), load_trace(args.right), show_text=args.text_diff
            )
        else:
            traces, errors = [], []
            for path in paths(args.paths, args.glob):
                try:
                    trace = load_trace(path)
                    if args.profile is None or trace.profile == args.profile:
                        traces.append(trace)
                except (ValueError, OSError) as error:
                    errors.append({"path": str(path), "error": str(error)})
            report = {
                "traces": [t.summary() for t in traces],
                "errors": errors,
                "profile_counts": dict(Counter(t.profile for t in traces)),
                "input_groups": dict(
                    Counter(
                        value
                        for t in traces
                        if (value := t.input_digest("application")) is not None
                    )
                ),
                "limitation": "Files may mirror one call; do not count files as independent draws.",
            }
            output_groups: dict[str, list[str]] = {}
            session_groups: dict[str, list[str]] = {}
            for trace in traces:
                if "output.text" in trace.fields:
                    output_groups.setdefault(digest(trace.fields["output.text"]), []).append(
                        str(trace.path)
                    )
                for session in trace.sessions:
                    session_groups.setdefault(session, []).append(str(trace.path))
            report["repeated_outputs"] = {k: v for k, v in output_groups.items() if len(v) > 1}
            report["shared_sessions"] = {k: v for k, v in session_groups.items() if len(v) > 1}
            if args.command == "search":
                pattern = re.compile(args.query if args.regex else re.escape(args.query), re.I)
                report["hits"] = [
                    h for t in traces for h in search(t, pattern, context=args.context)
                ]
            if not traces and not errors:
                raise ValueError("No matching traces")
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 1 if report.get("errors") else 0
    except (ValueError, OSError, re.error) as error:
        print(json.dumps({"error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
