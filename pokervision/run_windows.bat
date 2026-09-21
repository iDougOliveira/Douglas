@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado.
  echo Instale o Python 3 para Windows e marque "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente do PokerVision...
  py -3 -m venv .venv
  if errorlevel 1 goto :fail
  call ".venv\Scripts\activate.bat"
  python -m pip install --upgrade pip
  if errorlevel 1 goto :fail
  pip install -r requirements.txt
  if errorlevel 1 goto :fail
) else (
  call ".venv\Scripts\activate.bat"
)

python app.py
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo O PokerVision encontrou um erro.
pause
exit /b 1
