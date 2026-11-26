<#
.SYNOPSIS
    Start the ChainAIM Research local app (PR-9, no AI) at http://127.0.0.1:<Port>.

.DESCRIPTION
    Runs `uv run streamlit run app/streamlit_app.py` from chainaim-deep-research, bound to
    127.0.0.1 only (not reachable from other computers), with Streamlit usage statistics off and
    the developer toolbar items (Deploy, Rerun, Clear cache) hidden (client.toolbarMode viewer, PR-12).
    Opens the page in your default browser a few seconds after start (unless -NoBrowser).
    The first start may take a minute while uv installs Streamlit. Stop the app with Ctrl+C.
    The app uses the same pipeline.lock as the scheduled tasks, so runs never overlap.
    Used by the VS Code task "Research: open app" (.vscode/tasks.json).

.PARAMETER Port       Port to serve on (default 8501).
.PARAMETER NoBrowser  Do not open the browser automatically.
.PARAMETER KbDir      Optional extra KB folder offered first in the app (sets CHAINAIM_APP_KB).
.PARAMETER Uv         Full path to uv.exe (default: found on PATH).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File ops\run_app.ps1
#>
[CmdletBinding()]
param([int]$Port = 8501, [switch]$NoBrowser, [string]$KbDir, [string]$Uv)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_common.ps1")

$uvExe = Resolve-Uv $Uv
if ($KbDir) { $env:CHAINAIM_APP_KB = $KbDir }
$url = "http://127.0.0.1:$Port"
Write-Host "ChainAIM Research app (no AI) -> $url   (Ctrl+C to stop)"
if (-not $NoBrowser) {
    Start-Process powershell -WindowStyle Hidden -ArgumentList @(
        "-NoProfile", "-Command", "Start-Sleep -Seconds 5; Start-Process '$url'")
}
Set-Location -LiteralPath $script:PkgDir
& $uvExe run streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port $Port `
    --server.headless true --browser.gatherUsageStats false --client.toolbarMode viewer
exit $LASTEXITCODE
