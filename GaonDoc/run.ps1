Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\uvicorn.exe")) {
    Write-Host "Setting up virtual environment..." -ForegroundColor Cyan
    py -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt
}

Write-Host "Starting GaonDoc on http://localhost:8000 ..." -ForegroundColor Green
Start-Process "http://localhost:8000"
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000

