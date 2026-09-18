@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or 3.12 and retry.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  python -m venv .venv
  if errorlevel 1 goto setup_failed
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto setup_failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto setup_failed
".venv\Scripts\python.exe" -c "import streamlit"
if errorlevel 1 goto setup_failed
if not exist .env (
  if exist .env.example (
    copy .env.example .env >nul
    if errorlevel 1 goto setup_failed
  ) else (
    echo GROQ_API_KEY=replace_with_your_key> .env
    if errorlevel 1 goto setup_failed
  )
)
echo.
echo Setup complete.
echo Open .env and replace GROQ_API_KEY with your test API key.
pause
exit /b 0

:setup_failed
echo.
echo Setup failed. Review the error above, then run setup_windows.bat again.
pause
exit /b 1
