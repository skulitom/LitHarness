# Security Policy

## Reporting a Vulnerability

Please report vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/skulitom/LitHarness/security/advisories/new)
("Report a vulnerability" under the repository's **Security** tab). Do not open
a public issue for a security problem.

Include what you can of: the affected file or module, steps to reproduce, and
the impact you believe it has. You should receive an acknowledgement within a
few days.

## Scope

LitHarness is a research harness that drives paid LLM providers and writes to
local SQLite databases. Reports we care most about:

- **Credential exposure** — API keys, tokens, or subscription state leaking
  into committed files, logs, run artifacts, or exported books.
- **Prompt-injection paths** — untrusted text (corpus content, reader output,
  web material) reaching a provider call in a role that can direct spend or
  overwrite project state.
- **Dependency and supply-chain issues** in `pyproject.toml` / `uv.lock`.
- **Unsafe file handling** — path traversal or overwrite bugs in the export,
  migration, or run-artifact paths.

Out of scope: the quality of generated prose, research findings, and issues in
the upstream `claude` CLI or provider APIs themselves (report those to their
vendors).

## Supported Versions

Only the tip of `main` is supported. There are no maintained release branches.
