param(
    [string]$PagesUrl = 'https://agriai-demo.pages.dev'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$updateScript = Join-Path $PSScriptRoot 'update-pages-proxy.ps1'
$publicContainer = 'agriai-public-web'
$tunnelContainer = 'agriai-quick-tunnel'

function Test-Health([string]$url) {
    try {
        $result = Invoke-RestMethod "$url/health" -TimeoutSec 15
        return $result.status -eq 'healthy'
    } catch {
        return $false
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker chua san sang.'
}

$publicState = docker inspect --format '{{.State.Status}}' $publicContainer 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Khong tim thay container $publicContainer."
}
if ($publicState -ne 'running') {
    docker start $publicContainer | Out-Null
}

$tunnelState = docker inspect --format '{{.State.Status}}' $tunnelContainer 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Khong tim thay container $tunnelContainer."
}
if ($tunnelState -ne 'running') {
    docker start $tunnelContainer | Out-Null
}

if (Test-Health $PagesUrl) {
    Write-Output "PASS: $PagesUrl dang hoat dong."
    exit 0
}

# Quick Tunnel co the van mang trang thai running sau khi URL da bi thu hoi.
# Restart buoc Cloudflare cap URL moi; script update se cap nhat Pages proxy.
docker restart $publicContainer | Out-Null
docker restart $tunnelContainer | Out-Null

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $updateScript
if ($LASTEXITCODE -ne 0) {
    throw 'Khong the cap nhat Cloudflare Pages sang Quick Tunnel moi.'
}

if (-not (Test-Health $PagesUrl)) {
    throw "$PagesUrl van chua dat health check sau khi phuc hoi."
}

Write-Output "PASS: da phuc hoi $PagesUrl."
