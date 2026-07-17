$ErrorActionPreference = "Stop"

$repoRoot = "c:\GitHubLocal\Albertina"
$serverPath = "c:/GitHubLocal/Albertina/mcp/MCP-Supabase/server.py"
$cfgPath = "c:\Users\tmrossi\AppData\Roaming\Trae\User\mcp.json"

if (-not (Test-Path $cfgPath)) {
    throw "Arquivo nao encontrado: $cfgPath"
}

$json = Get-Content $cfgPath -Raw | ConvertFrom-Json
if (-not $json.mcpServers) {
    $json | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
}

$server = [pscustomobject]@{
    command = "python"
    args = @($serverPath)
    cwd = $repoRoot.Replace('\', '/')
}

$json.mcpServers | Add-Member -NotePropertyName "MCP-Supabase" -NotePropertyValue $server -Force
$json | ConvertTo-Json -Depth 20 | Set-Content $cfgPath -Encoding UTF8

Write-Output "MCP-Supabase registrado em $cfgPath"
