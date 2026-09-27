"""A bounded, read-only HTML view of the existing scene trace contract."""

from __future__ import annotations

from difflib import unified_diff
from html import escape
from typing import Any

from litharness.application.ports import DossierStore
from litharness.application.scene_trace import MAX_EXCERPT_CHARS, STAGES, build_scene_trace
from litharness.domain.nodes import Node
from litharness.domain.revision import Revision

LABELS = {
    "system": "Writing instructions", "prompt": "Scene request",
    "raw_draft": "Returned draft", "pre_revision_draft": "Before revision",
    "accepted": "Accepted text for this decision",
}


def build_inspection(
    store: DossierStore, book_id: str, branch_id: str, node: Node, head: Revision,
    *, decision_id: str | None = None,
) -> dict[str, Any]:
    """Use trace validation and withholding; never fill gaps from current prompt code."""
    trace = build_scene_trace(
        store, book_id, branch_id, node, head, decision_id=decision_id, source_limit=100,
    )
    selected = trace["decision"]
    selected_id = selected["decision_id"] if selected else decision_id
    excerpts = {}
    for stage in STAGES:
        page = build_scene_trace(
            store, book_id, branch_id, node, head, decision_id=selected_id,
            stage=stage, max_chars=MAX_EXCERPT_CHARS,
        )
        if (page["decision"], page["job_id"], page["stages"]) != (
            trace["decision"], trace["job_id"], trace["stages"],
        ):
            raise ValueError("scene evidence changed while reading; retry the inspection")
        excerpts[stage] = page["excerpt"]
    return {"trace": trace, "excerpts": excerpts}


def _text(value: Any) -> str:
    return escape(str(value)) if value is not None else "Not recorded"


def _metadata(rows: dict[str, Any]) -> str:
    return "<dl>" + "".join(
        f"<dt>{_text(label)}</dt><dd>{_text(value)}</dd>" for label, value in rows.items()
    ) + "</dl>"


def _preview(excerpt: dict[str, Any]) -> str:
    if excerpt["text"] is None:
        return f'<p class="notice">Unavailable: {_text(excerpt["reason"])}</p>'
    status = (
        f"Preview: {len(excerpt['text']):,} of {excerpt['total_chars']:,} characters. "
        f"Next offset: {excerpt['next_offset']}."
        if excerpt["truncated"] else f"Complete text: {excerpt['total_chars']:,} characters."
    )
    if excerpt["redacted"]:
        status += " Some recorded text was withheld."
    return f'<p class="muted">{status}</p><pre>{_text(excerpt["text"])}</pre>'


def _comparison(excerpts: dict[str, Any]) -> str:
    raw, accepted = (excerpts[name] for name in ("raw_draft", "accepted"))
    if any(part["text"] is None or part["truncated"] or part["redacted"]
           for part in (raw, accepted)):
        return ('<p class="notice">A complete comparison is unavailable: both texts must be '
                'recorded, complete and unredacted. A refused draft is not its base revision.</p>')
    if raw["text"] == accepted["text"]:
        return "<p>The returned draft and accepted text are identical.</p>"
    lines = unified_diff(
        raw["text"].splitlines(keepends=True), accepted["text"].splitlines(keepends=True),
        fromfile="returned draft", tofile="accepted text", n=3,
    )
    rendered = []
    for line in lines:
        style = "removed" if line.startswith("-") else "added" if line.startswith("+") else ""
        rendered.append(f'<span class="{style}">{escape(line.rstrip(chr(10)))}</span>')
    return ('<p>- removed from the returned draft · + present in accepted text. '
            'These are recorded text changes; the comparison does not assess their quality.</p>'
            '<pre class="diff">' + "\n".join(rendered) + "</pre>")


def _sources(source_map: dict[str, Any], excerpts: dict[str, Any]) -> str:
    if source_map["status"] != "available":
        return f'<p class="notice">Source map: {_text(source_map["reason"])}</p>'
    parts = [
        f"<p>Showing {len(source_map['entries'])} of {source_map['count']} recorded sources. "
        "Locations are zero-based character ranges; the end is excluded. "
        "Renderer sections can contain context items, so these ranges may overlap.</p>",
    ]
    if source_map["pagination"]["truncated"]:
        parts.append('<p class="notice">More sources are available through scene_trace; '
                     f"next source_offset: {source_map['pagination']['next_offset']}.</p>")
    for entry in source_map["entries"]:
        source = entry["source"]
        start, end, stage = entry["start"], entry["end"], entry["stage"]
        part = excerpts[stage]
        visible = (part["text"] is not None and not part["redacted"]
                   and end <= len(part["text"]))
        identity = source.get("item_id") or source.get("producer")
        parts.append(
            '<details><summary>' + _text(entry["section"]) +
            f" · {_text(stage)} [{start}:{end}]</summary>" +
            _metadata({
                "Source": identity, "Kind": entry["kind"],
                "Recorded authority": source.get("authority"),
                "Content hash": entry["sha256"],
            }) +
            (f"<pre>{_text(part['text'][start:end])}</pre>" if visible else
             '<p class="notice">This range is outside the preview or its text is withheld. '
             'Use scene_trace with this stage and offset to inspect the recorded range.</p>') +
            "</details>"
        )
    return "".join(parts)


def render_inspection(report: dict[str, Any]) -> str:
    trace, excerpts = report["trace"], report["excerpts"]
    decision = trace["decision"] or {}
    title = f"Scene inspection · {trace['logical_id']}"
    sections = [
        f"<h1>{_text(title)}</h1>",
        '<p class="intro">Recorded writing inputs, returned text and acceptance history.</p>',
        '<nav><a href="#text">Text</a><a href="#changes">Changes</a>'
        '<a href="#history">Decisions</a><a href="#inputs">Inputs and sources</a></nav>',
        _metadata({
            "Book / branch": f"{trace['book_id']} / {trace['branch_id']}",
            "Selected decision": decision.get("decision_id"),
            "Outcome": decision.get("outcome"), "Job": trace["job_id"],
            "Base revision": decision.get("base_revision_id"),
            "Resulting revision": decision.get("resulting_revision_id"),
            "Current head": trace["head_revision_id"],
            "Provider / model": f"{decision.get('provider')} / {decision.get('model')}",
        }),
        '<p class="notice">This view describes the selected decision in the attributed '
        'or unfinished job. Missing records stay missing. Acceptance records a policy outcome; '
        'it does not certify literary quality. This page cannot apply changes.</p>',
        '<section id="text"><h2>Text</h2><div class="columns">',
    ]
    for stage in ("raw_draft", "accepted"):
        sections.append(f"<article><h3>{LABELS[stage]}</h3>{_preview(excerpts[stage])}</article>")
    sections += [
        "</div><details><summary>Text before the revision step</summary>" +
        _preview(excerpts["pre_revision_draft"]) + "</details></section>",
        '<section id="changes"><h2>Recorded changes</h2>' + _comparison(excerpts) + "</section>",
        '<section id="history"><h2>Decisions on this job</h2><div class="table-wrap">'
        '<table><thead><tr><th>Decision</th><th>Stage</th><th>Outcome</th>'
        '<th>Attempt</th><th>Resulting revision</th></tr></thead><tbody>',
    ]
    for row in trace["attempts"]:
        sections.append("<tr>" + "".join(f"<td>{_text(row.get(key))}</td>" for key in (
            "decision_id", "stage", "outcome", "attempt", "resulting_revision_id",
        )) + "</tr>")
    sections += [
        "</tbody></table></div><p>Select another decision with --decision-id when exporting. "
        "Attempt counters can reset after revival.</p></section>",
        '<section id="inputs"><h2>Inputs and source locations</h2>'
        '<p>Inputs are the frozen application request. Provider-added instructions and transport '
        'settings are not captured here. A source location shows where input came from, '
        'not what caused a sentence.</p>',
    ]
    for stage in ("system", "prompt"):
        sections.append(f"<details><summary>{LABELS[stage]}</summary>" +
                        _preview(excerpts[stage]) + "</details>")
    sections += [_sources(trace["source_map"], excerpts), "</section>"]
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'">'
        f"<title>{_text(title)}</title><style>{_CSS}</style></head><body><main>" +
        "".join(sections) + "</main></body></html>\n"
    )


_CSS = """
:root { color-scheme:light dark; --bg:#f5f3ed; --ink:#242923; --panel:#fffefa;
        --rule:#ccd1c5; --accent:#315b46; --muted:#596256; }
* { box-sizing:border-box; } html { scroll-behavior:smooth; }
body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 system-ui,sans-serif; }
main { max-width:1280px; margin:auto; padding:40px 28px 80px; }
h1 { font:38px/1.2 Georgia,serif; margin-bottom:8px; } h2 { font:28px Georgia,serif; }
h3 { font-size:18px; } .intro,.muted { color:var(--muted); }
nav { display:flex; flex-wrap:wrap; gap:24px; margin:24px 0; }
a { color:var(--accent); text-underline-offset:4px; } a:focus-visible,summary:focus-visible
{ outline:3px solid var(--accent); outline-offset:4px; }
section { margin-top:32px; border-top:1px solid var(--rule); padding-top:8px; }
dl { display:grid; grid-template-columns:160px minmax(0,1fr); gap:6px 16px; font-size:14px; }
dt { color:var(--muted); } dd { margin:0; overflow-wrap:anywhere; }
.notice { border-left:3px solid var(--accent); padding:8px 16px; background:var(--panel); }
.columns { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:24px; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; font:15px/1.65 Georgia,serif;
      background:var(--panel); padding:20px; border:1px solid var(--rule); }
.diff { font:13px/1.65 ui-monospace,monospace; } .diff span { display:block; }
.added { background:#dceede; color:#173d20; } .removed { background:#f6dfdb; color:#672921; }
details { margin:12px 0; padding:12px 16px; border:1px solid var(--rule); }
summary { cursor:pointer; overflow-wrap:anywhere; } .table-wrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th,td { text-align:left; vertical-align:top; padding:10px; border-bottom:1px solid var(--rule); }
@media(max-width:760px) { main { padding:24px 16px; } .columns { grid-template-columns:1fr; }
                       dl { grid-template-columns:1fr; gap:2px; } dd { margin-bottom:8px; } }
@media(prefers-color-scheme:dark) { :root { --bg:#181e1b; --ink:#e8eae2; --panel:#212a24;
                                 --rule:#465249; --accent:#a1d0b1; --muted:#b7bfb2; } }
@media print { nav { display:none; } .columns { display:block; } }
"""
