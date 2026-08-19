<#
.SYNOPSIS
    Register a Windows Scheduled Task that republishes the library every few hours.

.DESCRIPTION
    **Read this before installing it, because you probably do not need it.** Every tick already
    republishes the library, and a book whose head has not moved is skipped — so while
    `tools\run-loop.ps1` is running, the folder is exactly as fresh as the book, which is
    strictly better than any wall-clock cadence. A schedule can only make it staler.

    What this is for is the case the loop does not cover: the loop is off, and you still want
    the folder rebuilt on a clock — after a manual import, say, or so a rendering change lands
    without anyone remembering to run the command.

    **It schedules `library` and never `tick`, and the distinction is load-bearing.** stage-0
    §63 removed the cron deployment along with the instance lease that made overlapping
    invocations safe: "leader election among overlapping invocations; one process has nobody to
    lose the claim to". A scheduled `tick` firing beside a running loop is exactly the
    overlapping-invocation case that lease used to cover, and it no longer exists. `library` is
    read-only against the store — it takes no lease, claims no job, and mutates nothing — so it
    is safe to fire whenever, including alongside a running loop.

    Nothing happens without -Install. Run it bare to see what it would register.

.PARAMETER Database
    The store to publish. Defaults to bz3.db beside this repository.

.PARAMETER EveryHours
    Repeat interval. Three by default, which is "every few hours" read literally.

.PARAMETER TaskName
    The Scheduled Task name. Named so it is findable in taskschd.msc.

.PARAMETER Install
    Actually register it. Without this the script prints the plan and exits.

.PARAMETER Uninstall
    Remove a previously registered task.

.EXAMPLE
    .\tools\schedule-library.ps1
.EXAMPLE
    .\tools\schedule-library.ps1 -EveryHours 3 -Install
.EXAMPLE
    .\tools\schedule-library.ps1 -Uninstall

.NOTES
    On a Unix host the same thing is one crontab line and needs no script:
        0 */3 * * * cd /path/to/LitHarness && uv run litharness --database bz3.db library
#>
[CmdletBinding()]
param(
    [string] $Database,
    [int]    $EveryHours = 3,
    [string] $TaskName = 'LitHarness book-library',
    [switch] $Install,
    [switch] $Uninstall
)

$ErrorActionPreference = 'Stop'

# $PSScriptRoot is empty during parameter binding when the script is invoked by a relative
# path, which is exactly how somebody runs it from the repository root. Resolved here in the
# body instead, with the invocation path as the fallback that always works.
$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repo = (Resolve-Path (Join-Path $here '..')).Path
if (-not $Database) { $Database = Join-Path $repo 'bz3.db' }

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "removed scheduled task: $TaskName"
    return
}

$command = "uv run litharness --database `"$Database`" library"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -WindowStyle Hidden -Command `"$command`"" `
    -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
    -RepetitionInterval (New-TimeSpan -Hours $EveryHours)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Write-Host "task      : $TaskName"
Write-Host "runs      : $command"
Write-Host "in        : $repo"
Write-Host "every     : $EveryHours hour(s), starting two minutes from now"
Write-Host "writes to : $(Join-Path (Split-Path -Parent $Database) 'book-library')"

if (-not $Install) {
    Write-Host ''
    Write-Host 'Nothing registered. Re-run with -Install to register it.'
    Write-Host 'Consider whether you need it: a running tick loop keeps the library fresher'
    Write-Host 'than any schedule can, because it publishes when the book actually changes.'
    return
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description (
        'Republish the LitHarness book-library. Read-only against the store: takes no job ' +
        'lease and mutates nothing, so it is safe beside a running tick loop.'
    ) -Force | Out-Null
Write-Host ''
Write-Host "registered. Remove it with: .\tools\schedule-library.ps1 -Uninstall"
