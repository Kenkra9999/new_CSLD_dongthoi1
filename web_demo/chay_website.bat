@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Dang tao moi truong Python lan dau...
  python -m venv .venv || goto :err
  ".venv\Scripts\python.exe" -m pip install -q flask "psycopg[binary]" || goto :err
)
echo Mo trinh duyet tai http://127.0.0.1:5019 ...
start "" http://127.0.0.1:5019
".venv\Scripts\python.exe" -X utf8 app.py
pause
exit /b
:err
echo Loi khi cai dat. Kiem tra Python va ket noi mang.
pause
