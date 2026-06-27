$ErrorActionPreference = 'Stop'

$baseUrl = 'http://127.0.0.1:8000/api'
$outputPath = 'c:\GitHubLocal\Albertina\last_extraction_validation_result.json'

$loginBody = @{
    email    = 'admin@empresa.com'
    password = 'Betin@01012023'
} | ConvertTo-Json

$login = Invoke-RestMethod -Uri "$baseUrl/auth/login" -Method Post -ContentType 'application/json' -Body $loginBody
$headers = @{ Authorization = "Bearer $($login.token)" }

$start = Invoke-RestMethod -Uri "$baseUrl/extraction/run" -Method Post -Headers $headers
$executionId = $start.executionId

do {
    Start-Sleep -Seconds 20
    $execution = Invoke-RestMethod -Uri "$baseUrl/extraction/executions/$executionId" -Method Get -Headers $headers
    $running = @($execution.runs | Where-Object { $_.status -eq 'running' }).Count -gt 0
} while ($running)

$execution | ConvertTo-Json -Depth 8 | Set-Content -Path $outputPath -Encoding UTF8
Write-Host $outputPath
