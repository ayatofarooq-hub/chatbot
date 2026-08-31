$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$modelName = "vits-piper-ar_JO-kareem-medium"
$ttsRoot = Join-Path $projectRoot "data\models\tts"
$modelDirectory = Join-Path $ttsRoot $modelName
$modelFile = Join-Path $modelDirectory "ar_JO-kareem-medium.onnx"
$archive = Join-Path $ttsRoot "$modelName.tar.bz2"
$downloadUrl = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/$modelName.tar.bz2"

if (Test-Path -LiteralPath $modelFile) {
    Write-Host "[OK] Local Arabic voice is already installed."
    exit 0
}

New-Item -ItemType Directory -Force -Path $ttsRoot | Out-Null
Write-Host "[INFO] Downloading the offline Arabic voice model (about 64 MB)..."
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $archive
    tar -xjf $archive -C $ttsRoot
} finally {
    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive -Force
    }
}

if (-not (Test-Path -LiteralPath $modelFile)) {
    throw "The local Arabic voice model could not be installed."
}
Write-Host "[OK] Local Arabic voice installed: $modelName"
