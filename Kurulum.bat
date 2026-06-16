@echo off
REM Matematik Avi - Yeni PC kurulumu. Bir kez calistirin (cift tiklayin).
REM Python paketlerini (mediapipe, opencv, Pillow, ...) kurar.
cd /d "%~dp0python"

set "PYRUN="
py -3.13 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYRUN=py -3.13"
if defined PYRUN goto haspy

py -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYRUN=py"
if defined PYRUN goto haspy

python -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYRUN=python"
if defined PYRUN goto haspy

echo.
echo [HATA] Python bulunamadi. Once Python 3.13 kurun:
echo   https://www.python.org/downloads/
echo Kurulumda "Add python.exe to PATH" kutusunu ISARETLEYIN, sonra bu dosyayi tekrar calistirin.
echo.
pause
exit /b 1

:haspy
echo Python bulundu: %PYRUN%
echo Paketler kuruluyor (internet gerekir, birkac dakika surebilir)...
echo.
%PYRUN% -m pip install --upgrade pip
%PYRUN% -m pip install -r requirements.txt
if errorlevel 1 goto piperr

echo.
echo Gesture modeli indiriliyor...
%PYRUN% download_model.py

echo.
echo === KURULUM TAMAM ===
echo Artik Kamera-Ayarlari.bat ve Matematik-Avi-Baslat.bat calisabilir.
echo.
pause
exit /b 0

:piperr
echo.
echo [HATA] Paket kurulumu basarisiz. Internet baglantisini kontrol edin.
echo.
pause
exit /b 1
