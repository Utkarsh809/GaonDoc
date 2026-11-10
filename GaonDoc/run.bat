@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\uvicorn.exe" (
    echo Virtual environment not found. Setting up...
    py -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)
echo Starting GaonDoc on http://localhost:8000 ...
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause

