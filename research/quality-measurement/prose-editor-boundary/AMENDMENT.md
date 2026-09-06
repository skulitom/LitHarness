# Dispatch amendment after the first Claude response

2026-09-06, after selector, Codex full-1 and Claude full-1; no subsequent calls dispatched.
The original registration and runner remain unchanged. Claude exited successfully, with a
single turn, no tools, no permission denials and an Opus 5 prose result, but modelUsage also
reports an auxiliary Haiku 4.5 request (4314 input, 15 output tokens). The strict single-model
parser rejected this and stopped globally as registered. Its origin and influence are not
established by the result; subagent_stats reports zero spawned agents. Do not call it a
second drafting agent, assume it was harmless, or hide it in the primary model's accounting.

Recover the existing raw response offline into a separate recovered.json; preserve raw.json,
request.json and the failed result.json bytes. Verify the assistant messages are Opus 5 only,
no tool content, one successful result and consistent main-model usage. Require and sum every
modelUsage row, including input, cache reads/creation and output. Main output already contains
thinking tokens; do not count those twice. Report the primary writer and unexpected auxiliary
model separately. Recovered prose is retained for reading, not a successful contained D draw.

Do not run the remaining three Claude requests, retry the first or introduce a replacement
provider. D remains incomplete: one contaminated Claude observation and the four shared Codex
controls, with no claimed model comparison result. A, B and C retain their exact registered
systems, inputs, order relative to one another, sample sizes and analysis rules. The next
call is Codex static-1. Maximum actual CLI invocations is now 20; retain the original 23-slot
schedule with explicit skipped records. Count the recovered Claude primary plus auxiliary
usage toward the same 300000-token global dispatch stop.

A source-free resume wrapper validates the original frozen manifest, the unchanged failed
record and raw response, and separately freezes this amendment, its recovery code and recovered
artifact before more calls. The original complete function handles all new Codex requests.
No prompts or source units are changed after seeing prose. Run handoff and commit this amendment
and its accounting regression tests before resuming. Keep all development and execution failures
in the final history. This amendment enables independent diagnostics; it does not retroactively
make the failed Claude containment check pass.

After the amendment commit, without editing the original frozen inputs:

```powershell
uv run python research/quality-measurement/prose_editor_boundary_resume.py prepare --out runs/ab/prose-editor-boundary-20260906
uv run python research/quality-measurement/prose_editor_boundary_resume.py run --out runs/ab/prose-editor-boundary-20260906
```
