$modulePath = Join-Path $PSScriptRoot '..\PublicWebRecovery.psm1'
Import-Module $modulePath -Force

Describe 'Public web recovery' {
    It 'returns the newest Quick Tunnel URL from cloudflared output' {
        $logs = @'
2026-09-22T00:01:00Z INF | Your quick Tunnel has been created! Visit it at https://old-origin.trycloudflare.com
2026-09-22T00:02:00Z INF | Your quick Tunnel has been created! Visit it at https://new-origin.trycloudflare.com
'@

        Get-QuickTunnelUrl -Text $logs | Should Be 'https://new-origin.trycloudflare.com'
    }

    It 'updates only the Worker origin declaration' {
        $source = @'
const ORIGIN_URL = "https://old-origin.trycloudflare.com";

export default {
  async fetch(request) {
    return fetch(request);
  },
};
'@

        $updated = Set-WorkerOriginUrl -WorkerSource $source -OriginUrl 'https://new-origin.trycloudflare.com'

        $updated | Should Match 'const ORIGIN_URL = "https://new-origin.trycloudflare.com";'
        $updated | Should Match 'async fetch\(request\)'
    }
}
