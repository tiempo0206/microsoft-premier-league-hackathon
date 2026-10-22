param([ValidateRange(1024, 65535)][int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create this project .venv and install backend/requirements.lock first; see backend/README.md.'
}
Push-Location -LiteralPath $projectRoot
$previousPort = $env:PORT
try {
    $env:PORT = [string]$Port
    & $pythonPath -m deploy.preflight
    if ($LASTEXITCODE -ne 0) { throw 'Backend data/config preflight failed; review its JSON report.' }
    & $pythonPath -m uvicorn backend.app:app --host 127.0.0.1 --port $Port --workers 1
    if ($LASTEXITCODE -ne 0) { throw "Backend exited with code $LASTEXITCODE" }
} finally {
    $env:PORT = $previousPort
    Pop-Location
}
