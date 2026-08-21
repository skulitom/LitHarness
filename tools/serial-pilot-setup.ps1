<#
.SYNOPSIS
    Stand up Serial Pilot 1 ("Reappraisal") up to, but not including, the first drafted word.

.DESCRIPTION
    `plan/serial-pilot-1.md` §3 is a list of commands to retype. This is that list, run once,
    with the preconditions checked first and the postconditions checked after. It creates the
    store, the book, the seed canon and the eight directives. It draws no prose and makes no
    provider call: every step here is a local store write.

    **The directive texts are not in this file, and that is the point.** They are read from
    `plan/serial-pilot-directives.json`, which was extracted verbatim from §1 and §4 of the
    package rather than retyped. Two failures are closed by that: a transcription drift
    between the plan and the store, and PowerShell 5.1 parsing a .ps1 without a BOM as
    Windows-1252 — which would turn every em dash in C2 into three characters and break the
    exact form `STATUS_TEMPLATE` matches on. This file is ASCII; the text with the em dashes
    is read from UTF-8 with the encoding named.

    **The database must not already exist.** `planner._resolved_directive_scope` materialises
    an unscoped directive only when exactly one branch matches it, so a second book in this
    store would silently strand every directive §4 issues without `--book`.

    Afterwards, run the loop (the command is printed at the end), then the gate:

        uv run python tools/serial_pilot_check.py --database serial.db

.PARAMETER Database
    The store to create. Defaults to serial.db beside this repository.

.PARAMETER Spec
    The extracted premise and directive set. Defaults to plan/serial-pilot-directives.json.

.PARAMETER Seed
    The StateSnapshot to seed canon with. Defaults to plan/serial-pilot-seed.json.

.EXAMPLE
    .\tools\serial-pilot-setup.ps1
#>
[CmdletBinding()]
param(
    [string] $Database,
    [string] $Spec,
    [string] $Seed
)

$ErrorActionPreference = 'Stop'

$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repo = (Resolve-Path (Join-Path $here '..')).Path
if (-not $Database) { $Database = Join-Path $repo 'serial.db' }
if (-not $Spec)     { $Spec     = Join-Path $repo 'plan\serial-pilot-directives.json' }
if (-not $Seed)     { $Seed     = Join-Path $repo 'plan\serial-pilot-seed.json' }

function Fail([string] $message) {
    Write-Host "setup: REFUSED - $message" -ForegroundColor Red
    exit 1
}

# -- preconditions, each one a way the run goes wrong quietly ------------------------------

if (Test-Path $Database) {
    Fail "$Database already exists. A second book in one store makes every unscoped directive ambiguous, and the planner then materialises none of them. Move it aside or pass -Database."
}
foreach ($path in @($Spec, $Seed)) {
    if (-not (Test-Path $path)) { Fail "$path is missing" }
}
if ($env:LITHARNESS_ENV -eq 'test') {
    Fail "LITHARNESS_ENV=test. The pinned registry refuses to resolve a billing provider in test mode, so the loop would park every unit. Clear it."
}
if ($env:LITHARNESS_FAKE_PAD_CHARS) {
    Fail "LITHARNESS_FAKE_PAD_CHARS is set. That selects the deterministic fake, and the book would be written in filler. Clear it."
}
foreach ($name in @('LITHARNESS_NO_OUTLINE', 'LITHARNESS_PLAN_SEARCH', 'LITHARNESS_DIRECTOR', 'LITHARNESS_NO_LIBRARY')) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($value) { Write-Host "setup: note - $name=$value is set and will change the run" -ForegroundColor Yellow }
}
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Fail "the claude CLI is not on PATH. It is the pinned provider; without it every unit requeues forever."
}

$pilot = Get-Content -Raw -Encoding UTF8 $Spec | ConvertFrom-Json
# The count comes from the spec, which is extracted from the package -- hardcoding it here
# would be one more number somebody has to remember to change, which is the defect class this
# whole run kept finding.
$expected = $pilot.directives.Count
if ($expected -lt 1) {
    Fail "$Spec holds no directives; re-extract it from plan/serial-pilot-1.md."
}

Write-Host "setup: $Database"
Write-Host "setup: $($pilot.title), $($pilot.scenes) scene(s), $($pilot.directives.Count) directive(s)"
Write-Host ""

# -- the store, the book, the seed ---------------------------------------------------------

Push-Location $repo
try {
    Write-Host "setup: init" -ForegroundColor Cyan
    uv run litharness --database $Database init
    if ($LASTEXITCODE -ne 0) { Fail "init exited $LASTEXITCODE" }

    Write-Host ""
    Write-Host "setup: new" -ForegroundColor Cyan
    uv run litharness --database $Database new $pilot.title `
        --premise $pilot.premise --scenes $pilot.scenes --state $Seed
    if ($LASTEXITCODE -ne 0) { Fail "new exited $LASTEXITCODE" }

    Write-Host ""
    Write-Host "setup: state (expect the seed records, subject silas among them)" -ForegroundColor Cyan
    uv run litharness --database $Database state
    if ($LASTEXITCODE -ne 0) { Fail "state exited $LASTEXITCODE" }

    # -- the directives, in §4 order -------------------------------------------------------
    #
    # Order is not decoration: `directive_id_for` keys on (kind, body, received_at), so the
    # same words submitted twice in the same second collapse to one row rather than queueing
    # two readings. Issuing them in one pass keeps that property useful rather than surprising.

    Write-Host ""
    Write-Host "setup: directives" -ForegroundColor Cyan
    foreach ($directive in $pilot.directives) {
        uv run litharness --database $Database directive $directive.text --kind $directive.kind
        if ($LASTEXITCODE -ne 0) { Fail "directive '$($directive.label)' exited $LASTEXITCODE" }
        Write-Host "        ^ $($directive.label)"
    }
}
finally {
    Pop-Location
}

# -- postconditions ------------------------------------------------------------------------

Write-Host ""
Write-Host "setup: verifying what landed" -ForegroundColor Cyan
Push-Location $repo
try {
    $listed = uv run litharness --database $Database directives 2>&1
    $listed | Select-Object -Last 1 | ForEach-Object { Write-Host "        $_" }
    if (($listed -join "`n") -notmatch "\($expected received") {
        Fail "the inbox does not hold $expected received directives. Nothing has been drafted; inspect with ``litharness --database $Database directives``."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "setup: done. Nothing has been drafted." -ForegroundColor Green
Write-Host ""
Write-Host "Next, in two phases. Phase 1 lands the direction (about 9 ticks, no prose):"
Write-Host ""
Write-Host "  .\tools\run-loop.ps1 -Database $Database -Ticks 12 -DelaySeconds 2 ``"
Write-Host "    -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'"
Write-Host "  uv run python tools/serial_pilot_check.py --database $Database --phase directives"
Write-Host ""
Write-Host "Only when that gate is green, phase 2 writes the eight scenes:"
Write-Host ""
Write-Host "  .\tools\run-loop.ps1 -Database $Database -Ticks 48 -DelaySeconds 2 ``"
Write-Host "    -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'"
Write-Host "  uv run python tools/serial_pilot_check.py --database $Database"
Write-Host ""
Write-Host "TickArgs must be a comma-separated array. One quoted string binds as a single"
Write-Host "argv token and argparse refuses it - the form printed in the package fails."
