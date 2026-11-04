@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ======================================
echo             MENTEX
echo ======================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python nao foi encontrado. Instale Python 3.11 ou 3.12.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Nao foi possivel criar o ambiente virtual.
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo Falha ao instalar dependencias. Confira sua conexao com a internet.
  pause
  exit /b 1
)
start "" http://127.0.0.1:5000
python app.py
pause
