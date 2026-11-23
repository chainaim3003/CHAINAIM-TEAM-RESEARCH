<#
.SYNOPSIS
    Weekly run (no AI): write the weekly digest kb/digests/<year>-W<week>.md.

.DESCRIPTION
    Runs scripts/digest.py: lists everything extracted in the last -Days days with links and
    whether a summary has been saved. Log: logs/<date>-weekly.log. Shares the run lock with
    run_nightly.ps1. Exit code: 0 OK, 1 failed, 2 skipped (another run active).

.PARAMETER KbDir  KB folder (default: config output.kb_dir)
.PARAMETER Days   Look-back window (default 7)
.PARAMETER Uv     Full path to uv.exe (default: found on PATH)
#>
[CmdletBinding()]
param([string]$KbDir, [int]$Days = 7, [string]$Uv)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_common.ps1")

$log = Start-RunLog "weekly"
Write-Log "=== weekly digest start (no AI) ==="
if (-not (Enter-RunLock)) { exit 2 }
$failed = $false
try {
    $uvExe = Resolve-Uv $Uv
    Set-Location -LiteralPath $script:PkgDir
    $a = @("run", "scripts/digest.py", "--config", "config.yaml", "--days", "$Days")
    if ($KbDir) { $a += @("--kb-dir", $KbDir) }
    if ((Invoke-Logged $uvExe $a) -ne 0) { $failed = $true }
}
catch {
    $failed = $true
    Write-Log ("ERROR: {0}" -f $_.Exception.Message)
}
finally {
    Exit-RunLock
    Write-Log ("=== weekly digest end: {0} === log: {1}" -f ($(if ($failed) { "FAILED" } else { "OK" })), $log)
}
if ($failed) { exit 1 } else { exit 0 }
