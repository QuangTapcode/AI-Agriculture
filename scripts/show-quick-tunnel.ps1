param(
    [switch]$Open
)

$ErrorActionPreference = "Stop"
$containerName = "agriai-quick-tunnel"

$status = docker inspect --format "{{.State.Status}}" $containerName 2>$null
if ($LASTEXITCODE -ne 0 -or $status -ne "running") {
    throw "Cloudflare Quick Tunnel chua chay. Hay mo Docker Desktop va doi cac container khoi dong."
}

$ErrorActionPreference = "Continue"
$logText = (docker logs $containerName 2>&1) -join "`n"
$ErrorActionPreference = "Stop"
$matches = [regex]::Matches($logText, 'https://[a-z0-9-]+\.trycloudflare\.com')
if ($matches.Count -eq 0) {
    throw "Chua tim thay URL. Hay doi vai giay roi chay lai tep nay."
}

$url = $matches[$matches.Count - 1].Value
Write-Host "AgriAI dang hoat dong tai:" -ForegroundColor Green
Write-Host $url -ForegroundColor Cyan

if ($Open) {
    Start-Process $url
}
