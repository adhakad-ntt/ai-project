@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import streamlit" >nul 2>nul
if errorlevel 1 (
  echo Streamlit is missing or could not load. Run setup_windows.bat and check for installation errors.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 (
  pause
  exit /b 1
)
