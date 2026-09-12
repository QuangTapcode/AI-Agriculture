param(
    [string]$TaskName = 'AgriAI Public Web Watchdog'
)

$ErrorActionPreference = 'Stop'
$watchdog = Join-Path $PSScriptRoot 'ensure-public-web.ps1'
$quotedWatchdog = '"' + $watchdog + '"'
$taskCommand = "powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File $quotedWatchdog"

schtasks.exe /Create /TN $TaskName /SC HOURLY /MO 1 /TR $taskCommand /F | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Khong the tao tac vu kiem tra web.'
}

Write-Output "PASS: da tao tac vu '$TaskName', chay moi gio."
