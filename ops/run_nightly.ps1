<#
.SYNOPSIS
    Nightly run (no AI): collect new links -> transcripts / GitHub extracts -> prompts + INDEX.md.

.DESCRIPTION
    1. scripts/orchestrate.py  - extracts every NEW YouTube / GitHub link (dedupe skips done ones)
    2. scripts/build_kb_pack.py - writes ready-to-paste prompts + kb/INDEX.md
    Output goes to the KB folder (config output.kb_dir, or -KbDir). A log is written to
    logs/<date>-nightly.log. A lock (pipeline.lock) prevents overlapping runs.
    Exit code: 0 = all good, 1 = a step failed (see log), 2 = skipped (another run active).

.PARAMETER KbDir       KB folder (default: config output.kb_dir). Example: ..\Transcript
.PARAMETER SourceList  Link list file (default: config input.source_list)
.PARAMETER SourceDir   Folder of *.txt/*.md link files (default: config input.source_dir)
.PARAMETER MaxItems    Cap on new items per run (default: no cap)
.PARAMETER Uv          Full path to uv.exe (default: found on PATH)

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File ops\run_nightly.ps1 -KbDir "C:\...\CHAINAIM-TEAM-RESEARCH\Transcript" -SourceList "C:\...\Transcript\links.txt" -SourceDir "C:\...\Transcript\no-such-dir"
#>
[CmdletBinding()]
param(
    [string]$KbDir, [string]$SourceList, [string]$SourceDir,
    [int]$MaxItems = 0, [string]$Uv
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_common.ps1")

$log = Start-RunLog "nightly"
Write-Log "=== nightly run start (no AI) ==="
if (-not (Enter-RunLock)) { exit 2 }
$failed = $false
try {
    $uvExe = Resolve-Uv $Uv
    Set-Location -LiteralPath $script:PkgDir
    $pathArgs = Get-PathArgs $KbDir $SourceList $SourceDir
    $orch = @("run", "scripts/orchestrate.py", "--config", "config.yaml") + $pathArgs
    if ($MaxItems -gt 0) { $orch += @("--max-videos", "$MaxItems") }
    if ((Invoke-Logged $uvExe $orch) -ne 0) { $failed = $true; Write-Log "orchestrate reported failures (see above)." }
    $packArgs = @("run", "scripts/build_kb_pack.py", "--config", "config.yaml")
    if ($KbDir) { $packArgs += @("--kb-dir", $KbDir) }
    if ((Invoke-Logged $uvExe $packArgs) -ne 0) { $failed = $true; Write-Log "build_kb_pack failed." }
}
catch {
    $failed = $true
    Write-Log ("ERROR: {0}" -f $_.Exception.Message)
}
finally {
    Exit-RunLock
    Write-Log ("=== nightly run end: {0} === log: {1}" -f ($(if ($failed) { "FAILED" } else { "OK" })), $log)
}
if ($failed) { exit 1 } else { exit 0 }
