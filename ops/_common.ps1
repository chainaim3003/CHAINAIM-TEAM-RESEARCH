# ops/_common.ps1 - shared helpers for the scheduled runs (dot-sourced; not run directly).
# Windows PowerShell 5.1 compatible. No AI is used anywhere in these runs.
#
# Provides:
#   Write-Log <text>          - prints and appends a UTF-8 line to the current log file
#   Invoke-Logged <exe> <args> - runs a native command, streams its output into the log,
#                                returns its exit code
#   Enter-RunLock / Exit-RunLock - single-run lock (pipeline.lock at the repo root, git-ignored)
#                                so a nightly and a weekly run (or two clicks) never overlap.

$script:RepoRoot = Split-Path -Parent $PSScriptRoot
$script:PkgDir   = Join-Path $script:RepoRoot "chainaim-deep-research"
$script:LogDir   = Join-Path $script:RepoRoot "logs"
$script:LockFile = Join-Path $script:RepoRoot "pipeline.lock"

function Start-RunLog([string]$Name) {
    if (-not (Test-Path -LiteralPath $script:LogDir)) { New-Item -ItemType Directory -Path $script:LogDir | Out-Null }
    $script:LogFile = Join-Path $script:LogDir ("{0}-{1}.log" -f (Get-Date -Format "yyyy-MM-dd_HHmmss"), $Name)
    return $script:LogFile
}

function Write-Log([string]$Text) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Text
    Write-Host $line
    Add-Content -LiteralPath $script:LogFile -Value $line -Encoding UTF8
}

function Invoke-Logged([string]$Exe, [string[]]$Arguments) {
    Write-Log ("RUN  {0} {1}" -f $Exe, ($Arguments -join " "))
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"   # native stderr must not abort the run
    & $Exe @Arguments 2>&1 | ForEach-Object {
        $l = "$_"
        Write-Host $l
        Add-Content -LiteralPath $script:LogFile -Value $l -Encoding UTF8
    }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    Write-Log ("EXIT {0}" -f $code)
    return $code
}

function Enter-RunLock {
    if (Test-Path -LiteralPath $script:LockFile) {
        $pidText = (Get-Content -LiteralPath $script:LockFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        $otherPid = 0
        if ([int]::TryParse("$pidText", [ref]$otherPid) -and (Get-Process -Id $otherPid -ErrorAction SilentlyContinue)) {
            Write-Log "Another run is in progress (PID $otherPid). Skipping this run."
            return $false
        }
        Write-Log "Removing stale lock (PID '$pidText' is not running)."
    }
    Set-Content -LiteralPath $script:LockFile -Value $PID -Encoding ASCII
    return $true
}

function Exit-RunLock {
    if (Test-Path -LiteralPath $script:LockFile) { Remove-Item -LiteralPath $script:LockFile -Force }
}

function Resolve-Uv([string]$Uv) {
    if ($Uv) { return $Uv }
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $cmd) { throw "uv not found on PATH. Install uv or pass -Uv <full path to uv.exe>." }
    return $cmd.Source
}

function Get-PathArgs([string]$KbDir, [string]$SourceList, [string]$SourceDir) {
    $a = @()
    if ($KbDir)      { $a += @("--kb-dir", $KbDir) }
    if ($SourceList) { $a += @("--source-list", $SourceList) }
    if ($SourceDir)  { $a += @("--source-dir", $SourceDir) }
    return ,$a
}
