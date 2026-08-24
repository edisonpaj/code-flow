@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (py -m venv .venv)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
start "EXPERT CODE FLOW" http://127.0.0.1:8000
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

