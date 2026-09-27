# move-ignored.ps1 - Phase B5 of the LitHarness rebuild (PLAN.md section 6 beside this file).
# ASCII only: Windows PowerShell 5.1 reads BOM-less UTF-8 as ANSI.
#
#   -Mode List     (default) print what would move, with bytes and file counts. Changes nothing.
#   -Mode Move     copy this script to the archive, record the plan once in MANIFEST.tsv, move each
#                  path to <Archive>\tree\<path> by a same-volume rename, then make the draw-6 junction.
#                  Re-runnable: a row is done when its destination exists and its source does not.
#   -Mode Reverse  remove the junction (cmd rmdir, never Remove-Item) and the empty parents it needed,
#                  then move every row back, last first. Re-runnable: a row is done when its source exists.
#   -Mode Backup   zip the generated books and the memory copy to OneDrive and record the sha256.
#
# Nothing is ever deleted. The manifest is append-only: planned rows once, then one line per move.
param(
    [ValidateSet('List', 'Move', 'Reverse', 'Backup')] [string] $Mode = 'List',
    [string] $Repo = 'C:\DEV\LitHarness',
    [string] $Archive = 'C:\DEV\LitHarness-archive'
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Manifest = Join-Path $Archive 'MANIFEST.tsv'
$Tree = Join-Path $Archive 'tree'
$Junction = 'runs\chapter-one\read-21\draw-6'
$NoBom = New-Object System.Text.UTF8Encoding $false
$Exemplars = @('PrimalHunter', 'DefianceOfTheFall', 'RandidlyGhosthound', 'TheGam3')

function Local-Path([string] $p) { return ($p.TrimEnd('/') -replace '/', '\') }

function Write-Row([string] $status, [string] $path, [string] $bytes, [string] $count, [string] $sha) {
    New-Item -ItemType Directory -Force $Archive | Out-Null
    $line = @($status, $path, $bytes, $count, $sha, (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')) -join "`t"
    [System.IO.File]::AppendAllText($Manifest, $line + "`r`n", $NoBom)
}

function Test-Keep([string] $p) {
    # Stays in place: the venv, test caches, ignored .claude entries, the box lock, every __pycache__ and *_cache.
    if ($p -match '^(\.venv|\.hypothesis|\.claude)(/|$)') { return $true }
    if ($p.TrimEnd('/') -eq 'runs/box.lock') { return $true }
    foreach ($part in $p.TrimEnd('/').Split('/')) {
        if ($part -eq '__pycache__' -or $part -like '*_cache') { return $true }
    }
    return $false
}

function Get-Rank([string] $p) {
    if ($p.StartsWith('research/')) { return 0 }
    if ($p.StartsWith('runs/')) { return 1 }
    if ($p.StartsWith('book-library')) { return 2 }
    if ($p -like 'litharness.db*') { return 3 }
    return 4
}

function Get-Plan {
    $raw = (& git -C $Repo ls-files --others --ignored --exclude-standard --directory -z) -join ''
    if ($LASTEXITCODE -ne 0) { throw 'git ls-files failed' }
    $paths = New-Object System.Collections.Generic.List[string]
    foreach ($p in $raw.Split([char]0)) {
        if (-not $p) { continue }
        if ($p -eq 'runs/') {
            foreach ($child in Get-ChildItem -Force -LiteralPath (Join-Path $Repo 'runs')) {
                $paths.Add('runs/' + $child.Name + $(if ($child.PSIsContainer) { '/' } else { '' }))
            }
        } else { $paths.Add($p) }
    }
    $dirs = @($paths | Where-Object { $_.EndsWith('/') })
    $moving = @($paths | Where-Object {
        $p = $_
        -not (Test-Keep $p) -and -not @($dirs | Where-Object { $_ -ne $p -and $p.StartsWith($_) }).Count
    })
    # A SQLite -wal or -shm travels in its database's row (Get-Members), so the two never split.
    $moving = @($moving | Where-Object { -not ($_ -match '\.db-(wal|shm)$' -and $moving -contains ($_ -replace '-(wal|shm)$', '')) })
    return @($moving | Sort-Object @{ Expression = { Get-Rank $_ } }, @{ Expression = { $_ } })
}

function Get-Members([string] $p) {
    if ($p -like '*.db') { return @($p, "$p-wal", "$p-shm") }
    return @($p)
}

function Measure-Row([string] $p) {
    $full = Join-Path $Repo (Local-Path $p)
    $item = Get-Item -Force -LiteralPath $full
    if (-not $item.PSIsContainer) {
        $sha = if ($p -like '*.db*') { (Get-FileHash -Algorithm SHA256 -LiteralPath $full).Hash } else { '' }
        return @($item.Length, 1, $sha)
    }
    $files = @(Get-ChildItem -Force -Recurse -File -LiteralPath $full -ErrorAction SilentlyContinue)
    return @([int64](($files | Measure-Object -Sum Length).Sum), $files.Count, '')
}

function Get-Planned {
    if (-not (Test-Path -LiteralPath $Manifest)) { return @() }
    return @(Get-Content -LiteralPath $Manifest -Encoding UTF8 | Where-Object { $_.StartsWith("planned`t") } |
        ForEach-Object { $_.Split("`t")[1] })
}

switch ($Mode) {
    'List' {
        $total = [int64]0
        foreach ($p in Get-Plan) {
            $m = Measure-Row $p
            $total += $m[0]
            '{0,12:N0} {1,8} {2}' -f $m[0], $m[1], $p
        }
        '{0,12:N0} bytes in all; keep in place: .venv/, .hypothesis/, .claude/, runs/box.lock, __pycache__/, *_cache/' -f $total
    }
    'Move' {
        New-Item -ItemType Directory -Force $Archive | Out-Null
        $copy = Join-Path $Archive 'move-ignored.ps1'
        if (-not (Test-Path -LiteralPath $copy)) { Copy-Item -LiteralPath $PSCommandPath -Destination $copy }
        $plan = @(Get-Planned)
        if (-not $plan.Count) {
            $plan = Get-Plan
            foreach ($p in $plan) { $m = Measure-Row $p; Write-Row 'planned' $p $m[0] $m[1] $m[2] }
        }
        foreach ($q in @($plan | ForEach-Object { Get-Members $_ })) {
            $src = Join-Path $Repo (Local-Path $q)
            $dst = Join-Path $Tree (Local-Path $q)
            $hasSrc = Test-Path -LiteralPath $src
            $hasDst = Test-Path -LiteralPath $dst
            # Done: moved earlier. The junction's parents exist again once it is made, so those rows are done too.
            if ($hasDst -and (-not $hasSrc -or $Junction.StartsWith((Local-Path $q) + '\'))) { continue }
            if ($hasDst) { throw "exists: $dst" }
            if (-not $hasSrc) { if ($q -match '\.db-(wal|shm)$') { continue }; throw "missing: $src" }
            New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
            Move-Item -LiteralPath $src -Destination $dst -ErrorAction Stop
            Write-Row 'moved' $q '' '' ''
            "moved $q"
        }
        $link = Join-Path $Repo $Junction
        if (-not (Test-Path -LiteralPath $link)) {
            New-Item -ItemType Directory -Force (Split-Path $link) | Out-Null
            New-Item -ItemType Junction -Path $link -Target (Join-Path $Tree $Junction) | Out-Null
            Write-Row 'junction' ($Junction -replace '\\', '/') '' '' ''
        }
    }
    'Reverse' {
        $link = Join-Path $Repo $Junction
        if (Test-Path -LiteralPath $link) {
            cmd /c rmdir "$link"
            foreach ($parent in @('runs\chapter-one\read-21', 'runs\chapter-one')) {
                $dir = Join-Path $Repo $parent
                if ((Test-Path -LiteralPath $dir) -and -not @(Get-ChildItem -Force -LiteralPath $dir).Count) { cmd /c rmdir "$dir" }
            }
        }
        $plan = @(Get-Planned | ForEach-Object { Get-Members $_ })
        [array]::Reverse($plan)
        foreach ($q in $plan) {
            $src = Join-Path $Repo (Local-Path $q)
            $dst = Join-Path $Tree (Local-Path $q)
            if (Test-Path -LiteralPath $src) { continue }
            if (-not (Test-Path -LiteralPath $dst)) { if ($q -match '\.db-(wal|shm)$') { continue }; throw "missing in the archive: $dst" }
            New-Item -ItemType Directory -Force (Split-Path $src) | Out-Null
            Move-Item -LiteralPath $dst -Destination $src -ErrorAction Stop
            Write-Row 'returned' $q '' '' ''
            "returned $q"
        }
    }
    'Backup' {
        $zip = Join-Path $env:OneDrive 'LitHarness-backups\2026-09-27-books.zip'
        if (Test-Path -LiteralPath $zip) { throw "exists: $zip" }
        New-Item -ItemType Directory -Force (Split-Path $zip) | Out-Null
        $items = @('runs\chapter-one', 'runs\volume1', 'runs\full-book-trial-20260919', 'litharness.db',
                   'litharness.db-shm', 'litharness.db-wal') | ForEach-Object { Join-Path $Tree $_ }
        $items += @(Get-ChildItem -Force -LiteralPath (Join-Path $Tree 'book-library') |
                    Where-Object { $Exemplars -notcontains $_.Name } | ForEach-Object { $_.FullName })
        $items += @(Join-Path $Archive 'memory-2026-09-27')
        $present = @($items | Where-Object { Test-Path -LiteralPath $_ })
        @($items | Where-Object { -not (Test-Path -LiteralPath $_) }) | ForEach-Object { "not found, skipped: $_" }
        Compress-Archive -LiteralPath $present -DestinationPath $zip
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash
        Write-Row 'backup' $zip (Get-Item -LiteralPath $zip).Length $present.Count $hash
        "backup $zip $hash"
    }
}
