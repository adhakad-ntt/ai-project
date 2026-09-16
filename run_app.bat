@echo off
setlocal
cd /d %~dp0
if not exist .venv\Scripts\activate.bat (
  echo Environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m streamlit run app.py
