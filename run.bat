@echo off
chcp 65001 >nul
echo =========================================================
echo   TOAN CAU - HE THONG DOC ANH BIEN BAN ^& XUAT WORD (.DOCX)
echo =========================================================

if not exist ".venv" (
    echo [1/3] Dang khoi tao moi truong Python .venv...
    python -m venv .venv
)

echo [2/3] Dang kiem tra thu vien can thiet...
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo [3/3] Dang khoi dong Web tai http://localhost:8000 ...
start "" http://localhost:8000
uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
