"""An amended audit still rejects wrong runtimes and widened world-tool scope."""

import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / (
    "research/quality-measurement/full-book-trial-20260919/readout.py")
spec = importlib.util.spec_from_file_location("full_book_readout_test", PATH)
readout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readout)


@pytest.mark.parametrize("fault", [None, "runtime", "scope", "arguments"])
def test_bridge_check_requires_exact_registered_runtime_and_allowed_arguments(fault):
    executable = Path("registered-runtime/python.exe")
    arguments = (["world", "accept"] if fault == "scope" else ["world", "show"])
    argv = ["wrong-runtime" if fault == "runtime" else str(executable),
            "-m", "litharness", *arguments]
    if fault == "arguments":
        argv += ["--database", "another.db"]
    raw = {"commands_jsonl": json.dumps({"phase": "result", "arguments": arguments, "argv": argv})}
    request = {"allowed_tools": ["Bash(litharness world show:*)"]}
    result, _observed = readout.bridge_check(raw, request, executable)
    assert result is (fault is None)
