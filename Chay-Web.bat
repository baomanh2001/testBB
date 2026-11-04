@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Bien ban kiem dinh 44-48
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo.
echo ============================================================
echo   BIEN BAN KIEM DINH DIEN LUC 44-48
echo   Lan dau chay se tu cai moi truong, hoi API key 1 lan.
echo ============================================================
echo.

rem ---- 1) Tim Python ----------------------------------------------------
rem PY co the la "py -3" (co dau cach) nen KHONG boc nhay quanh bien nay.
set "PY="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python --version >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY goto :no_python

rem ---- 2) Moi truong ---------------------------------------------------
rem Uu tien .venv trong thu muc nay; chua co ma Python san co du thu vien
rem thi dung luon (khoi tao ~80 MB).
set "VPY=.venv\Scripts\python.exe"
if exist "%VPY%" (
  echo [1/3] Da co moi truong .venv.
  goto :libs
)

%PY% -c "import docx, lxml, flask" >nul 2>&1
if not errorlevel 1 (
  echo [1/3] Dung Python san co ^(da du thu vien^).
  set "VPY="
  goto :libs
)

echo [1/3] Dang tao moi truong Python .venv ...
%PY% -m venv .venv
if errorlevel 1 goto :venv_failed

:libs
rem ---- 3) Thu vien ------------------------------------------------------
if defined VPY (
  "%VPY%" -c "import docx, lxml, flask, PIL" >nul 2>&1
) else (
  %PY% -c "import docx, lxml, flask, PIL" >nul 2>&1
)
if not errorlevel 1 (
  echo [2/3] Thu vien da du.
  goto :run
)

echo [2/3] Dang cai thu vien ^(lan dau, 1-3 phut^) ...
if defined VPY (
  "%VPY%" -m pip install --upgrade pip --quiet
  "%VPY%" -m pip install --quiet -r requirements.txt
) else (
  %PY% -m pip install --upgrade pip --quiet
  %PY% -m pip install --quiet -r requirements.txt
)
if errorlevel 1 goto :pip_failed

:run
rem ---- 4) Chay ---------------------------------------------------------
echo [3/3] Dang mo web ...  ^(Ctrl+C de dung^)
echo.
if defined VPY (
  "%VPY%" launcher.py --port 8000
) else (
  %PY% launcher.py --port 8000
)
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo [!] Server dung voi ma loi %RC%.
echo Neu trinh duyet chua tu mo, bam vao link in o tren.
echo.
pause
exit /b 0

rem ======================= Xu ly loi ====================================
:no_python
echo [X] Khong tim thay Python.
echo     Tai Python 3.10+ tai: https://www.python.org/downloads/
echo     Khi cai nho TICH vao o "Add python.exe to PATH".
echo.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:venv_failed
echo [X] Tao moi truong .venv that bai.
echo     Thu chay: python -m pip install --upgrade pip setuptools
pause
exit /b 1

:pip_failed
echo [X] Cai thu vien that bai. Kiem tra ket noi mang roi chay lai.
pause
exit /b 1
