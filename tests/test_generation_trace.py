"""Recorded inputs remain distinct from transport, missing evidence and fresh draws."""

import json

from tools.generation_trace import compare, load_trace, main, search


def receipt(tmp_path, name="one", *, session="s1", extra="", text="A water wheel."):
    path = tmp_path / f"{name}.json"
    raw = {
        "provider": "codex",
        "requested_model": "test-model",
        "system": "Invent." + extra,
        "prompt": "A story.",
        "native_schema": None,
        "argv": ["--ephemeral"],
        "settings": {"model_instructions_file": f"/temp/{name}", "features.memories": False},
        "events": [{"type": "thread.started", "thread_id": session}],
    }
    data = {
        "request": {"profile": "discovery", "system": "Invent.", "prompt": "A story."},
        "result": {"text": text, "model": "test-model", "raw": raw},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_comparison_locates_transport_added_material(tmp_path):
    left = load_trace(receipt(tmp_path))
    right = load_trace(receipt(tmp_path, "two", extra=" Repair a pump.", session="s2"))
    result = compare(left, right)
    assert result["fields"]["application.system"]["equal"] is True
    assert result["fields"]["transport.system"]["equal"] is False
    assert result["configuration_equal"] is True
    assert result["same_native_session"] is False
    assert "Repair" not in json.dumps(result)


def test_identical_outputs_from_fresh_sessions_are_not_deduplicated(tmp_path, capsys):
    one = receipt(tmp_path)
    two = receipt(tmp_path, "two", session="s2")
    assert main(["inventory", str(one), str(two)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result["traces"]) == 2
    assert result["traces"][0]["sessions"] != result["traces"][1]["sessions"]
    assert len(result["repeated_outputs"]) == 1
    assert result["shared_sessions"] == {}


def test_missing_transport_is_unknown_not_equal_or_isolated(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "profile": "discovery",
                "request": {"system": "Invent.", "prompt": "A story."},
                "response": "A water wheel.",
            }
        ),
        encoding="utf-8",
    )
    left = load_trace(path)
    result = compare(left, load_trace(receipt(tmp_path)))
    assert result["configuration_equal"] is None
    assert result["same_native_session"] is None
    assert result["fields"]["transport.system"]["equal"] is None
    assert left.input_digest("transport") is None


def test_search_locates_output_and_does_not_invent_input_match(tmp_path):
    import re

    trace = load_trace(receipt(tmp_path, text="First.\nA water wheel."))
    hits = search(trace, re.compile("water"))
    assert len(hits) == 1 and hits[0]["field"] == "output.text"
    assert hits[0]["line"] == 2
    assert "excerpt" not in hits[0]
    assert trace.fields["output.text"][hits[0]["start"] : hits[0]["end"]] == "water"
    assert "water" in search(trace, re.compile("water"), context=5)[0]["excerpt"]


def test_failed_native_trace_retains_output_and_session_from_stdout(tmp_path):
    path = receipt(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))["result"]["raw"]
    data["stdout"] = "Native warning\n" + "\n".join(json.dumps(e) for e in data.pop("events"))
    data["final_text"] = "Retained output."
    data["failure"] = {"message": "rejected"}
    path.write_text(json.dumps(data), encoding="utf-8")
    trace = load_trace(path)
    assert trace.sessions == ["s1"]
    assert trace.fields["output.text"] == "Retained output."
    assert "non-JSON or truncated" in " ".join(trace.gaps)


def test_claude_envelope_session_does_not_imply_captured_launch(tmp_path):
    path = receipt(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["result"]["raw"] = {"session_id": "claude-session", "modelUsage": {"opus": {}}}
    path.write_text(json.dumps(data), encoding="utf-8")
    trace = load_trace(path)
    assert trace.sessions == ["claude-session"]
    assert trace.configuration is None
    assert trace.input_digest("transport") is None
    data["transport"] = {
        "provider": "claude_code",
        "system": "Launch system",
        "prompt": "Launch prompt",
        "native_schema": None,
        "argv": [
            "--safe-mode",
            "--no-session-persistence",
            "--tools",
            "",
            "--settings",
            '{"autoMemoryEnabled":false}',
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    trace = load_trace(path)
    assert trace.fields["transport.system"] == "Launch system"
    assert trace.sessions == ["claude-session"]
    assert trace.configuration["safe_mode"] is True
    assert trace.configuration["tools"] == ""
    assert trace.configuration["settings"] == {"autoMemoryEnabled": False}


def test_missing_argv_does_not_report_disabled_isolation_flags(tmp_path):
    path = receipt(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["result"]["raw"]["argv"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert load_trace(path).configuration["ephemeral"] is None
    assert load_trace(path).configuration["output_schema"] is None


def test_native_schema_constraint_is_distinct_from_json_event_logging(tmp_path):
    paths = [receipt(tmp_path, name) for name in ("native", "relocated", "prompt_only")]
    for index, path in enumerate(paths):
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data["result"]["raw"]
        raw["argv"] = ["--ephemeral", "--json"]
        if index < 2:
            raw["argv"] += ["--output-schema", f"/temp/{index}/schema.json"]
            raw["native_schema"] = {"type": "object"}
        path.write_text(json.dumps(data), encoding="utf-8")
    native, relocated, prompt_only = [load_trace(path) for path in paths]
    assert native.configuration["output_schema"] is True
    assert prompt_only.configuration["output_schema"] is False
    assert prompt_only.configuration["json"] is True
    assert compare(native, relocated)["configuration_equal"] is True
    assert compare(native, prompt_only)["configuration_equal"] is False


def test_show_opens_complete_field_but_respects_withheld_inputs(tmp_path, capsys):
    path = receipt(tmp_path, text="Complete recorded output.")
    assert main(["show", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["text"] == "Complete recorded output."
    data = json.loads(path.read_text(encoding="utf-8"))
    data["contains_exemplar_material"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["show", str(path), "--field", "application.system"]) == 2
    assert "withheld" in capsys.readouterr().out


def test_marked_exemplar_input_is_withheld(tmp_path):
    path = receipt(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["contains_exemplar_material"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    trace = load_trace(path)
    assert "application.system" not in trace.fields
    assert "transport.system" not in trace.fields
    assert "withheld" in " ".join(trace.gaps)


def test_prepared_requests_expose_parameter_differences_without_inventing_output(tmp_path):
    one, two = tmp_path / "one.json", tmp_path / "two.json"
    request = {"system": "Invent.", "prompt": "A story.", "max_output_tokens": 200}
    one.write_text(json.dumps(request), encoding="utf-8")
    two.write_text(json.dumps({**request, "max_output_tokens": 400}), encoding="utf-8")
    left, right = load_trace(one), load_trace(two)
    result = compare(left, right)
    assert result["fields"]["application.parameters"]["equal"] is False
    assert "output.text" not in left.fields
    assert result["configuration_equal"] is None


def test_bad_and_missing_files_are_reported_without_creating_them(tmp_path, capsys):
    missing = tmp_path / "missing.json"
    assert main(["inventory", str(missing)]) == 2
    assert not missing.exists()
    capsys.readouterr()
    bad = tmp_path / "discovery-trace.json"
    bad.write_text("not JSON", encoding="utf-8")
    assert main(["inventory", str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out)["errors"]
