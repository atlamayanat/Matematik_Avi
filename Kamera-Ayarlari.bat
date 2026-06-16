@echo off
REM Matematik Avi - Kamera ayar penceresi (kamera sec + onizle + kaydet).
cd /d "%~dp0python"

REM --- Python var mi? (once py -3.13, sonra herhangi bir py, sonra python) ---
set "PYRUN="
py -3.13 -c "import sys" >nul 2>&1 && set "PYRUN=py -3.13"
if not defined PYRUN ( py -c "import sys" >nul 2>&1 && set "PYRUN=py" )
if not defined PYRUN ( python -c "import sys" >nul 2>&1 && set "PYRUN=python" )

if not defined PYRUN (
    echo.
    echo [HATA] Bu bilgisayarda Python bulunamadi.
    echo Once Python 3.13 kurun:  https://www.python.org/downloads/
    echo Kurulumda "Add python.exe to PATH" kutusunu ISARETLEYIN.
    echo Sonra bu klasordeki Kurulum.bat dosyasina cift tiklayin.
    echo.
    pause
    exit /b 1
)

REM --- Gerekli paketler kurulu mu? ---
%PYRUN% -c "import cv2, PIL" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [HATA] Gerekli Python paketleri eksik (opencv-python / Pillow).
    echo Bu klasordeki Kurulum.bat dosyasina cift tiklayip paketleri kurun.
    echo.
    pause
    exit /b 1
)

%PYRUN% camera_settings.py
if errorlevel 1 (
    echo.
    echo [HATA] Kamera ayar penceresi calisirken bir hata olustu (yukariya bakin).
    echo.
    pause
)
