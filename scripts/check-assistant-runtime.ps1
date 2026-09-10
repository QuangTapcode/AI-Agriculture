param(
    [string]$FrontendUrl = 'http://localhost:5173',
    [string]$BackendUrl = 'http://localhost:8000'
)

# Smoke check for the Vite development server used by docker-compose.yml.
# Inspect the running services, not only the files/build on the host.
$ErrorActionPreference = 'Stop'
$page = Invoke-WebRequest -UseBasicParsing "$FrontendUrl/src/pages/AIChatPage.jsx" -TimeoutSec 20
if (-not $page.Content.Contains('libraryOpen')) {
    throw "Frontend at $FrontendUrl is still serving the old assistant. Rebuild and recreate the frontend container."
}
$client = Invoke-WebRequest -UseBasicParsing "$FrontendUrl/src/services/aiApi.js" -TimeoutSec 20
if (-not $client.Content.Contains('/api/ai-chat/documents')) {
    throw 'The running frontend does not have the document upload API client.'
}
$schema = Invoke-RestMethod "$BackendUrl/openapi.json" -TimeoutSec 20
$paths = $schema.paths.PSObject.Properties.Name
foreach ($path in @('/api/ai-chat/documents', '/api/ai-chat/conversations', '/api/ai-chat/message',
                    '/api/admin/knowledge/sources', '/api/admin/knowledge/documents', '/api/admin/knowledge/run')) {
    if ($path -notin $paths) {
        throw "Backend at $BackendUrl is missing $path. Rebuild and recreate the backend container."
    }
}
Write-Output 'PASS: running frontend includes the document library and upload client.'
Write-Output 'PASS: running backend exposes document, conversation and chat APIs.'
Write-Output 'PASS: running backend exposes Knowledge Agent administration APIs.'
