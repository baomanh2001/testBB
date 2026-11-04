@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Kiem tra moi truong - Bien ban 44-48
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if not exist ".venv\Scripts\python.exe" (
  echo Chua co moi truong. Hay chay "Chay-Web.bat" truoc.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" launcher.py --check
echo.
pause
