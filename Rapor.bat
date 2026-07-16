@echo off
REM Matematik Avi - Ziyaretci raporu. Toplanan telemetri verisinden (data\telemetry\)
REM Turkce HTML rapor uretir ve tarayicida acar. Oyun calisirken de calistirilabilir.
cd /d "%~dp0"

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
echo Once Kurulum.bat calistirin (veya python.org'dan Python kurun).
echo.
pause
exit /b 1

:haspy
echo Rapor hazirlaniyor...
%PYRUN% tools\rapor.py
if errorlevel 1 goto runerr

start "" "%~dp0data\rapor.html"
exit /b 0

:runerr
echo.
echo [HATA] Rapor uretilirken hata olustu (yukariya bakin).
echo.
pause
exit /b 1
