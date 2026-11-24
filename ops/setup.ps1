<#
.SYNOPSIS
    One-command setup of the ChainAIM research agent on a Windows PC (PR-10, no AI).

.DESCRIPTION
    Takes a PC from nothing to a working agent. Every step checks first and skips what is
    already done, so it is safe to run again (e.g. to repair or update).
      1. Check the PC      - Windows, PowerShell 5.1+
      2. Tools             - git (winget) and uv (official installer) if missing
      3. Code              - clone the repo to -InstallDir, or update it (fast-forward only)
      4. Packages          - uv sync --frozen + the YouTube transcript tool's package
      5. Knowledge base    - <InstallDir>\Transcript\ and links.txt
      6. .env              - copied from .env.example (optional GitHub token, hidden prompt)
      7. Tests             - evals must all pass, otherwise setup stops
      8. Scheduled tasks   - nightly + weekly, pointed at <InstallDir>\Transcript
      9. End-to-end test   - adds -TestLink via ops\add_link.ps1 and checks the files
     10. VS Code           - opens the repo (tasks "Research: add link" / "Research: open app")
    No admin rights needed. A step log is written to <InstallDir>\logs\setup-<time>.log.

    One command for a new PC (PowerShell):
      irm https://raw.githubusercontent.com/chainaim3003/CHAINAIM-TEAM-RESEARCH/main/ops/setup.ps1 -OutFile $env:TEMP\setup.ps1; powershell -NoProfile -ExecutionPolicy Bypass -File $env:TEMP\setup.ps1

.PARAMETER InstallDir      Repo folder (default C:\ChainAIM\CHAINAIM-TEAM-RESEARCH; when this script
                           is run from inside a cloned repo and -InstallDir is not given, that repo).
.PARAMETER RepoUrl         Git URL to clone (default the GitHub repo).
.PARAMETER Branch          Branch for a new clone (default main). For an existing repo the current
                           branch is kept unless -Branch is given.
.PARAMETER NightlyAt       Nightly run time HH:mm (default 02:30).
.PARAMETER WeeklyDay       Weekly digest day (default Sunday).
.PARAMETER WeeklyAt        Weekly digest time HH:mm (default 09:00).
.PARAMETER TestLink        Link used for the end-to-end test (default arXiv 1706.03762).
.PARAMETER SkipTests       Do not run the evals.
.PARAMETER SkipTasks       Do not register the scheduled tasks.
.PARAMETER SkipSmokeTest   Do not run the end-to-end link test.
.PARAMETER NoVSCode        Do not open VS Code at the end.
.PARAMETER InstallVSCode   Install VS Code with winget if it is missing.
.PARAMETER AskGithubToken  Ask for a GitHub token (hidden input) and store it in .env.
.PARAMETER DryRun          Only print what would be done; change nothing.
.PARAMETER Uninstall       Remove the two scheduled tasks (files and data are kept).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File ops\setup.ps1 -DryRun
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File ops\setup.ps1 -InstallDir D:\Work\research -NightlyAt 23:00
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File ops\setup.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "C:\ChainAIM\CHAINAIM-TEAM-RESEARCH",
    [string]$RepoUrl = "https://github.com/chainaim3003/CHAINAIM-TEAM-RESEARCH.git",
    [string]$Branch = "main",
    [string]$NightlyAt = "02:30",
    [ValidateSet("Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday")]
    [string]$WeeklyDay = "Sunday",
    [string]$WeeklyAt = "09:00",
    [string]$TestLink = "https://arxiv.org/abs/1706.03762",
    [switch]$SkipTests, [switch]$SkipTasks, [switch]$SkipSmokeTest,
    [switch]$NoVSCode, [switch]$InstallVSCode, [switch]$AskGithubToken,
    [switch]$DryRun, [switch]$Uninstall
)
$ErrorActionPreference = "Stop"
$script:Log = Join-Path $env:TEMP ("chainaim-setup-{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
$script:Results = New-Object System.Collections.ArrayList

# ---------------- helpers ----------------
function Say([string]$Text, [string]$Color = "Gray") {
    Write-Host $Text -ForegroundColor $Color
    Add-Content -LiteralPath $script:Log -Value ("{0}  {1}" -f (Get-Date -Format "HH:mm:ss"), $Text) -Encoding UTF8
}
function Step([int]$N, [string]$Title) { Say ""; Say ("[{0}/10] {1}" -f $N, $Title) "Cyan" }
function Done([string]$Name, [string]$Status) {
    # In -DryRun, steps that would change something are labelled "dry-run: ..." (nothing was done).
    if ($DryRun -and $Status -notmatch '^(OK|already installed|kept|skipped|dry-run)') { $Status = "dry-run: $Status" }
    [void]$script:Results.Add([pscustomobject]@{ Step = $Name; Result = $Status })
}
function Has([string]$Cmd) { [bool](Get-Command $Cmd -ErrorAction SilentlyContinue) }
function Refresh-Path {
    $m = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $u = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$m;$u;$HOME\.local\bin"
}
function Run([string]$Exe, [string[]]$Arguments, [string]$What) {
    # Runs a native command (output shown live), throws if it fails. Honours -DryRun.
    if ($DryRun) { Say ("  [dry-run] would run: {0} {1}" -f $Exe, ($Arguments -join " ")) "Yellow"; return }
    Say ("  > {0} {1}" -f $Exe, ($Arguments -join " "))
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & $Exe @Arguments
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    if ($code -ne 0) { throw ("{0} failed (exit {1})." -f $What, $code) }
}
function Run-Ps([string]$Script, [string[]]$Arguments, [string]$What) {
    Run "powershell.exe" (@("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Script) + $Arguments) $What
}

# Run from inside a cloned repo without -InstallDir -> use that repo.
$here = Split-Path -Parent $PSScriptRoot
if (-not $PSBoundParameters.ContainsKey("InstallDir") -and (Test-Path -LiteralPath (Join-Path $here "chainaim-deep-research\pyproject.toml"))) {
    $InstallDir = $here
}
$Pkg = Join-Path $InstallDir "chainaim-deep-research"
$Kb = Join-Path $InstallDir "Transcript"
$Links = Join-Path $Kb "links.txt"

Say "ChainAIM research agent - setup (no AI)   log: $script:Log" "Green"
$branchNote = if ((Test-Path -LiteralPath (Join-Path $InstallDir ".git")) -and -not $PSBoundParameters.ContainsKey("Branch")) { "current branch (existing repo)" } else { $Branch }
Say ("Install folder: {0}   branch: {1}{2}" -f $InstallDir, $branchNote, $(if ($DryRun) { "   DRY RUN - nothing will change" } else { "" }))

try {
    if ($Uninstall) {
        $reg = Join-Path $InstallDir "ops\register_tasks.ps1"
        if (-not (Test-Path -LiteralPath $reg)) { throw "Not found: $reg (wrong -InstallDir?)" }
        Run-Ps $reg @("-Unregister") "Removing scheduled tasks"
        Say "Scheduled tasks removed. Files and your Transcript\ data were kept." "Green"
        exit 0
    }

    # 1 ---------------------------------------------------------------
    Step 1 "Check this PC"
    if ($env:OS -ne "Windows_NT") { throw "This setup is for Windows." }
    if ($PSVersionTable.PSVersion.Major -lt 5) { throw "PowerShell 5.1 or newer is needed." }
    Say ("  Windows OK, PowerShell {0}" -f $PSVersionTable.PSVersion)
    Done "Check PC" "OK"

    # 2 ---------------------------------------------------------------
    Step 2 "Tools: git and uv"
    Refresh-Path
    if (Has "git") { Say "  git found"; Done "git" "already installed" }
    else {
        if (-not (Has "winget")) { throw "git is missing and winget is not available. Install git from https://git-scm.com/download/win and run setup again." }
        Run "winget" @("install", "--id", "Git.Git", "-e", "--source", "winget", "--accept-package-agreements", "--accept-source-agreements") "Installing git"
        Refresh-Path
        if (-not $DryRun -and -not (Has "git")) { throw "git was installed but is not on PATH yet. Open a new PowerShell window and run setup again." }
        Done "git" "installed"
    }
    if (Has "uv") { Say "  uv found"; Done "uv" "already installed" }
    else {
        # Official installer (docs.astral.sh/uv/getting-started/installation)
        Run "powershell.exe" @("-NoProfile", "-ExecutionPolicy", "ByPass", "-c", "irm https://astral.sh/uv/install.ps1 | iex") "Installing uv"
        Refresh-Path
        if (-not $DryRun -and -not (Has "uv")) { throw "uv was installed but is not on PATH yet. Open a new PowerShell window and run setup again." }
        Done "uv" "installed"
    }

    # 3 ---------------------------------------------------------------
    Step 3 "Code: $InstallDir"
    if (Test-Path -LiteralPath (Join-Path $InstallDir ".git")) {
        $dirty = (& git -C $InstallDir status --porcelain --untracked-files=no) -join ""   # read-only, also in -DryRun
        if ($dirty) {
            Say "  Local changes found - not updating the code (your changes are kept)." "Yellow"
            Done "Code" "kept (local changes)"
        } else {
            # Existing repo: stay on its current branch unless -Branch was given explicitly.
            $target = $Branch
            if (-not $PSBoundParameters.ContainsKey("Branch")) {
                $target = (& git -C $InstallDir rev-parse --abbrev-ref HEAD).Trim()
            }
            Run "git" @("-C", $InstallDir, "fetch", "origin") "git fetch"
            if ($PSBoundParameters.ContainsKey("Branch")) { Run "git" @("-C", $InstallDir, "checkout", $target) "git checkout" }
            Run "git" @("-C", $InstallDir, "pull", "--ff-only", "origin", $target) "git pull"
            Done "Code" "updated ($target)"
        }
    } elseif (Test-Path -LiteralPath $InstallDir) {
        if (@(Get-ChildItem -LiteralPath $InstallDir -Force).Count -gt 0) {
            throw "$InstallDir exists and is not empty (and is not a git repo). Choose another -InstallDir."
        }
        Run "git" @("clone", "--branch", $Branch, $RepoUrl, $InstallDir) "git clone"
        Done "Code" "cloned"
    } else {
        $parent = Split-Path -Parent $InstallDir
        if (-not $DryRun -and $parent -and -not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
        Run "git" @("clone", "--branch", $Branch, $RepoUrl, $InstallDir) "git clone"
        Done "Code" "cloned"
    }

    # 4 ---------------------------------------------------------------
    Step 4 "Packages (uv sync)"
    if (-not $DryRun) { Set-Location -LiteralPath $Pkg }
    Run "uv" @("sync", "--frozen") "uv sync"
    $skill = Join-Path $InstallDir "agent-skills\skills\youtube-transcript\scripts\get_transcript.py"
    Run "uv" @("run", $skill, "--help") "Preparing the YouTube transcript tool"
    Done "Packages" "installed"

    # 5 ---------------------------------------------------------------
    Step 5 "Knowledge base folder: $Kb"
    if ($DryRun) { Say "  [dry-run] would create $Kb and $Links" "Yellow" }
    else {
        if (-not (Test-Path -LiteralPath $Kb)) { New-Item -ItemType Directory -Path $Kb | Out-Null }
        if (-not (Test-Path -LiteralPath $Links)) { [IO.File]::WriteAllText($Links, "") }
    }
    Done "Transcript folder" "ready"

    # 6 ---------------------------------------------------------------
    Step 6 ".env (optional keys)"
    $envFile = Join-Path $InstallDir ".env"
    $envExample = Join-Path $InstallDir ".env.example"
    if ($DryRun) { Say "  [dry-run] would create .env from .env.example if missing" "Yellow"; Done ".env" "dry-run" }
    else {
        if (-not (Test-Path -LiteralPath $envFile)) { Copy-Item -LiteralPath $envExample -Destination $envFile; Say "  .env created (all values empty)" }
        else { Say "  .env already exists - kept" }
        if ($AskGithubToken) {
            Say "  Type or paste the GitHub token (input is hidden; it is NOT shown or logged):" "Yellow"
            $sec = Read-Host -AsSecureString "GITHUB_TOKEN"
            $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
            try { $tok = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
            if ($tok) {
                $lines = @([IO.File]::ReadAllLines($envFile))
                $found = $false
                for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match "^\s*GITHUB_TOKEN\s*=") { $lines[$i] = "GITHUB_TOKEN=$tok"; $found = $true } }
                if (-not $found) { $lines += "GITHUB_TOKEN=$tok" }
                [IO.File]::WriteAllLines($envFile, [string[]]$lines, (New-Object System.Text.UTF8Encoding($false)))
                $tok = $null
                Say "  GITHUB_TOKEN saved in .env"
            } else { Say "  No token entered - skipped" }
        }
        Done ".env" "ready"
    }

    # 7 ---------------------------------------------------------------
    Step 7 "Tests (evals)"
    if ($SkipTests) { Say "  skipped (-SkipTests)"; Done "Tests" "skipped" }
    else { Run "uv" @("run", "evals/run_evals.py") "Tests"; Done "Tests" "all passed" }

    # 8 ---------------------------------------------------------------
    Step 8 "Scheduled tasks (nightly $NightlyAt, weekly $WeeklyDay $WeeklyAt)"
    if ($SkipTasks) { Say "  skipped (-SkipTasks)"; Done "Scheduled tasks" "skipped" }
    else {
        Run-Ps (Join-Path $InstallDir "ops\register_tasks.ps1") @(
            "-KbDir", $Kb, "-SourceList", $Links, "-SourceDir", (Join-Path $Kb "no-such-dir"),
            "-NightlyAt", $NightlyAt, "-WeeklyDay", $WeeklyDay, "-WeeklyAt", $WeeklyAt) "Registering scheduled tasks"
        Done "Scheduled tasks" "registered"
    }

    # 9 ---------------------------------------------------------------
    Step 9 "End-to-end test: $TestLink"
    if ($SkipSmokeTest) { Say "  skipped (-SkipSmokeTest)"; Done "End-to-end test" "skipped" }
    else {
        Run-Ps (Join-Path $InstallDir "ops\add_link.ps1") @("-Link", $TestLink, "-KbDir", $Kb, "-SourceList", $Links) "End-to-end link test"
        if (-not $DryRun) {
            $index = Join-Path $Kb "kb\INDEX.md"
            $prompts = @(Get-ChildItem -LiteralPath (Join-Path $Kb "kb\prompts") -Filter "*.prompt.md" -ErrorAction SilentlyContinue)
            if (-not (Test-Path -LiteralPath $index) -or $prompts.Count -eq 0) { throw "End-to-end test ran but no prompt / INDEX.md was written in $Kb\kb." }
            Say ("  OK: {0} prompt file(s), INDEX.md written" -f $prompts.Count)
        }
        Done "End-to-end test" "passed"
    }

    # 10 --------------------------------------------------------------
    Step 10 "VS Code"
    Refresh-Path
    if (-not (Has "code") -and $InstallVSCode) {
        Run "winget" @("install", "--id", "Microsoft.VisualStudioCode", "-e", "--source", "winget", "--accept-package-agreements", "--accept-source-agreements") "Installing VS Code"
        Refresh-Path
    }
    if ($NoVSCode) { Say "  skipped (-NoVSCode)"; Done "VS Code" "skipped" }
    elseif (Has "code") { Run "code" @($InstallDir) "Opening VS Code"; Done "VS Code" "opened" }
    else { Say "  VS Code not found. Install it (or re-run with -InstallVSCode), then open $InstallDir." "Yellow"; Done "VS Code" "not installed" }
}
catch {
    Say ""
    Say ("SETUP STOPPED: {0}" -f $_.Exception.Message) "Red"
    Say "Fix the problem above and run the same command again - finished steps are skipped." "Red"
    $script:Results | Format-Table -AutoSize | Out-String | ForEach-Object { Say $_ }
    exit 1
}

# ---------------- summary ----------------
Say ""
if ($DryRun) { Say "========== DRY RUN COMPLETE - nothing was changed ==========" "Yellow" }
else { Say "==================== SETUP COMPLETE ====================" "Green" }
$script:Results | Format-Table -AutoSize | Out-String | ForEach-Object { Say $_ }
Say "Next:"
Say "  VS Code: Ctrl+Shift+P -> Tasks: Run Task -> 'Research: add link'  (paste a URL)"
Say "  VS Code: Ctrl+Shift+P -> Tasks: Run Task -> 'Research: open app'  (http://127.0.0.1:8501)"
Say "  Your files: $Kb\kb   (prompts\ -> paste into any AI, save the answer with the app)"
Say "  All commands: $InstallDir\CMD.md"
if (-not $DryRun) {
    $logDir = Join-Path $InstallDir "logs"
    if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $final = Join-Path $logDir (Split-Path -Leaf $script:Log)
    Copy-Item -LiteralPath $script:Log -Destination $final -Force
    Write-Host "Setup log: $final"
}
exit 0
