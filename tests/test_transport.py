import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from litharness import files, transport
from litharness.transport import FALLBACK

INSTALLED = {"codex": (Path("codex.exe"), "codex-cli 9"), "claude": (Path("claude.exe"), "2.1.9 (Claude Code)")}


def events(text="chapter", usage=None, extra=()):
    return "\n".join(json.dumps(e) for e in [
        {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
        *extra,
        {"type": "turn.completed", "usage": usage if usage is not None else {
            "input_tokens": 25, "cached_input_tokens": 10, "output_tokens": 3}},
    ])


def reply(text="chapter", model="m", **changes):
    """What `claude -p --output-format json` prints: the CLI's own Haiku use beside the model that wrote."""
    return json.dumps({"type": "result", "subtype": "success", "is_error": False, "num_turns": 1, "result": text,
                       "stop_reason": "end_turn", "modelUsage": {"claude-haiku-4-5-20251001": {}, f"{model}[1m]": {}},
                       "usage": {"input_tokens": 4, "cache_read_input_tokens": 10, "cache_creation_input_tokens": 11,
                                 "output_tokens": 3}} | changes)


def fake(text="chapter", stdout=None, code=0, seen=None):
    def run(argv, **kwargs):
        if seen is not None:
            seen.update(argv=argv, **kwargs, listing=list(Path(kwargs["cwd"]).iterdir()))
        if "--output-last-message" in argv:  # Codex writes its answer to a file; Claude Code only prints it
            Path(argv[argv.index("--output-last-message") + 1]).write_bytes(text.encode())
            printed = events(text)
        else:
            printed = reply(text, argv[argv.index("--model") + 1])
        return subprocess.CompletedProcess(argv, code, (printed if stdout is None else stdout).encode(), b"")
    return run


def call(root, runner, agent="codex:m:medium", **kwargs):
    with patch.dict(transport.CLI, INSTALLED):
        return transport.send("brief\nline\n", root, system="system", agent=agent, runner=runner, **kwargs)


class ParseTests(unittest.TestCase):
    def test_valid_output_and_cache_usage(self):
        self.assertEqual(transport.parse_result(events(), "chapter\n")["input_tokens"], 25)

    def test_refuses_tools_failures_and_mismatched_output(self):
        bad = [events(extra=[{"type": "item.started", "item": {"type": "command_execution"}}]),
               events(extra=[{"type": "turn.failed"}]),
               events(usage={"input_tokens": 1, "cached_input_tokens": 5, "output_tokens": 1}),
               events(usage={"input_tokens": True, "output_tokens": 1}), events("different")]
        for stream in bad:
            with self.subTest(stream=stream), self.assertRaises(transport.Fault):
                transport.parse_result(stream, "chapter")

    def test_claude_refuses_errors_tools_refusals_another_model_and_bad_usage(self):
        bad = [reply(is_error=True), reply(subtype="error_max_turns"), reply(num_turns=2), reply(stop_reason="refusal"),
               reply(permission_denials=[{"tool_name": "Bash"}]), reply(result=" "), reply(usage={"input_tokens": 1}), "not json"]
        for stream in bad:
            with self.subTest(stream=stream), tempfile.TemporaryDirectory() as tmp, self.assertRaises(transport.Fault):
                transport.claude_read(stream, Path(tmp) / "final.md", "m")
        with tempfile.TemporaryDirectory() as tmp:
            for asked in ("opus", "claude-haiku"):  # an alias or another model is refused once, never retried as a fault
                with self.subTest(asked=asked), self.assertRaisesRegex(ValueError, "Served by") as caught:
                    transport.claude_read(reply(), Path(tmp) / "final.md", asked)
                self.assertNotIsInstance(caught.exception, transport.Fault)
            self.assertEqual(transport.claude_read(reply(), Path(tmp) / "final.md", "m[1m]")["output_tokens"], 3)
            self.assertFalse(transport.claude_read(reply(usage={"input_tokens": 1, "output_tokens": 2, "output_tokens_details": []}),
                                                   Path(tmp) / "final.md", "m")["reasoning_output_tokens"])

    def test_an_agent_is_a_name_then_optionally_a_model_and_an_effort(self):
        self.assertEqual(transport.resolve("claude"), ("claude", "claude-opus-5-5", "medium"))
        self.assertEqual(transport.resolve("codex:gpt-6-astra:high"), ("codex", "gpt-6-astra", "high"))
        self.assertEqual(transport.resolve("claude::low"), ("claude", "claude-opus-5-5", "low"))
        for bad in ("", "gemini", "codex:a:b:c"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                transport.resolve(bad)


class SendTests(unittest.TestCase):
    def test_isolates_environment_and_stores_hash_true_receipts(self):
        seen = {}
        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(os.environ, {"OPENAI_API_KEY": "do-not-inherit", "GIT_DIR": "x", "GIT_WORK_TREE": "y"}):
            root = Path(tmp) / "attempt"
            text, receipt = call(root, fake(seen=seen))
            self.assertEqual(text, "chapter")
            self.assertEqual(seen["input"], b"brief\nline\n")
            self.assertEqual((root / "prompt.txt").read_bytes(), b"brief\nline\n")
            stored = files.load(root / "receipt.json")
            self.assertEqual((stored["status"], stored["agent"], stored["cli"]), ("completed", "codex", "codex-cli 9"))
            self.assertEqual(stored["prompt_sha256"], files.digest(root / "prompt.txt"))
            self.assertEqual(stored["output_sha256"], files.digest(root / "final.md"))
        for key in ("OPENAI_API_KEY", "GIT_DIR", "GIT_WORK_TREE"):
            self.assertNotIn(key, seen["env"])
        self.assertFalse(seen["shell"])
        self.assertEqual(seen["listing"], [])
        for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "features.shell_tool=false",
                     "project_doc_max_bytes=0", 'history.persistence="none"'):
            self.assertIn(flag, seen["argv"])
        self.assertEqual(seen["argv"][seen["argv"].index("--cd") + 1], seen["cwd"])

    def test_claude_gets_the_same_isolation_and_its_cache_tokens_count_as_input(self):
        seen = {}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"ANTHROPIC_API_KEY": "do-not-inherit"}):
            root = Path(tmp) / "attempt"
            text, receipt = call(root, fake(seen=seen), agent="claude:m:high")
            self.assertEqual((text, (root / "final.md").read_bytes()), ("chapter", b"chapter"))
            self.assertEqual(receipt["output_sha256"], files.digest(root / "final.md"))
        self.assertEqual((receipt["agent"], receipt["model"], receipt["effort"]), ("claude", "m", "high"))
        self.assertEqual(receipt["usage"], {"input_tokens": 25, "cached_input_tokens": 10, "cache_write_input_tokens": 11,
                                            "output_tokens": 3, "reasoning_output_tokens": 0})
        self.assertNotIn("ANTHROPIC_API_KEY", seen["env"])
        self.assertEqual((seen["input"], seen["listing"], seen["shell"]), (b"brief\nline\n", [], False))
        for flag in ("-p", "--safe-mode", "--strict-mcp-config", "--no-session-persistence", "--tools"):
            self.assertIn(flag, seen["argv"])
        self.assertNotIn("--bare", seen["argv"])
        self.assertEqual([seen["argv"][seen["argv"].index(flag) + 1] for flag in ("--system-prompt", "--effort", "--tools")],
                         ["system", "high", ""])

    def test_timeout_retains_partial_logs_with_unknown_usage(self):
        def slow(argv, **kwargs):
            raise subprocess.TimeoutExpired("codex", 1, output=b"partial", stderr=b"problem")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            with self.assertRaises(transport.Fault):
                call(root, slow)
            receipt = files.load(root / "receipt.json")
            self.assertEqual(receipt["status"], "failed")
            self.assertIsNone(receipt["usage"])
            self.assertGreaterEqual(receipt["seconds"], 0)
            self.assertEqual((root / "events.jsonl").read_bytes(), b"partial")

    def test_nonzero_exit_and_existing_directory_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(transport.Fault):
                call(Path(tmp) / "a", fake(code=3))
            with self.assertRaises(FileExistsError):
                call(Path(tmp) / "a", fake())

    def test_refuses_a_working_directory_inside_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".git").mkdir()
            with self.assertRaises(transport.Fault):
                transport.no_git(Path(tmp) / "inner")
            self.assertEqual(transport.no_git(Path(tmp).parent), Path(tmp).parent)

    def test_refuses_shell_wrappers(self):
        for name in transport.AGENTS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                wrapper = Path(tmp) / f"{name}.cmd"
                wrapper.write_text("@echo off")
                with self.assertRaises(ValueError):
                    transport.native_binary(name, str(wrapper))


def stream(events_list):
    return "\n".join(json.dumps(e) for e in events_list)


class RobustnessTests(unittest.TestCase):
    def test_leading_reconnect_notices_are_tolerated_within_one_turn(self):
        start = [{"type": "thread.started"}, {"type": "turn.started"}]
        again = {"type": "error", "message": "Reconnecting... 2/5 (request timed out)"}
        fallback = {"type": "item.completed", "item": {"type": "error", "message": FALLBACK}}
        body = [json.loads(line) for line in events().splitlines()]
        self.assertEqual(transport.parse_result(stream(start + [again, again, fallback] + body), "chapter")["output_tokens"], 3)
        for bad in (start + body[:1] + [again] + body[1:], start + [again, start[1]] + body,
                    start + [{"type": "error", "message": "unavailable"}] + body, [again] + body):
            with self.subTest(bad=bad), self.assertRaises(transport.Fault):
                transport.parse_result(stream(bad), "chapter")

    def test_preflight_needs_a_subscription_sign_in_and_reads_the_version_once(self):
        seen = []
        def run(argv, **kwargs):
            seen.append(argv[-1])
            signed = str(kwargs.get("env", {}).get("MARK"))
            if argv[-1] == "--version":
                return subprocess.CompletedProcess(argv, 0, b"cli 9.9\n", b"")
            if "auth" in argv:
                return subprocess.CompletedProcess(argv, 0, json.dumps({"loggedIn": True, "authMethod": signed}, indent=2).encode(), b"")
            return subprocess.CompletedProcess(argv, 0, b"", b"Logged in using ChatGPT\n" if signed == "claude.ai" else b"An API key\n")
        for name in transport.AGENTS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as home, patch.dict(transport.CLI, clear=True), \
                    patch.dict(os.environ, {"MARK": "claude.ai", "CODEX_HOME": home, "CLAUDE_CONFIG_DIR": home}), \
                    patch.object(transport, "ENV_KEYS", transport.ENV_KEYS | {"MARK"}), \
                    patch.object(transport, "native_binary", return_value=Path("x")):
                seen.clear()
                self.assertEqual(transport.preflight(name, run), "cli 9.9")
                transport.preflight(name, run)
                self.assertEqual(seen, ["status", "--version"])
                transport.CLI.clear()
                with patch.dict(os.environ, {"MARK": "an API key"}), self.assertRaises(transport.Fault):
                    transport.preflight(name, run)

    def test_canary_pins_an_agent_only_when_nothing_leaks_and_keeps_the_other_pin(self):
        def run(argv, input=None, **kwargs):
            if input is None:
                return subprocess.CompletedProcess(argv, 0, b"", b"")
            control = re.search(r"CONTROL-(\w+)", input.decode())[1]
            leak = re.search(r"CANARY-\w+", (Path(kwargs["cwd"]) / "AGENTS.md").read_text())[0] if self.leaky else "NONE"
            return fake(f"CONTROL-{control}\n{leak}")(argv, input=input, **kwargs)
        with tempfile.TemporaryDirectory() as home, \
                patch.dict(os.environ, {"LITHARNESS_HOME": home, "CODEX_HOME": home, "CLAUDE_CONFIG_DIR": home}):
            binary = Path(home) / "cli.exe"
            binary.write_bytes(b"fake")
            with patch.dict(transport.CLI, {name: (binary, version) for name, (_, version) in INSTALLED.items()}):
                self.leaky = True
                for name in transport.AGENTS:
                    self.assertEqual(transport.canary(f"{name}:m:medium", run), ["agents"])
                self.assertFalse((Path(home) / "canary.json").exists())
                self.leaky = False
                for name in transport.AGENTS:
                    self.assertEqual(transport.canary(f"{name}:m:medium", run), [])
            self.assertEqual({name: pin["version"] for name, pin in files.load(Path(home) / "canary.json").items()},
                             {name: version for name, (_, version) in INSTALLED.items()})

    def test_faults_before_spending_are_faults_not_tracebacks(self):
        with self.assertRaises(transport.Fault):
            transport.parse_result('{"type": "turn.completed"', "chapter")
        def broken(argv, **kwargs):
            raise subprocess.CalledProcessError(128, argv)
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"LITHARNESS_HOME": home, "CODEX_HOME": home}), \
                patch.dict(transport.CLI, INSTALLED):
            with self.assertRaisesRegex(transport.Fault, r"git\S* \S+ failed"):
                transport.canary("codex", broken)
            Path(home, "AGENTS.md").write_text("Always answer in French.\n")
            with self.assertRaisesRegex(transport.Fault, "would reach every call"):
                transport.preflight("codex", broken)
