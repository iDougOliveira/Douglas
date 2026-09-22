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
)

call ".venv\Scripts\activate.bat"

python -c "import mss, PIL, numpy, cv2, pytesseract" >nul 2>nul
if errorlevel 1 (
  echo Instalando/atualizando dependencias do PokerVision...
  python -m pip install --upgrade pip
  if errorlevel 1 goto :fail
  pip install -r requirements.txt
  if errorlevel 1 goto :fail
)

where tesseract >nul 2>nul
if errorlevel 1 (
  if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo.
    echo AVISO: Tesseract OCR nao encontrado.
    echo Cartas continuarao funcionando, mas BLINDS/STACK/POTE nao serao lidos.
    echo Instale uma vez com:
    echo winget install -e --id UB-Mannheim.TesseractOCR
    echo.
  )
)

python app.py
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo O PokerVision encontrou um erro.
pause
exit /b 1
