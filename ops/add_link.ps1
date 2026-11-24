<#
.SYNOPSIS
    Add one or more links (YouTube, GitHub, arXiv, web article) and process them now (no AI).

.DESCRIPTION
    1. Appends each link to the link list (default: <repo>\Transcript\links.txt), skipping links
       that are already in the file.
    2. Runs scripts/orchestrate.py on that list only (already-done items are skipped by dedupe).
    3. Runs scripts/build_kb_pack.py so prompts and kb/INDEX.md are up to date.
    Uses the same lock and logs as the scheduled runs (logs/<date>-addlink.log).
    Used by the VS Code task "Research: add link" (.vscode/tasks.json).
    Exit code: 0 OK, 1 a step failed, 2 skipped (another run is active), 3 no link given.

.PARAMETER Link        One or more links; several may be separated by spaces or commas.
.PARAMETER KbDir       KB folder (default: <repo>\Transcript)
.PARAMETER SourceList  Link list file (default: <KbDir>\links.txt)
.PARAMETER Uv          Full path to uv.exe (default: found on PATH)

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File ops\add_link.ps1 -Link "https://arxiv.org/abs/1706.03762"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string[]]$Link,
    [string]$KbDir, [string]$SourceList, [string]$Uv
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_common.ps1")

if (-not $KbDir) { $KbDir = Join-Path $script:RepoRoot "Transcript" }
if (-not $SourceList) { $SourceList = Join-Path $KbDir "links.txt" }
$noDir = Join-Path $KbDir "no-such-dir"   # keeps this run to the link list only

$links = @($Link | ForEach-Object { $_ -split "[,\s]+" } | Where-Object { $_ -match "^\S+$" -and $_.Trim() })
$log = Start-RunLog "addlink"
Write-Log "=== add link start (no AI) ==="
if ($links.Count -eq 0) { Write-Log "No link given."; exit 3 }
if (-not (Enter-RunLock)) { exit 2 }
$failed = $false
try {
    if (-not (Test-Path -LiteralPath $KbDir)) { New-Item -ItemType Directory -Path $KbDir | Out-Null }
    $existing = @()
    if (Test-Path -LiteralPath $SourceList) { $existing = @(Get-Content -LiteralPath $SourceList -Encoding UTF8) }
    foreach ($l in $links) {
        if ($existing -contains $l) { Write-Log "already in list: $l" }
        else { Add-Content -LiteralPath $SourceList -Value $l -Encoding UTF8; Write-Log "added: $l" }
    }
    $uvExe = Resolve-Uv $Uv
    Set-Location -LiteralPath $script:PkgDir
    $orch = @("run", "scripts/orchestrate.py", "--config", "config.yaml", "--kb-dir", $KbDir,
              "--source-list", $SourceList, "--source-dir", $noDir)
    if ((Invoke-Logged $uvExe $orch) -ne 0) { $failed = $true; Write-Log "some items failed (see above)." }
    if ((Invoke-Logged $uvExe @("run", "scripts/build_kb_pack.py", "--config", "config.yaml", "--kb-dir", $KbDir)) -ne 0) { $failed = $true }
    Write-Log ("Files: {0}" -f (Join-Path $KbDir "kb"))
}
catch {
    $failed = $true
    Write-Log ("ERROR: {0}" -f $_.Exception.Message)
}
finally {
    Exit-RunLock
    Write-Log ("=== add link end: {0} === log: {1}" -f ($(if ($failed) { "FAILED" } else { "OK" })), $log)
}
if ($failed) { exit 1 } else { exit 0 }
