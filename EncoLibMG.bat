@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Rode primeiro o install.bat
    echo Run install.bat first
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m encolibmg
