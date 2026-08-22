<#
.SYNOPSIS
    Stand up Serial Pilot 2 on a forged world, up to but not including the first drafted word.

.DESCRIPTION
    `tools/serial-pilot-setup.ps1` is the same script for Serial Pilot 1, and the difference
    between them is the whole point of the Architect: pilot 1's seed and directives were typed
    by the operator into `plan/serial-pilot-seed.json`, and pilot 2's are produced by
    `litharness forge` and chosen by a person from K candidates.

    Three phases, and the middle one is a human being.

      1. `forge` builds K worlds in ONE structured call, gates them deterministically, and
         stops. No model orders them.
      2. The operator reads the report and runs `forge --pick <n>`. That is the only judgment
         in this pipeline and it is recorded as its own policy decision.
      3. This script takes the chosen bundle and stands the book up: `new --state --promises`,
         then the world's own directives, then the standing craft constraints.

    **The craft constraints are not the world's.** `plan/serial-pilot-2-craft.json` carries C3
    and C5-C8 from pilot 1 — four verbatim, two with a recorded edit where their wording named
    Reappraisal's own nouns. They came from a human read of real prose and they belong to the
    project. The world's directives come out of the forge and are stamped `architect:`.

    **The database must not already exist**, for `serial-pilot-setup.ps1`'s reason:
    `planner._resolved_directive_scope` materialises an unscoped directive only when exactly one
    branch matches it, so a second book in this store would silently strand every directive.

    Afterwards, run the loop (the command is printed at the end), then the gate:

        uv run python tools/serial_pilot_check.py --database serial2.db

.PARAMETER Database
    The store to create. Defaults to serial2.db beside this repository.

.PARAMETER Forge
    The directory a `litharness forge` wrote. Must already hold seed.json, directives.json and
    promises.json — that is, `forge --pick` must already have been run.

.PARAMETER Craft
    The standing craft constraints. Defaults to plan/serial-pilot-2-craft.json.

.PARAMETER Scenes
    How many scenes the book gets. Two chapters of four is the shape §101.2 recommends.

.EXAMPLE
    .\tools\serial-pilot-2-setup.ps1 -Forge pilot2\direct
#>
[CmdletBinding()]
param(
    [string] $Database,
    [string] $Forge,
    [string] $Craft,
    [int]    $Scenes = 8
)

$ErrorActionPreference = 'Stop'

$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repo = (Resolve-Path (Join-Path $here '..')).Path
if (-not $Database) { $Database = Join-Path $repo 'serial2.db' }
if (-not $Craft)    { $Craft    = Join-Path $repo 'plan\serial-pilot-2-craft.json' }

function Fail([string] $message) {
    Write-Host "setup: REFUSED - $message" -ForegroundColor Red
    exit 1
}

# -- preconditions, each one a way the run goes wrong quietly ------------------------------

if (-not $Forge) {
    Fail "-Forge is required. Run: litharness --database <db> forge '<brief>' --k 3 --out <dir>, read the report, then forge --out <dir> --pick <n>."
}
if (Test-Path $Database) {
    Fail "$Database already exists. A second book in one store makes every unscoped directive ambiguous, and the planner then materialises none of them. Move it aside or pass -Database."
}
$seed       = Join-Path $Forge 'seed.json'
$directives = Join-Path $Forge 'directives.json'
$promises   = Join-Path $Forge 'promises.json'
foreach ($path in @($seed, $directives, $promises, $Craft)) {
    if (-not (Test-Path $path)) {
        Fail "$path is missing. Run `litharness forge --out $Forge --pick <n>` first; that is the operator's choice among the forged worlds and nothing downstream may make it."
    }
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

$world = Get-Content -Raw -Encoding UTF8 $directives | ConvertFrom-Json
$craftSet = Get-Content -Raw -Encoding UTF8 $Craft | ConvertFrom-Json
$expected = $world.directives.Count + $craftSet.directives.Count
if ($expected -lt 1) { Fail "$directives and $Craft between them hold no directives." }

Write-Host "setup: $Database"
Write-Host "setup: $($world.title), $Scenes scene(s)"
Write-Host "setup: $($world.directives.Count) forged directive(s) + $($craftSet.directives.Count) standing craft constraint(s) = $expected"
Write-Host ""

Push-Location $repo
try {
    Write-Host "setup: init" -ForegroundColor Cyan
    uv run litharness --database $Database init
    if ($LASTEXITCODE -ne 0) { Fail "init exited $LASTEXITCODE" }

    Write-Host ""
    Write-Host "setup: new (seed and promises both come from the forge)" -ForegroundColor Cyan
    uv run litharness --database $Database new $world.title `
        --premise $world.premise --scenes $Scenes --state $seed --promises $promises
    if ($LASTEXITCODE -ne 0) { Fail "new exited $LASTEXITCODE" }

    Write-Host ""
    Write-Host "setup: state (expect the forged world's records)" -ForegroundColor Cyan
    uv run litharness --database $Database state
    if ($LASTEXITCODE -ne 0) { Fail "state exited $LASTEXITCODE" }

    # -- the directives ---------------------------------------------------------------------
    #
    # The world's own first, then the standing craft constraints, for `serial-pilot-setup.ps1`'s
    # reason: `directive_id_for` keys on (kind, body, received_at), so the same words submitted
    # twice in the same second collapse to one row. Issuing them in one ordered pass keeps that
    # property useful rather than surprising.

    Write-Host ""
    Write-Host "setup: directives from the forged world" -ForegroundColor Cyan
    foreach ($directive in $world.directives) {
        uv run litharness --database $Database directive $directive.text --kind $directive.kind
        if ($LASTEXITCODE -ne 0) { Fail "directive '$($directive.label)' exited $LASTEXITCODE" }
        Write-Host "        ^ $($directive.label)"
    }

    Write-Host ""
    Write-Host "setup: standing craft constraints" -ForegroundColor Cyan
    foreach ($directive in $craftSet.directives) {
        uv run litharness --database $Database directive $directive.text --kind $directive.kind
        if ($LASTEXITCODE -ne 0) { Fail "directive '$($directive.label)' exited $LASTEXITCODE" }
        Write-Host "        ^ $($directive.label) [$($directive.carried)]"
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
Write-Host "Next, in two phases. Phase 1 lands the direction (no prose):"
Write-Host ""
Write-Host "  .\tools\run-loop.ps1 -Database $Database -Ticks 14 -DelaySeconds 2 ``"
Write-Host "    -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'"
Write-Host "  uv run python tools/serial_pilot_check.py --database $Database --phase directives"
Write-Host ""
Write-Host "Only when that gate is green, phase 2 writes the $Scenes scenes:"
Write-Host ""
Write-Host "  .\tools\run-loop.ps1 -Database $Database -Ticks 48 -DelaySeconds 2 ``"
Write-Host "    -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'"
Write-Host "  uv run python tools/serial_pilot_check.py --database $Database"
Write-Host ""
Write-Host "TickArgs must be a comma-separated array. One quoted string binds as a single"
Write-Host "argv token and argparse refuses it - the form printed in the package fails."
