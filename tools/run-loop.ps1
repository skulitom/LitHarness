<#
.SYNOPSIS
    The operating model: one process running `litharness tick` in a loop.

.DESCRIPTION
    stage-0 §63 cut the cron deployment — leader election, durable pause, the outbox delivery
    path, status-as-external-monitor, net −1,103 lines — and stated what replaced it in one
    sentence: "One process runs `litharness tick` in a loop (or a shell loop does); killing it
    mid-job loses nothing." This script is that shell loop, written down so it is the same loop
    every time rather than a command somebody retypes.

    **It is also the answer to "publish the library every few hours".** Every tick republishes
    the library, and a book whose head has not moved is skipped, so the folder is exactly as
    fresh as the book at all times rather than as fresh as the last scheduled run. A separate
    schedule can only make it staler than this does.

    Killing it is safe at any point. The job lease is reclaimed, a replayed tick converges on
    its recorded decision, and accepted work was committed atomically with its events.

.PARAMETER Database
    The store to work. Defaults to runs/litharness.db so an ordinary run does not create
    database files at the repository root.

.PARAMETER DelaySeconds
    Wait between ticks. A pause rather than a rate limit: it keeps an idle loop from spinning
    on NO_WORK and leaves room for a provider that is rate-limiting.

.PARAMETER Ticks
    Stop after this many ticks. 0 runs until interrupted.

.PARAMETER TickArgs
    Anything else to pass through — `--plan-search`, `--director delver`, `--no-library`.

.EXAMPLE
    .\tools\run-loop.ps1
.EXAMPLE
    .\tools\run-loop.ps1 -DelaySeconds 30 -TickArgs '--plan-search','--director','delver'
#>
[CmdletBinding()]
param(
    [string] $Database,
    [int]    $DelaySeconds = 15,
    [int]    $Ticks = 0,
    [string[]] $TickArgs = @()
)

$ErrorActionPreference = 'Stop'

# $PSScriptRoot is empty during parameter binding when the script is invoked by a relative
# path, which is exactly how somebody runs it from the repository root. Resolved here in the
# body instead, with the invocation path as the fallback that always works.
$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repo = (Resolve-Path (Join-Path $here '..')).Path
if (-not $Database) {
    $runRoot = Join-Path $repo 'runs'
    New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
    $Database = Join-Path $runRoot 'litharness.db'
}
$store = $Database

Write-Host "loop: $store"
Write-Host "loop: delay ${DelaySeconds}s, $(if ($Ticks) { "$Ticks tick(s)" } else { 'until interrupted' })"
Write-Host "loop: Ctrl+C is the pause; a killed tick is reclaimed and replayed (§63)"

$count = 0
$idle = 0
while ($true) {
    Push-Location $repo
    try {
        $output = & uv run litharness --database $store @TickArgs tick 2>&1
    } finally {
        Pop-Location
    }
    $output | ForEach-Object { Write-Host $_ }

    # NO_WORK is the ordinary idle state and exits 0; a parked unit exits 1 and is somebody's
    # problem eventually, not the loop's. Neither is a reason to stop — §4.1: a blocked or
    # parked item never stalls the queue, the Conductor works elsewhere in the book.
    if ($output -match 'no_work') { $idle++ } else { $idle = 0 }
    if ($idle -eq 1) { Write-Host "loop: idle - nothing claimable, still watching" }

    $count++
    if ($Ticks -gt 0 -and $count -ge $Ticks) { break }
    Start-Sleep -Seconds $DelaySeconds
}
Write-Host "loop: stopped after $count tick(s)"
