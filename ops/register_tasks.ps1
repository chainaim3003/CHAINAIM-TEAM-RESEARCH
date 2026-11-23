<#
.SYNOPSIS
    Create (or remove) the two Windows Task Scheduler jobs for the research agent (no AI).

.DESCRIPTION
    ChainAIM-Research-Nightly : every day at -NightlyAt     -> ops\run_nightly.ps1
    ChainAIM-Research-Weekly  : every -WeeklyDay at -WeeklyAt -> ops\run_weekly.ps1
    Tasks run as the CURRENT user, only while that user is logged on (no password stored),
    start late if the PC was off at the scheduled time, never run twice at once, and stop
    after -TimeLimitHours. The full path of uv.exe is resolved now and stored in the task.
    Re-running this script updates the tasks (-Force). Use -WhatIf to preview, -Unregister to remove.

.PARAMETER NightlyAt   Time for the nightly run, HH:mm (default 02:30)
.PARAMETER WeeklyDay   Day for the weekly digest (default Sunday)
.PARAMETER WeeklyAt    Time for the weekly digest, HH:mm (default 09:00)
.PARAMETER KbDir       KB folder passed to both runs (default: config output.kb_dir)
.PARAMETER SourceList  Link list for the nightly run (default: config)
.PARAMETER SourceDir   Link folder for the nightly run (default: config)
.PARAMETER TimeLimitHours  Max runtime per run (default 2)
.PARAMETER Unregister  Remove both tasks instead of creating them

.EXAMPLE
    .\ops\register_tasks.ps1 -WhatIf
.EXAMPLE
    .\ops\register_tasks.ps1 -KbDir "$R\Transcript" -SourceList "$R\Transcript\links.txt" -SourceDir "$R\Transcript\no-such-dir"
.EXAMPLE
    .\ops\register_tasks.ps1 -Unregister
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$NightlyAt = "02:30",
    [ValidateSet("Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday")]
    [string]$WeeklyDay = "Sunday",
    [string]$WeeklyAt = "09:00",
    [string]$KbDir, [string]$SourceList, [string]$SourceDir,
    [int]$TimeLimitHours = 2,
    [switch]$Unregister
)
$ErrorActionPreference = "Stop"
$names = @("ChainAIM-Research-Nightly", "ChainAIM-Research-Weekly")

if ($Unregister) {
    foreach ($n in $names) {
        if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) {
            if ($PSCmdlet.ShouldProcess($n, "Unregister scheduled task")) {
                Unregister-ScheduledTask -TaskName $n -Confirm:$false
                Write-Host "removed: $n"
            }
        } else { Write-Host "not registered: $n" }
    }
    return
}

$uv = (Get-Command uv -ErrorAction SilentlyContinue)
if (-not $uv) { throw "uv not found on PATH - install uv first." }
$uvPath = $uv.Source

function Q([string]$s) { '"' + $s + '"' }
$nightlyScript = Join-Path $PSScriptRoot "run_nightly.ps1"
$weeklyScript  = Join-Path $PSScriptRoot "run_weekly.ps1"

$nArgs = "-NoProfile -ExecutionPolicy Bypass -File " + (Q $nightlyScript) + " -Uv " + (Q $uvPath)
if ($KbDir)      { $nArgs += " -KbDir " + (Q $KbDir) }
if ($SourceList) { $nArgs += " -SourceList " + (Q $SourceList) }
if ($SourceDir)  { $nArgs += " -SourceDir " + (Q $SourceDir) }
$wArgs = "-NoProfile -ExecutionPolicy Bypass -File " + (Q $weeklyScript) + " -Uv " + (Q $uvPath)
if ($KbDir)      { $wArgs += " -KbDir " + (Q $KbDir) }

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours $TimeLimitHours) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME) -LogonType Interactive -RunLevel Limited

$jobs = @(
    @{ Name = $names[0]; Args = $nArgs; Trigger = (New-ScheduledTaskTrigger -Daily -At $NightlyAt);
       Desc = "ChainAIM research agent: nightly extraction + prompts (no AI)" },
    @{ Name = $names[1]; Args = $wArgs; Trigger = (New-ScheduledTaskTrigger -Weekly -DaysOfWeek $WeeklyDay -At $WeeklyAt);
       Desc = "ChainAIM research agent: weekly digest (no AI)" }
)
foreach ($j in $jobs) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $j.Args -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
    if ($PSCmdlet.ShouldProcess($j.Name, "Register scheduled task")) {
        Register-ScheduledTask -TaskName $j.Name -Action $action -Trigger $j.Trigger -Settings $settings `
            -Principal $principal -Description $j.Desc -Force | Out-Null
        Write-Host ("registered: {0}" -f $j.Name)
    } else {
        Write-Host ("would register: {0}`n    powershell.exe {1}" -f $j.Name, $j.Args)
    }
}
Write-Host "Check with:  Get-ScheduledTask -TaskName 'ChainAIM-Research-*' | Get-ScheduledTaskInfo"
