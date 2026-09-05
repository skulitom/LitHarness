# Startup-notice parsing correction, before invocation 2

The first invocation exited zero and returned one complete prose message, one completed turn,
and token usage. No tool started or completed. The original parser nevertheless rejected it:
Codex emitted two pre-turn `item.completed` records typed `error`, one announcing the enabled
host-skill-discovery suppression and one announcing unavailable Code Mode with its host
deliberately disabled. They were startup diagnostics, not model tool activity. The separate
stderr warning says PowerShell shell snapshots are unsupported. All records remain retained.

This amendment changes only local event classification. Before the next invocation, add an
allowlist for the exact two notice forms, and only before `turn.started`. Every other error,
tool start/completion, multiple/empty prose output or invalid usage still fails. Preserve the
notice messages in the parsed result. Tests must reject even a recognized notice during the
turn, and must continue rejecting actual error/tool events.

Reparse the already-paid raw output locally; do not regenerate it. Preserve original failed
validation, original manifest and original runner bytes under versioned local filenames. Record
the old and new identities and the amendment hash before continuing. The manifest's source
requests, source system file and argv remain byte-identical. Update only runner/commit identity
and add this amendment to its frozen files. Invocation 1 continues to count toward the original
four-invocation and 120000-token limits. Resume at invocation 2, using the amended parser; no
model request, model, effort, input selection, prompt, CLI option or timeout changes.

The complete first draft was visible when diagnosing the parser failure. This is not a blind
amendment. No prose-quality criterion determines its recovery or the following inputs, and its
raw text and usage cannot be edited. The first invocation's original validation outcome must
remain visible in the final execution record. No quality or efficacy claim follows.
