$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Thiếu .venv. Cài dependencies của API trước khi chạy.'
}
$workerProcess = $null
$courseWorkerProcess = $null
$blogWorkerProcess = $null
$locationPushed = $false
try {
    $workerProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-B', 'manage.py', 'sync_accounts') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
    $courseWorkerProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-B', 'manage.py', 'sync_courses') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
    $blogWorkerProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-B', 'manage.py', 'sync_blog') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
    Push-Location $PSScriptRoot
    $locationPushed = $true
    & $pythonPath -B manage.py runserver 127.0.0.1:8001
} finally {
    if ($locationPushed) { Pop-Location }
    if ($workerProcess -and -not $workerProcess.HasExited) { $workerProcess.Kill() }
    if ($courseWorkerProcess -and -not $courseWorkerProcess.HasExited) { $courseWorkerProcess.Kill() }
    if ($blogWorkerProcess -and -not $blogWorkerProcess.HasExited) { $blogWorkerProcess.Kill() }
}
