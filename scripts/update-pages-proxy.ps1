$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$recoveryModule = Join-Path $PSScriptRoot "PublicWebRecovery.psm1"
Import-Module $recoveryModule -Force
$pagesDirectory = Join-Path $projectRoot "infra\deploy\agriai-demo-pages"
$workerPath = Join-Path $pagesDirectory "_worker.js"
$logDirectory = Join-Path $projectRoot ".local\logs"
$logPath = Join-Path $logDirectory "pages-proxy-update.log"
$containerName = "agriai-quick-tunnel"
$pagesUrl = "https://agriai-demo.pages.dev"

New-Item -ItemType Directory -Force $logDirectory | Out-Null

function Write-UpdateLog([string]$message) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $logPath -Value "[$timestamp] $message"
}

try {
    $deadline = (Get-Date).AddMinutes(4)
    $quickTunnelUrl = $null

    do {
        $status = docker inspect --format "{{.State.Status}}" $containerName 2>$null
        if ($LASTEXITCODE -eq 0 -and $status -eq "running") {
            $startedAt = docker inspect --format "{{.State.StartedAt}}" $containerName
            $ErrorActionPreference = "Continue"
            $logText = (docker logs --since $startedAt $containerName 2>&1) -join "`n"
            $ErrorActionPreference = "Stop"
            $quickTunnelUrl = Get-QuickTunnelUrl -Text $logText
            if ($quickTunnelUrl) {
                break
            }
        }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)

    if (-not $quickTunnelUrl) {
        throw "Khong tim thay URL Quick Tunnel sau 4 phut."
    }

    $originDeadline = (Get-Date).AddMinutes(2)
    do {
        try {
            $originHealth = Invoke-RestMethod "$quickTunnelUrl/health" -TimeoutSec 15
            if ($originHealth.status -eq "healthy") {
                break
            }
        } catch {
            $originHealth = $null
        }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $originDeadline)

    if ($originHealth.status -ne "healthy") {
        throw "Quick Tunnel co URL nhung backend chua san sang."
    }

    $workerSource = Get-Content -LiteralPath $workerPath -Raw
    $updatedSource = Set-WorkerOriginUrl -WorkerSource $workerSource -OriginUrl $quickTunnelUrl

    if ($updatedSource -ne $workerSource) {
        $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($workerPath, $updatedSource, $utf8WithoutBom)

        Push-Location $pagesDirectory
        try {
            $deployOutput = npx.cmd --yes wrangler@3 pages deploy . --project-name agriai-demo --branch main --commit-dirty=true 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "Cloudflare deploy that bai: $($deployOutput -join ' ')"
            }
        } finally {
            Pop-Location
        }
        Write-UpdateLog "Da cap nhat Pages sang $quickTunnelUrl"
    } else {
        Write-UpdateLog "Pages da dung URL hien tai: $quickTunnelUrl"
    }

    # Pages deployment can return Cloudflare 530 briefly while the new
    # Worker version propagates. Retry the public health check instead of
    # reporting a false failure immediately after a successful deploy.
    $pagesDeadline = (Get-Date).AddMinutes(3)
    $pagesHealth = $null
    do {
        try {
            $pagesHealth = Invoke-RestMethod "$pagesUrl/health" -TimeoutSec 30
            if ($pagesHealth.status -eq "healthy") {
                break
            }
        } catch {
            $pagesHealth = $null
        }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $pagesDeadline)

    if ($pagesHealth.status -ne "healthy") {
        throw "Pages da cap nhat nhung health check khong dat sau khi cho propagation."
    }

    Write-UpdateLog "Kiem tra thanh cong: $pagesUrl"
} catch {
    Write-UpdateLog "LOI: $($_.Exception.Message)"
    exit 1
}
