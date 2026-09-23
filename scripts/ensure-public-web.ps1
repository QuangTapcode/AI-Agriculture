param(
    [string]$PagesUrl = 'https://agriai-demo.pages.dev'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$mainComposeFile = Join-Path $projectRoot 'docker-compose.yml'
$composeFile = Join-Path $projectRoot 'infra\public-web\docker-compose.yml'
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

function Test-ContainerExists([string]$name) {
    docker inspect $name 1>$null 2>$null
    return $LASTEXITCODE -eq 0
}

function Get-ContainerState([string]$name) {
    if (-not (Test-ContainerExists $name)) {
        return $null
    }

    return (docker inspect --format '{{.State.Status}}' $name).Trim()
}

function Wait-ForDocker {
    $deadline = (Get-Date).AddMinutes(5)
    do {
        docker info 1>$null 2>$null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)

    throw 'Docker chua san sang sau 5 phut.'
}

function Start-BackendStack {
    if (-not (Test-Path -LiteralPath $mainComposeFile)) {
        throw "Khong tim thay cau hinh backend: $mainComposeFile"
    }

    & docker compose -f $mainComposeFile up -d db redis backend
    if ($LASTEXITCODE -ne 0) {
        throw 'Khong the khoi dong db, redis va backend.'
    }
}

function Start-PublicStack {
    $publicExists = Test-ContainerExists $publicContainer
    $tunnelExists = Test-ContainerExists $tunnelContainer

    if (-not ($publicExists -and $tunnelExists)) {
        if (-not (Test-Path -LiteralPath $composeFile)) {
            throw "Khong tim thay cau hinh public web: $composeFile"
        }

        & docker compose -f $composeFile up -d --build
        if ($LASTEXITCODE -ne 0) {
            throw 'Khong the tao lai public web stack bang Docker Compose.'
        }
    }

    if ((Get-ContainerState $publicContainer) -ne 'running') {
        docker start $publicContainer | Out-Null
    }
    if ((Get-ContainerState $tunnelContainer) -ne 'running') {
        docker start $tunnelContainer | Out-Null
    }
}

function Wait-ForLocalWeb {
    $deadline = (Get-Date).AddMinutes(2)
    do {
        if (Test-Health 'http://127.0.0.1:18080') {
            return
        }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)

    throw 'Public web local chua tra ve health sau 2 phut.'
}

function Wait-ForPageHealth([string]$url) {
    $deadline = (Get-Date).AddMinutes(3)
    do {
        if (Test-Health $url) {
            return
        }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)

    throw "$url van chua dat health sau 3 phut propagation."
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Khong tim thay Docker CLI.'
}

Wait-ForDocker
Start-BackendStack
Start-PublicStack
Wait-ForLocalWeb

if (Test-Health $PagesUrl) {
    Write-Output "PASS: $PagesUrl dang hoat dong."
    exit 0
}

# A running Quick Tunnel can still point at a revoked/expired URL. Restarting
# it forces a new URL, then update-pages-proxy deploys that URL to Pages.
docker restart $publicContainer | Out-Null
docker restart $tunnelContainer | Out-Null

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $updateScript
if ($LASTEXITCODE -ne 0) {
    throw 'Khong the cap nhat Cloudflare Pages sang Quick Tunnel moi.'
}

Wait-ForPageHealth $PagesUrl

Write-Output "PASS: da phuc hoi $PagesUrl."
