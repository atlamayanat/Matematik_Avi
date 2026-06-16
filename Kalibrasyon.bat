@echo off
REM Matematik Avi - Kalibrasyon. Projeksiyon + kamera yerlestikten sonra bir kez calistir.
REM Tam ekran hedefler cikar; oyuncu yerinde durup imleci her hedefe getirip sabit tutar.
cd /d "%~dp0python"

REM --- Python var mi? (once py -3.13, sonra herhangi bir py, sonra python) ---
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
echo [HATA] Bu bilgisayarda Python bulunamadi.
echo Once Python 3.13 kurun:  https://www.python.org/downloads/
echo Kurulumda "Add python.exe to PATH" kutusunu ISARETLEYIN.
echo Sonra bu klasordeki Kurulum.bat dosyasina cift tiklayin.
echo.
pause
exit /b 1

:haspy
%PYRUN% -c "import cv2, mediapipe" >nul 2>&1
if errorlevel 1 goto nopkg

echo.
echo Kalibrasyon basliyor. Pencereyi PROJEKSIYON ekranina tasiyin (gerekirse).
echo Oyuncu yerinde dursun; imleci her hedefe getirip ~1.5 sn sabit tutsun.
echo SPACE: yakala   B: geri   R: bastan   A: kaydet   ESC: iptal
echo.
%PYRUN% main.py --calibrate
if errorlevel 1 goto runerr
exit /b 0

:nopkg
echo.
echo [HATA] Gerekli Python paketleri eksik (opencv-python / mediapipe).
echo Bu klasordeki Kurulum.bat dosyasina cift tiklayip paketleri kurun.
echo.
pause
exit /b 1

:runerr
echo.
echo [HATA] Kalibrasyon calisirken bir hata olustu (yukariya bakin).
echo.
pause
exit /b 1
