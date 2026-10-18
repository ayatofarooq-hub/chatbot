param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$desktopProject = Join-Path $projectRoot 'LegalChatbotDesktop\LegalChatbotDesktop.csproj'
$buildStamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
$publishDirectory = Join-Path $projectRoot "build\desktop\$buildStamp\win-x64"
$archiveDirectory = Join-Path $projectRoot 'LegalChatbotDesktop\dist'
$archivePath = Join-Path $archiveDirectory 'LegalChatbotDesktop-win-x64.zip'

dotnet publish $desktopProject --configuration $Configuration --runtime win-x64 --self-contained true --output $publishDirectory
if ($LASTEXITCODE -ne 0) {
    throw 'Desktop publish failed.'
}

$backendConfiguration = Get-Content -LiteralPath (Join-Path $publishDirectory 'appsettings.json') -Raw | ConvertFrom-Json
$backendRevision = git -C $projectRoot rev-parse HEAD
if ($LASTEXITCODE -ne 0) {
    throw 'Could not identify the backend revision.'
}
$versionRecord = [ordered]@{
    BuiltAtUtc = [DateTime]::UtcNow.ToString('o')
    BackendRevision = $backendRevision.Trim()
    BackendMode = 'shared-python-project'
    BackendWorkingDirectory = $backendConfiguration.Backend.BackendWorkingDirectory
    BackendEntrypoint = 'app.api:app'
}
$versionRecord | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $publishDirectory 'backend-version.json') -Encoding UTF8

New-Item -ItemType Directory -Path $archiveDirectory -Force | Out-Null
Compress-Archive -Path (Join-Path $publishDirectory '*') -DestinationPath $archivePath -Force
Write-Output "Published desktop: $publishDirectory"
Write-Output "Desktop archive: $archivePath"
Write-Output "Shared backend revision: $backendRevision"
