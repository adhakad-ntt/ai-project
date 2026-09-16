@echo off
setlocal
cd /d %~dp0
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or 3.12 and retry.
  pause
  exit /b 1
)
if not exist .venv (
  python -m venv .venv
  if errorlevel 1 exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env >nul
echo.
echo Setup complete.
echo Open .env and replace GROQ_API_KEY with your test API key.
pause
