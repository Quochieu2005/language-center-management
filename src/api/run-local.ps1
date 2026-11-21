$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Thiếu .venv. Cài dependencies của API trước khi chạy.'
}
$workerProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-B', 'manage.py', 'sync_accounts') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
try {
    Push-Location $PSScriptRoot
    & $pythonPath -B manage.py runserver 127.0.0.1:8001
} finally {
    Pop-Location
    if (-not $workerProcess.HasExited) { $workerProcess.Kill() }
}
