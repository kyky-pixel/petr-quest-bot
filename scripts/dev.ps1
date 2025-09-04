param([ValidateSet("run","fmt")]$cmd="run")

# Абсолютный путь к python.exe из твоего .venv
$venvPy = (Resolve-Path (Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe')).Path

if ($cmd -eq "fmt") {
  & $venvPy -m pip install -q black | Out-Null
  & $venvPy -m black app
  exit
}

Write-Host "Dev-watch: перезапуск при изменениях..." -ForegroundColor Green
Write-Host "Python: $venvPy" -ForegroundColor DarkCyan

# Важно: и watcher, и целевой процесс — под одним и тем же интерпретатором из .venv
& $venvPy -m watchfiles "$venvPy -m app.main"
