Describe 'Public web Docker contract' {
    BeforeAll {
        $composePath = Join-Path $PSScriptRoot '..\..\infra\public-web\docker-compose.yml'
        $compose = Get-Content -LiteralPath $composePath -Raw -ErrorAction SilentlyContinue
    }

    It 'defines a restartable public web service' {
        $compose | Should Not BeNullOrEmpty
        $compose | Should Match 'container_name:\s+agriai-public-web'
        $compose | Should Match 'restart:\s+unless-stopped'
        $compose | Should Match '127\.0\.0\.1:18080:80'
    }

    It 'runs Quick Tunnel with observable logs and a restart policy' {
        $compose | Should Match 'container_name:\s+agriai-quick-tunnel'
        $compose | Should Match '--loglevel'
        $compose | Should Match 'info'
        $compose | Should Match '--url'
        $compose | Should Match 'http://agriai-public-web:80'
        $compose | Should Match 'restart:\s+unless-stopped'
    }

    It 'connects the public frontend to the project backend network' {
        $compose | Should Match 'name:\s+ai-agriculture_default'
        $compose | Should Match 'external:\s+true'
    }
}
