Describe 'Public web startup recovery' {
    BeforeAll {
        $ensureScript = Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\ensure-public-web.ps1') -Raw
        $watchdogScript = Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\install-public-web-watchdog.ps1') -Raw
        $launcher = Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\..\Xem-Link-AgriAI.cmd') -Raw
    }

    It 'can recreate the public stack through its compose file' {
        $ensureScript | Should Match 'infra\\public-web\\docker-compose\.yml'
        $ensureScript | Should Match 'docker compose'
        $ensureScript | Should Match '--build'
        $ensureScript | Should Match 'Wait-ForPageHealth'
        $ensureScript | Should Match 'Start-BackendStack'
        $ensureScript | Should Match 'db redis backend'
    }

    It 'installs both logon and hourly recovery triggers' {
        $watchdogScript | Should Match 'ONLOGON'
        $watchdogScript | Should Match 'HOURLY'
        $watchdogScript | Should Match 'Startup'
    }

    It 'recovers before opening the public URL' {
        $launcher | Should Match 'ensure-public-web\.ps1'
        $launcher | Should Match 'agriai-demo\.pages\.dev'
    }
}
