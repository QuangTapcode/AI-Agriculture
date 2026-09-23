param(
    [string]$TaskName = 'AgriAI Public Web Watchdog'
)

$ErrorActionPreference = 'Stop'
$watchdog = Join-Path $PSScriptRoot 'ensure-public-web.ps1'
$startupScript = Join-Path $PSScriptRoot 'run-public-web-watchdog.cmd'
$quotedWatchdog = '"' + $watchdog + '"'
$taskCommand = "powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File $quotedWatchdog"

function Invoke-SchtasksQuiet([string[]]$arguments) {
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & schtasks.exe @arguments 2>&1 | Out-Null
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorAction
    return $exitCode
}

$startupTaskExit = Invoke-SchtasksQuiet @('/Create', '/TN', $TaskName, '/SC', 'ONLOGON', '/TR', $taskCommand, '/F')
$startupInstalled = $startupTaskExit -eq 0

if (-not $startupInstalled) {
    $startupDirectory = [Environment]::GetFolderPath('Startup')
    $startupShortcutPath = Join-Path $startupDirectory 'AgriAI Public Web Watchdog.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($startupShortcutPath)
    $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\cmd.exe'
    $shortcut.Arguments = "/c `"$startupScript`""
    $shortcut.WorkingDirectory = Split-Path -Parent $PSScriptRoot
    $shortcut.WindowStyle = 7
    $shortcut.Save()

    if (-not (Test-Path -LiteralPath $startupShortcutPath)) {
        throw 'Khong the tao shortcut khoi phuc web trong thu muc Startup.'
    }
}

$hourlyTaskName = "$TaskName (Hourly)"
$hourlyTaskExit = Invoke-SchtasksQuiet @('/Create', '/TN', $hourlyTaskName, '/SC', 'HOURLY', '/MO', '1', '/TR', $taskCommand, '/F')
if ($hourlyTaskExit -ne 0) {
    $existingTaskExit = Invoke-SchtasksQuiet @('/Query', '/TN', $TaskName)
    if ($existingTaskExit -ne 0) {
        throw 'Khong the tao tac vu kiem tra web moi gio.'
    }
}

if ($startupInstalled) {
    Write-Output "PASS: da tao '$TaskName' khi dang nhap va '$hourlyTaskName' moi gio."
} else {
    Write-Output "PASS: da cai fallback Startup va watchdog moi gio."
}
